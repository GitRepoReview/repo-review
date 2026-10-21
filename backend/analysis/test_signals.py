from datetime import UTC, datetime, timedelta

import pytest

from analysis.signals import (
    Risk,
    SignalResult,
    Status,
    bus_factor,
    license_signal,
    liveness,
    releases,
    responsiveness,
    verdict,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def ago(days=0, hours=0):
    return (NOW - timedelta(days=days, hours=hours)).isoformat()


def commit(login="alice", *, type="User", email="a@example.com", days=1, parents=1):
    return {
        "parents": [{"sha": "p"}] * parents,
        "author": {"login": login, "type": type} if login else None,
        "commit": {"author": {"email": email}, "committer": {"date": ago(days)}},
    }


def closed_issue(*, open_days, closed_days_ago=1, hours=0):
    created = NOW - timedelta(days=closed_days_ago + open_days, hours=hours)
    return {
        "created_at": created.isoformat(),
        "closed_at": ago(closed_days_ago),
    }


def three_closed(open_days, hours=0):
    return [closed_issue(open_days=open_days, hours=hours) for _ in range(3)]


# --- liveness ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("age_days", "status"),
    [
        (0, Status.GREEN),
        (183, Status.GREEN),
        (184, Status.AMBER),
        (365, Status.AMBER),
        (366, Status.RED),
    ],
)
def test_liveness_by_age_of_latest_commit(age_days, status):
    result = liveness({"archived": False}, [commit(days=age_days)], NOW)

    assert result.status is status
    assert result.evidence["days_since_last_commit"] == age_days
    assert result.evidence["archived"] is False


def test_liveness_uses_newest_commit_regardless_of_order():
    commits = [commit(days=400), commit(days=10), commit(days=200)]

    result = liveness({"archived": False}, commits, NOW)

    assert result.evidence["days_since_last_commit"] == 10
    assert result.status is Status.GREEN


def test_liveness_red_when_no_commits_in_window():
    result = liveness({"archived": False}, [], NOW)

    assert result.status is Status.RED
    assert result.evidence["days_since_last_commit"] is None


def test_liveness_red_when_archived_despite_recent_commit():
    result = liveness({"archived": True}, [commit(days=1)], NOW)

    assert result.status is Status.RED
    assert result.evidence["archived"] is True
    assert "archived" in result.summary.lower()


# --- bus factor -------------------------------------------------------------


def commits_by(counts):
    return [commit(login) for login, n in counts.items() for _ in range(n)]


