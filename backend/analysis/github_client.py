"""The only module that talks to GitHub. Raw JSON out, typed errors for the rest."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from analysis import thresholds as t

API = "https://api.github.com"
TIMEOUT = httpx.Timeout(10.0)

# Request params per endpoint; the fixtures were recorded with the same ones.
REPO_PARAMS: dict = {}
COMMITS_PARAMS = {"per_page": 100}
ISSUES_PARAMS = {"state": "closed", "per_page": 100}
RELEASES_PARAMS = {"per_page": 10}
SINCE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class RepoNotFound(Exception):
    pass


class EmptyRepo(Exception):
    """GitHub answers 409 on /commits for a repository without commits."""


class UpstreamError(Exception):
    pass


@dataclass(frozen=True)
class RateLimit:
    remaining: int
    reset_at: datetime

    def as_dict(self) -> dict:
        return {"remaining": self.remaining, "reset_at": self.reset_at.isoformat()}


class RateLimited(Exception):
    def __init__(self, limit: RateLimit):
        super().__init__(f"GitHub rate limit: {limit.remaining} requests left")
        self.limit = limit


def _rate_limit(response: httpx.Response) -> RateLimit:
    try:
        remaining = int(response.headers["x-ratelimit-remaining"])
        reset = int(response.headers["x-ratelimit-reset"])
    except (KeyError, ValueError):
        raise UpstreamError("GitHub response has no rate limit headers") from None
    return RateLimit(remaining, datetime.fromtimestamp(reset, UTC))


def _get(http: httpx.Client, path: str, params: dict | None = None) -> httpx.Response:
    try:
        response = http.get(path, params=params)
    except httpx.HTTPError as exc:
        raise UpstreamError(f"GitHub request failed: {exc!r}") from exc
    status = response.status_code
    if status in (403, 429) and response.headers.get("x-ratelimit-remaining") == "0":
        raise RateLimited(_rate_limit(response))
    if status == 404:
        raise RepoNotFound(path)
    if status == 409 and path.endswith("/commits"):
        raise EmptyRepo(path)
    if status != 200:
        raise UpstreamError(f"GitHub returned {status} for {path}")
    return response


def _client() -> httpx.Client:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "repo-review",
    }
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=API, headers=headers, timeout=TIMEOUT)


def fetch_rate_limit() -> RateLimit:
    """GET /rate_limit does not count against the quota."""
    with _client() as http:
        return _rate_limit(_get(http, "/rate_limit"))


def _since(now: datetime, days: int) -> str:
    return (now - timedelta(days=days)).strftime(SINCE_FORMAT)


def fetch_bundle(owner: str, repo: str, now: datetime) -> tuple[dict, RateLimit]:
    """Four requests: the repo, then commits, issues and releases by its full_name."""
    with _client() as http:
        repo_json = _get(http, f"/repos/{owner}/{repo}", REPO_PARAMS).json()
        base = f"/repos/{repo_json['full_name']}"
        commits_params = {
            **COMMITS_PARAMS,
            "since": _since(now, t.BUS_FACTOR_WINDOW_DAYS),
        }
        issues_params = {
            **ISSUES_PARAMS,
            "since": _since(now, t.RESPONSIVENESS_WINDOW_DAYS),
        }
        try:
            commits = _get(http, f"{base}/commits", commits_params)
            issues = _get(http, f"{base}/issues", issues_params)
            releases = _get(http, f"{base}/releases", RELEASES_PARAMS)
        except RepoNotFound as exc:
            raise UpstreamError("repository vanished mid-analysis") from exc
    bundle = {
        "repo": repo_json,
        "commits": commits.json(),
        "issues": issues.json(),
        "releases": releases.json(),
        "fetched_at": now.isoformat(timespec="seconds"),
    }
    return bundle, _rate_limit(releases)
