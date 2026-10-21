"""Endpoint and client tests. GitHub is mocked with respx; no network."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

import httpx
import pytest
from django.core.cache import cache
from django.utils import timezone

from analysis import github_client as gh
from analysis import reports

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "pallets_flask.json").read_text()
)
NOW = datetime.fromisoformat(FIXTURE["fetched_at"])
RESET = 1_900_000_000
URL = "/api/repos/pallets/flask/report"


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW)


def limit_headers(remaining=50):
    return {"x-ratelimit-remaining": str(remaining), "x-ratelimit-reset": str(RESET)}


def mock_github(github, remaining=50, full_name="pallets/flask"):
    """Quota is read from /rate_limit first, then from the last response."""
    repo = {**FIXTURE["repo"], "full_name": full_name}
    routes = {
        "rate_limit": github.get("/rate_limit").respond(
            200, headers=limit_headers(remaining)
        ),
        "repo": github.get(f"/repos/{full_name}").respond(200, json=repo),
        "commits": github.get(f"/repos/{full_name}/commits").respond(
            200, json=FIXTURE["commits"]
        ),
        "issues": github.get(f"/repos/{full_name}/issues").respond(
            200, json=FIXTURE["issues"]
        ),
        "releases": github.get(f"/repos/{full_name}/releases").respond(
            200, json=FIXTURE["releases"], headers=limit_headers(remaining - 4)
        ),
    }
    return routes


def seed_cache(age: timedelta, key="pallets/flask"):
    bundle = {**FIXTURE, "fetched_at": (NOW - age).isoformat(timespec="seconds")}
    reports.store_bundle(key, bundle)
    return bundle


def calls(routes):
    return {name: route.call_count for name, route in routes.items()}


def test_uncached_report_calls_github_and_returns_the_contract(client, github):
    routes = mock_github(github)

    response = client.get(URL)

    body = response.json()
    assert response.status_code == 200
    assert calls(routes) == dict.fromkeys(routes, 1)
    assert body["repo"] == "pallets/flask"
    assert body["verdict"]["level"] in {"low", "medium", "high"}
    assert body["verdict"]["reason"]
    assert [s["id"] for s in body["signals"]] == [
        "liveness",
        "bus_factor",
        "responsiveness",
        "releases",
        "license",
    ]
    assert set(body["context"]) == {
        "stars",
        "forks",
        "language",
        "created_at",
        "pushed_at",
        "archived",
        "description",
    }
    assert body["meta"] == {
        "cached": False,
        "stale": False,
        "fetched_at": FIXTURE["fetched_at"],
        "rate_limit": {
            "remaining": 46,
            "reset_at": datetime.fromtimestamp(RESET, UTC).isoformat(),
        },
    }


def test_requests_use_the_recorded_params(github):
    routes = mock_github(github)

    gh.fetch_bundle("pallets", "flask", NOW)

    def params(name):
        return dict(routes[name].calls.last.request.url.params)

    assert params("repo") == {}
    assert params("commits") == {"per_page": "100", "since": "2025-10-21T16:59:17Z"}
    assert params("issues") == {
        "state": "closed",
        "per_page": "100",
        "since": "2026-07-23T16:59:17Z",
    }
    assert params("releases") == {"per_page": "10"}


def test_fresh_cache_makes_no_github_call(client, github):
    routes = mock_github(github)
    seed_cache(timedelta(hours=23))

    body = client.get(URL).json()

    assert calls(routes) == dict.fromkeys(routes, 0)
    assert body["meta"]["cached"] is True
    assert body["meta"]["stale"] is False
    assert body["meta"]["rate_limit"] is None


def test_cache_key_is_the_lowercased_input(client, github):
    routes = mock_github(github)

    client.get(URL)
    client.get("/api/repos/Pallets/Flask/report")

    assert routes["repo"].call_count == 1


def test_stale_cache_is_refreshed_when_quota_allows(client, github):
    routes = mock_github(github)
    seed_cache(timedelta(hours=25))

    body = client.get(URL).json()

    assert routes["repo"].call_count == 1
    assert body["meta"]["cached"] is False
    assert body["meta"]["fetched_at"] == FIXTURE["fetched_at"]
    assert cache.get("bundle:pallets/flask")["fetched_at"] == FIXTURE["fetched_at"]


def test_stale_cache_is_served_when_budget_is_low(client, github):
    routes = mock_github(github, remaining=3)
    old = seed_cache(timedelta(hours=25))

    response = client.get(URL)

    body = response.json()
    assert response.status_code == 200
    assert calls(routes) == {**dict.fromkeys(routes, 0), "rate_limit": 1}
    assert body["meta"]["cached"] is True
    assert body["meta"]["stale"] is True
    assert body["meta"]["fetched_at"] == old["fetched_at"]
    assert body["meta"]["rate_limit"]["remaining"] == 3


def test_stale_cache_is_served_when_refresh_fails_midway(client, github):
    routes = mock_github(github)
    routes["issues"].respond(500)
    old = seed_cache(timedelta(hours=25))

    body = client.get(URL).json()

    assert body["meta"]["stale"] is True
    assert body["meta"]["rate_limit"] is None
    assert cache.get("bundle:pallets/flask") == old


def test_budget_below_four_refuses_to_start_without_cache(client, github):
    routes = mock_github(github, remaining=3)

    response = client.get(URL)

    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "rate_limited",
            "message": "GitHub request budget is used up. Try again after the reset.",
            "reset_at": datetime.fromtimestamp(RESET, UTC).isoformat(),
        }
    }
    assert calls(routes) == {**dict.fromkeys(routes, 0), "rate_limit": 1}


def test_budget_of_exactly_four_starts_the_analysis(client, github):
    mock_github(github, remaining=4)

    assert client.get(URL).status_code == 200


@pytest.mark.parametrize("status", [403, 429])
def test_exhausted_limit_midway_is_429_and_nothing_is_cached(client, github, status):
    routes = mock_github(github)
    routes["commits"].respond(status, headers=limit_headers(0))

    response = client.get(URL)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert cache.get("bundle:pallets/flask") is None


@pytest.mark.parametrize("status", [403, 429])
def test_403_or_429_with_quota_left_is_upstream_error(client, github, status):
    routes = mock_github(github)
    routes["repo"].respond(status, headers=limit_headers(30))

    response = client.get(URL)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_error"


def test_unknown_repo_is_404_and_remembered(client, github):
    routes = mock_github(github)
    routes["repo"].respond(404)

    first = client.get(URL)
    second = client.get(URL)

    assert first.status_code == second.status_code == 404
    assert first.json()["error"]["code"] == "not_found"
    assert routes["repo"].call_count == 1
    assert routes["rate_limit"].call_count == 1


def test_upstream_failure_is_502_and_nothing_is_cached(client, github):
    routes = mock_github(github)
    routes["releases"].respond(500)

    response = client.get(URL)

    assert response.status_code == 502
    assert cache.get("bundle:pallets/flask") is None


def test_network_error_is_502(client, github):
    routes = mock_github(github)
    routes["repo"].mock(side_effect=httpx.ConnectTimeout("slow"))

    assert client.get(URL).status_code == 502


def test_redirect_is_not_followed_and_is_502(client, github):
    routes = mock_github(github)
    routes["repo"].respond(
        301, headers={"location": "https://api.github.com/repositories/1"}
    )

    assert client.get(URL).status_code == 502


def test_renamed_repo_reports_full_name_and_uses_it_for_later_calls(client, github):
    routes = mock_github(github, full_name="psf/requests")
    github.get("/repos/kennethreitz/requests").respond(
        200, json={**FIXTURE["repo"], "full_name": "psf/requests"}
    )

    body = client.get("/api/repos/kennethreitz/requests/report").json()

    assert body["repo"] == "psf/requests"
    assert [routes[n].call_count for n in ("commits", "issues", "releases")] == [
        1,
        1,
        1,
    ]
    assert cache.get("bundle:kennethreitz/requests") is not None


@pytest.mark.parametrize(
    "owner_repo", ["-bad/flask", "pallets/..", "pallets/fl%20ask", "a" * 40 + "/x"]
)
def test_invalid_repo_is_400_without_any_call(client, github, owner_repo):
    response = client.get(f"/api/repos/{owner_repo}/report")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_repo"
    assert len(github.calls) == 0


def test_report_is_get_only(client):
    assert client.post(URL).status_code == 405


def test_token_is_sent_only_when_set(github, monkeypatch):
    route = github.get("/rate_limit").respond(200, headers=limit_headers())

    gh.fetch_rate_limit()
    assert "authorization" not in route.calls.last.request.headers

    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    gh.fetch_rate_limit()
    assert route.calls.last.request.headers["authorization"] == "Bearer t0ken"


def test_empty_repo_is_422_stops_early_and_is_remembered(client, github):
    routes = mock_github(github)
    routes["commits"].respond(409, json={"message": "Git Repository is empty."})

    first = client.get(URL)
    second = client.get(URL)

    assert first.status_code == second.status_code == 422
    assert first.json()["error"]["code"] == "empty_repo"
    assert routes["issues"].call_count == routes["releases"].call_count == 0
    assert routes["repo"].call_count == 1
    assert routes["rate_limit"].call_count == 1


@pytest.fixture
def cache_set():
    with mock.patch.object(cache, "set", wraps=cache.set) as spy:
        yield spy


def test_report_is_cached_for_thirty_days(client, github, cache_set):
    mock_github(github)

    client.get(URL)

    assert [c.kwargs["timeout"] for c in cache_set.call_args_list] == [30 * 86400]


@pytest.mark.parametrize("status", [404, 409])
def test_not_found_and_empty_repo_are_cached_for_an_hour(
    client, github, cache_set, status
):
    routes = mock_github(github)
    routes["repo" if status == 404 else "commits"].respond(status)

    client.get(URL)

    assert [c.kwargs["timeout"] for c in cache_set.call_args_list] == [3600]


@pytest.mark.parametrize("status", [403, 429])
def test_403_or_429_without_limit_headers_is_upstream_error(client, github, status):
    routes = mock_github(github)
    routes["repo"].respond(status)

    response = client.get(URL)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_error"