@pytest.mark.parametrize(
    ("top", "status"),
    [(49, Status.GREEN), (50, Status.AMBER), (80, Status.AMBER), (81, Status.RED)],
)
def test_bus_factor_by_top_author_share(top, status):
    rest = 100 - top
    commits = commits_by({"alice": top, "bob": rest // 2, "carol": rest - rest // 2})

    result = bus_factor(commits)

    assert result.status is status
    assert result.evidence["top_author"] == "alice"
    assert result.evidence["top_author_share_pct"] == top


def test_bus_factor_amber_when_fewer_than_ten_human_commits():
    result = bus_factor(commits_by({"alice": 9}))

    assert result.status is Status.AMBER
    assert "too little activity" in result.summary.lower()
    assert result.evidence["human_commits"] == 9


def test_bus_factor_too_little_activity_is_insufficient_data():
    result = bus_factor(commits_by({"alice": 9}))

    assert result.evidence["reason"] == "insufficient_data"


def test_bus_factor_enough_commits_has_no_insufficient_data_reason():
    result = bus_factor(commits_by({"alice": 5, "bob": 5}))

    assert "reason" not in result.evidence


def test_bus_factor_ten_human_commits_is_enough_to_judge():
    result = bus_factor(commits_by({"alice": 10}))

    assert result.status is Status.RED


def test_bus_factor_ignores_bots_by_login_suffix_and_by_type():
    commits = (
        commits_by({"alice": 6, "bob": 6})
        + [commit("dependabot[bot]") for _ in range(50)]
        + [commit("renovate-app", type="Bot") for _ in range(50)]
    )

    result = bus_factor(commits)

    assert result.status is Status.AMBER
    assert result.evidence["human_commits"] == 12
    assert result.evidence["bot_commits"] == 100
    assert result.evidence["top_author_share_pct"] == 50


def test_bus_factor_ignores_merge_commits():
    merges = [commit("alice", parents=2) for _ in range(50)]

    result = bus_factor(commits_by({"alice": 6, "bob": 6}) + merges)

    assert result.status is Status.AMBER
    assert result.evidence["human_commits"] == 12
    assert result.evidence["merge_commits"] == 50
    assert result.evidence["top_author_share_pct"] == 50


def test_bus_factor_merge_commits_do_not_count_towards_minimum_activity():
    merges = [commit("alice", parents=2) for _ in range(20)]

    result = bus_factor(commits_by({"alice": 9}) + merges)

    assert result.status is Status.AMBER
    assert "too little activity" in result.summary.lower()


def test_bus_factor_red_summary_names_the_concentration():
    result = bus_factor(commits_by({"alice": 9, "bob": 1}))

    assert result.status is Status.RED
    assert "concentrated" in result.summary
    assert "alice" in result.summary
    assert "90" in result.summary


def test_bus_factor_falls_back_to_commit_email_when_no_github_login():
    commits = [commit(None, email="ghost@example.com") for _ in range(10)]

    result = bus_factor(commits)

    assert result.evidence["top_author"] == "ghost@example.com"
    assert result.status is Status.RED


def test_bus_factor_evidence_reports_the_sample_window():
    commits = [
        commit("alice", days=5),
        commit("bob", days=30),
        commit("alice", days=2),
        commit("dependabot[bot]", days=60),
        commit("alice", days=9, parents=2),
    ]

    result = bus_factor(commits)

    assert result.evidence["sample_commits"] == 5
    assert result.evidence["sample_oldest"] == ago(60)
    assert result.evidence["sample_newest"] == ago(2)


def test_bus_factor_sample_window_is_empty_without_commits():
    result = bus_factor([])

    assert result.evidence["sample_commits"] == 0
    assert result.evidence["sample_oldest"] is None
    assert result.evidence["sample_newest"] is None


def test_bus_factor_treats_null_login_like_missing_author():
    commits = [commit(None, email="ghost@example.com") for _ in range(10)]
    for c in commits:
        c["author"] = {"login": None, "type": "User"}

    result = bus_factor(commits)

    assert result.evidence["top_author"] == "ghost@example.com"


# --- responsiveness ---------------------------------------------------------


@pytest.mark.parametrize(
    ("open_days", "hours", "status"),
    [
        (30, 0, Status.GREEN),
        (30, 1, Status.AMBER),
        (90, 0, Status.AMBER),
        (90, 1, Status.RED),
    ],
)
def test_responsiveness_by_median_close_time(open_days, hours, status):
    result = responsiveness(
        three_closed(open_days, hours), {"open_issues_count": 5}, NOW
    )

    assert result.status is status


def test_responsiveness_uses_median_not_mean():
    issues = [
        closed_issue(open_days=1),
        closed_issue(open_days=1),
        closed_issue(open_days=300),
    ]

    result = responsiveness(issues, {"open_issues_count": 5}, NOW)

    assert result.status is Status.GREEN
    assert result.evidence["median_close_days"] == 1
    assert result.evidence["closed_count"] == 3


def test_responsiveness_median_of_even_count_averages_middle_two():
    issues = [closed_issue(open_days=d) for d in (10, 20, 40, 100)]

    result = responsiveness(issues, {"open_issues_count": 5}, NOW)

    assert result.evidence["median_close_days"] == 30
    assert result.status is Status.GREEN


def test_responsiveness_skips_pull_requests():
    issues = three_closed(1) + [
        {**closed_issue(open_days=500), "pull_request": {}} for _ in range(10)
    ]

    result = responsiveness(issues, {"open_issues_count": 5}, NOW)

    assert result.evidence["closed_count"] == 3
    assert result.status is Status.GREEN


def test_responsiveness_skips_issues_closed_as_duplicate():
    duplicates = [
        {**closed_issue(open_days=500), "state_reason": "duplicate"} for _ in range(10)
    ]

    result = responsiveness(three_closed(1) + duplicates, {"open_issues_count": 5}, NOW)

    assert result.evidence["closed_count"] == 3
    assert result.status is Status.GREEN


def test_responsiveness_keeps_not_planned_and_completed_issues():
    issues = [
        {**closed_issue(open_days=1), "state_reason": "not_planned"},
        {**closed_issue(open_days=1), "state_reason": "completed"},
        {**closed_issue(open_days=1), "state_reason": None},
    ]

    result = responsiveness(issues, {"open_issues_count": 5}, NOW)

    assert result.evidence["closed_count"] == 3


def test_responsiveness_filters_by_closed_at_in_code():
    stale = closed_issue(open_days=1, closed_days_ago=91)
    boundary = closed_issue(open_days=1, closed_days_ago=90)

    result = responsiveness(
        [stale, boundary, boundary, boundary], {"open_issues_count": 5}, NOW
    )

    assert result.evidence["closed_count"] == 3


def test_responsiveness_red_when_nothing_closed_but_issues_open():
    result = responsiveness([], {"open_issues_count": 12}, NOW)

    assert result.status is Status.RED
    assert result.evidence["closed_count"] == 0
    assert result.evidence["median_close_days"] is None


def test_responsiveness_amber_when_issues_are_disabled():
    repo = {"has_issues": False, "open_issues_count": 0}

    result = responsiveness([], repo, NOW)

    assert result.status is Status.AMBER
    assert "issues disabled" in result.summary.lower()


def test_responsiveness_issues_disabled_is_never_red():
    repo = {"has_issues": False, "open_issues_count": 7}

    result = responsiveness([], repo, NOW)

    assert result.status is Status.AMBER


def test_responsiveness_red_when_nothing_closed_and_issues_enabled():
    repo = {"has_issues": True, "open_issues_count": 12}

    result = responsiveness([], repo, NOW)

    assert result.status is Status.RED


@pytest.mark.parametrize(
    ("issues", "repo"),
    [
        ([], {"has_issues": True, "open_issues_count": 0}),
        ([closed_issue(open_days=1)], {"open_issues_count": 5}),
        (
            [closed_issue(open_days=1), closed_issue(open_days=1)],
            {"open_issues_count": 5},
        ),
        ([], {"has_issues": False, "open_issues_count": 0}),
    ],
    ids=["nothing-closed-nothing-open", "one-closed", "two-closed", "issues-disabled"],
)
def test_responsiveness_without_enough_data_is_insufficient_data(issues, repo):
    result = responsiveness(issues, repo, NOW)

    assert result.status is Status.AMBER
    assert result.evidence["reason"] == "insufficient_data"


def test_responsiveness_nothing_closed_with_open_issues_is_red_not_insufficient():
    result = responsiveness([], {"has_issues": True, "open_issues_count": 3}, NOW)

    assert result.status is Status.RED
    assert "reason" not in result.evidence


def test_responsiveness_with_enough_closed_issues_has_no_reason():
    result = responsiveness(three_closed(10), {"open_issues_count": 5}, NOW)

    assert "reason" not in result.evidence


def test_responsiveness_amber_when_nothing_closed_and_nothing_open():
    result = responsiveness([], {"open_issues_count": 0}, NOW)

    assert result.status is Status.AMBER


def test_responsiveness_amber_when_fewer_than_three_closed():
    issues = [closed_issue(open_days=1), closed_issue(open_days=1)]

    result = responsiveness(issues, {"open_issues_count": 5}, NOW)

    assert result.status is Status.AMBER
    assert result.evidence["closed_count"] == 2


# --- releases ---------------------------------------------------------------


def release(days, *, draft=False, tag="v1.0.0"):
    return {"draft": draft, "tag_name": tag, "published_at": ago(days)}


@pytest.mark.parametrize(
    ("age_days", "status"),
    [
        (183, Status.GREEN),
        (184, Status.AMBER),
        (548, Status.AMBER),
        (549, Status.RED),
    ],
)
def test_releases_by_age_of_latest_release(age_days, status):
    result = releases([release(age_days)], NOW)

    assert result.status is status
    assert result.evidence["days_since_last_release"] == age_days
    assert result.evidence["tag_name"] == "v1.0.0"


def test_releases_skips_drafts():
    result = releases([release(1, draft=True, tag="v9"), release(400, tag="v2")], NOW)

    assert result.evidence["tag_name"] == "v2"
    assert result.status is Status.AMBER


def test_releases_uses_newest_published_date_not_list_order():
    payload = [
        release(400, tag="v1.0"),
        release(10, tag="v2.0"),
        release(100, tag="v1.5"),
    ]

    result = releases(payload, NOW)

    assert result.evidence["tag_name"] == "v2.0"
    assert result.evidence["days_since_last_release"] == 10
    assert result.status is Status.GREEN


def test_releases_newest_date_ignores_a_newer_draft_in_any_position():
    payload = [release(400, tag="v1.0"), release(1, draft=True, tag="v9-draft")]

    result = releases(payload, NOW)

    assert result.evidence["tag_name"] == "v1.0"


@pytest.mark.parametrize("payload", [[], [release(1, draft=True)]])
def test_releases_amber_when_no_published_releases(payload):
    result = releases(payload, NOW)

    assert result.status is Status.AMBER
    assert "no github releases" in result.summary.lower()
    assert result.evidence["days_since_last_release"] is None
    assert result.evidence["reason"] == "insufficient_data"


def test_releases_with_a_release_has_no_insufficient_data_reason():
    assert "reason" not in releases([release(10)], NOW).evidence


# --- license ----------------------------------------------------------------


@pytest.mark.parametrize(
    "spdx",
    [
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "0BSD",
        "Unlicense",
        "Zlib",
    ],
)
def test_license_permissive_is_green(spdx):
    result = license_signal({"license": {"spdx_id": spdx}})

    assert result.status is Status.GREEN
    assert result.evidence["spdx_id"] == spdx


@pytest.mark.parametrize(
    "spdx",
    [
        "GPL-3.0",
        "GPL-2.0-only",
        "LGPL-3.0",
        "AGPL-3.0",
        "MPL-2.0",
        "EPL-2.0",
        "NOASSERTION",
    ],
)
def test_license_copyleft_and_unclear_is_amber_check_with_legal(spdx):
    result = license_signal({"license": {"spdx_id": spdx}})

    assert result.status is Status.AMBER
    assert "legal" in result.summary.lower()


def test_license_unknown_spdx_id_is_amber_not_green():
    result = license_signal({"license": {"spdx_id": "WTFPL"}})

    assert result.status is Status.AMBER


def test_license_amber_summaries_explain_why_for_each_case():
    copyleft = license_signal({"license": {"spdx_id": "GPL-3.0"}}).summary
    unclear = license_signal({"license": {"spdx_id": "NOASSERTION"}}).summary
    unlisted = license_signal({"license": {"spdx_id": "WTFPL"}}).summary

    assert "copyleft" in copyleft
    assert "could not be identified" in unclear
    assert "not on the reviewed list" in unlisted
    assert len({copyleft, unclear, unlisted}) == 3


@pytest.mark.parametrize(
    "repo", [{"license": None}, {}, {"license": {"spdx_id": None}}]
)
def test_license_missing_is_red(repo):
    result = license_signal(repo)

    assert result.status is Status.RED
    assert result.summary == "GitHub found no license file"
    assert result.evidence["spdx_id"] is None


# --- verdict ----------------------------------------------------------------

IDS = ["liveness", "bus_factor", "responsiveness", "releases", "license"]


def signals(*statuses, insufficient=()):
    return [
        SignalResult(
            id=id,
            status=status,
            summary="",
            evidence={"reason": "insufficient_data"} if id in insufficient else {},
        )
        for id, status in zip(IDS, statuses, strict=True)
    ]


G, A, R = Status.GREEN, Status.AMBER, Status.RED


@pytest.mark.parametrize(
    ("statuses", "level"),
    [
        ((G, G, G, G, G), Risk.LOW),
        ((G, A, G, G, G), Risk.LOW),
        ((G, A, A, G, G), Risk.MEDIUM),
        ((G, G, G, R, G), Risk.MEDIUM),
        ((G, G, G, R, A), Risk.MEDIUM),
        ((R, R, G, G, G), Risk.HIGH),
        ((R, A, A, R, A), Risk.HIGH),
        ((G, G, G, G, R), Risk.HIGH),
        ((R, G, G, G, G), Risk.HIGH),
        ((R, A, A, A, G), Risk.HIGH),
    ],
)
def test_verdict_level(statuses, level):
    assert verdict(signals(*statuses), archived=False).level is level


def test_verdict_high_when_archived_even_if_only_one_red():
    result = verdict(signals(R, G, G, G, G), archived=True)

    assert result.level is Risk.HIGH
    assert "archived" in result.reason.lower()


def test_verdict_stalled_liveness_reason_says_no_commits_in_12_months():
    result = verdict(signals(R, G, G, G, G), archived=False)

    assert result.level is Risk.HIGH
    assert (
        "no commits in 12 months — you'd likely maintain it yourself" in result.reason
    )


def test_verdict_archived_reason_says_archived_by_the_owner():
    result = verdict(signals(R, G, G, G, G), archived=True)

    assert result.level is Risk.HIGH
    assert "archived by the owner — you'd maintain it yourself" in result.reason
    assert "no commits" not in result.reason


def test_verdict_no_license_reason_warns_about_the_right_to_use():
    result = verdict(signals(G, G, G, G, R), archived=False)

    assert result.level is Risk.HIGH
    assert (
        "GitHub found no license file — you may have no right to use it; check manually"
    ) in result.reason
    assert "maintain it yourself" not in result.reason


def test_verdict_names_each_cause_once():
    result = verdict(signals(R, G, G, R, R), archived=False)

    assert result.reason.count("no commits in 12 months") == 1
    assert result.reason.count("no license file") == 1
    assert result.reason.count("releases") == 1
    assert "liveness" not in result.reason


@pytest.mark.parametrize(
    ("statuses", "insufficient", "level"),
    [
        ((G, A, G, G, A), (), Risk.LOW),  # amber license does not count
        ((G, A, A, G, G), (), Risk.MEDIUM),
        ((G, A, A, G, G), ("bus_factor",), Risk.LOW),
        ((G, A, A, G, G), ("bus_factor", "responsiveness"), Risk.LOW),
        ((G, A, A, A, A), ("bus_factor",), Risk.MEDIUM),  # responsiveness + releases
        ((G, A, G, A, A), ("releases",), Risk.LOW),
        ((G, G, G, R, A), ("bus_factor",), Risk.MEDIUM),  # one red still counts
    ],
)
def test_verdict_amber_license_and_insufficient_data_do_not_count(
    statuses, insufficient, level
):
    result = verdict(signals(*statuses, insufficient=insufficient), archived=False)

    assert result.level is level


def test_verdict_mentions_amber_license():
    result = verdict(signals(G, G, G, G, A), archived=False)

    assert result.level is Risk.LOW
    assert "check the license" in result.reason


def test_verdict_mentions_each_insufficient_data_signal():
    result = verdict(
        signals(
            G, A, A, A, G, insufficient=("bus_factor", "responsiveness", "releases")
        ),
        archived=False,
    )

    assert "not enough data for bus_factor" in result.reason
    assert "not enough data for responsiveness" in result.reason
    assert "not enough data for releases" in result.reason


def test_verdict_reason_names_the_signals_that_drove_it():
    result = verdict(signals(G, R, G, R, G), archived=False)

    assert "bus_factor" in result.reason
    assert "releases" in result.reason


def test_verdict_medium_reason_names_amber_signals():
    result = verdict(signals(G, A, A, G, G), archived=False)

    assert "bus_factor" in result.reason
    assert "responsiveness" in result.reason


def test_verdict_low_reason_is_one_sentence():
    result = verdict(signals(G, G, G, G, G), archived=False)

    assert result.reason.endswith(".")
    assert result.reason.count(".") == 1


def test_signal_result_is_frozen():
    result = license_signal({"license": {"spdx_id": "MIT"}})

    with pytest.raises(AttributeError):
        result.status = Status.RED
