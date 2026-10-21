"""Smoke tests: real recorded GitHub responses through every signal.

Each fixture holds the four responses plus `fetched_at`, which is used as `now`
so the tests do not age. Expectations were written before recording; where the
real data disagreed, the test pins what the rules actually give and says so.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from analysis.signals import (
    Risk,
    bus_factor,
    license_signal,
    liveness,
    releases,
    responsiveness,
    verdict,
)

FIXTURES = Path(__file__).parent / "fixtures"


def report(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    now = datetime.fromisoformat(data["fetched_at"])
    repo, commits = data["repo"], data["commits"]
    signals = [
        liveness(repo, commits, now),
        bus_factor(commits),
        responsiveness(data["issues"], repo, now),
        releases(data["releases"], now),
        license_signal(repo),
    ]
    return {s.id: s for s in signals}, verdict(signals, repo["archived"])


def statuses(signals):
    return {id: s.status.value for id, s in signals.items()}


def test_active_repo_pallets_flask_is_medium_risk():
    # Predicted low. One maintainer wrote 88% of the non-merge commits (bus
    # factor red, after dropping 36 merge commits) and the last release is
    # 8 months old (amber).
    signals, result = report("pallets_flask")

    assert statuses(signals) == {
        "liveness": "green",
        "bus_factor": "red",
        "responsiveness": "green",
        "releases": "amber",
        "license": "green",
    }
    evidence = signals["bus_factor"].evidence
    assert evidence["merge_commits"] == 36
    assert evidence["sample_commits"] == 94
    assert evidence["sample_oldest"] == "2025-11-17T16:49:53Z"
    assert evidence["sample_newest"] == "2026-10-07T14:02:54Z"
    assert evidence["top_author_share_pct"] == 87.9
    assert "concentrated" in signals["bus_factor"].summary
    assert result.level is Risk.MEDIUM
    assert result.reason == "Medium risk: red signals: bus_factor."


def test_archived_repo_atom_atom_is_high_risk():
    signals, result = report("atom_atom")

    assert statuses(signals) == {
        "liveness": "red",
        "bus_factor": "amber",
        "responsiveness": "red",
        "releases": "red",
        "license": "green",
    }
    assert result.level is Risk.HIGH
    assert "archived by the owner — you'd maintain it yourself" in result.reason
    assert "also red: responsiveness, releases" in result.reason
    assert "not enough data for bus_factor" in result.reason


def test_deprecated_but_not_archived_request_request_is_high_risk():
    # GitHub does not flag it as archived, but nothing has been committed for
    # years: red liveness alone is high (D-77).
    signals, result = report("request_request")

    assert statuses(signals) == {
        "liveness": "red",
        "bus_factor": "amber",
        "responsiveness": "amber",
        "releases": "amber",
        "license": "green",
    }
    assert result.level is Risk.HIGH
    assert (
        "no commits in 12 months — you'd likely maintain it yourself" in result.reason
    )
    for id in ("bus_factor", "responsiveness", "releases"):
        assert signals[id].evidence["reason"] == "insufficient_data"
        assert f"not enough data for {id}" in result.reason


def test_single_maintainer_repo_sindresorhus_p_map_is_high_risk():
    # Predicted medium. The 90-day window holds a backlog sweep: 11 old
    # issues were closed in one go, so the median close time is ~1000 days.
    signals, result = report("sindresorhus_p-map")

    assert statuses(signals) == {
        "liveness": "green",
        "bus_factor": "red",
        "responsiveness": "red",
        "releases": "green",
        "license": "green",
    }
    assert result.level is Risk.HIGH
    assert result.reason == "High risk: red signals: bus_factor, responsiveness."


@pytest.mark.parametrize(
    "name",
    ["pallets_flask", "atom_atom", "request_request", "sindresorhus_p-map"],
)
def test_fixture_evidence_is_json_serialisable(name):
    signals, _ = report(name)

    for signal in signals.values():
        json.dumps(signal.evidence)
