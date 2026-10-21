"""Cache policy and report assembly: the glue between client, cache and signals."""

from datetime import datetime, timedelta

from django.core.cache import cache

from analysis import github_client as gh
from analysis import signals as s
from analysis import thresholds as t


def _bundle_key(slug: str) -> str:
    return f"bundle:{slug}"


def _missing_key(slug: str) -> str:
    return f"missing:{slug}"


MISSING = {"not_found": gh.RepoNotFound, "empty_repo": gh.EmptyRepo}


def store_bundle(slug: str, bundle: dict) -> None:
    cache.set(_bundle_key(slug), bundle, timeout=t.REPORT_KEEP_DAYS * 86400)


def store_missing(slug: str, code: str) -> None:
    cache.set(_missing_key(slug), code, timeout=t.MISSING_CACHE_HOURS * 3600)


def _is_fresh(bundle: dict, now: datetime) -> bool:
    age = now - datetime.fromisoformat(bundle["fetched_at"])
    return age < timedelta(hours=t.REPORT_FRESH_HOURS)


def build_report(
    bundle: dict,
    now: datetime,
    *,
    cached: bool,
    stale: bool,
    limit: gh.RateLimit | None,
) -> dict:
    repo = bundle["repo"]
    results = [
        s.liveness(repo, bundle["commits"], now),
        s.bus_factor(bundle["commits"]),
        s.responsiveness(bundle["issues"], repo, now),
        s.releases(bundle["releases"], now),
        s.license_signal(repo),
    ]
    verdict = s.verdict(results, repo["archived"])
    return {
        "repo": repo["full_name"],
        "verdict": {"level": verdict.level, "reason": verdict.reason},
        "signals": [
            {
                "id": r.id,
                "status": r.status,
                "summary": r.summary,
                "evidence": r.evidence,
            }
            for r in results
        ],
        "context": {
            "stars": repo["stargazers_count"],
            "forks": repo["forks_count"],
            "language": repo["language"],
            "created_at": repo["created_at"],
            "pushed_at": repo["pushed_at"],
            "archived": repo["archived"],
            "description": repo["description"],
            "watchers": repo["subscribers_count"],
            "open_issues": repo["open_issues_count"],
            "html_url": repo["html_url"],
            "homepage": repo["homepage"] or None,
        },
        "meta": {
            "cached": cached,
            "stale": stale,
            "fetched_at": bundle["fetched_at"],
            "rate_limit": limit.as_dict() if limit else None,
        },
    }


def get_report(owner: str, repo: str, now: datetime) -> dict:
    """Fresh cache, else refresh if quota allows, else stale, else raise.

    Raises RepoNotFound, EmptyRepo, RateLimited or UpstreamError if nothing is served.
    """
    slug = f"{owner}/{repo}".lower()
    if code := cache.get(_missing_key(slug)):
        raise MISSING[code](slug)

    cached = cache.get(_bundle_key(slug))
    if cached and _is_fresh(cached, now):
        return build_report(cached, now, cached=True, stale=False, limit=None)

    try:
        limit = gh.fetch_rate_limit()
        if limit.remaining < t.MIN_REQUESTS_REMAINING:
            raise gh.RateLimited(limit)
        bundle, limit = gh.fetch_bundle(owner, repo, now)
    except gh.RepoNotFound:
        store_missing(slug, "not_found")
        raise
    except gh.EmptyRepo:
        store_missing(slug, "empty_repo")
        raise
    except (gh.RateLimited, gh.UpstreamError) as exc:
        if not cached:
            raise
        limit = exc.limit if isinstance(exc, gh.RateLimited) else None
        return build_report(cached, now, cached=True, stale=True, limit=limit)

    store_bundle(slug, bundle)
    return build_report(bundle, now, cached=False, stale=False, limit=limit)
