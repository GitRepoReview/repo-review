"""Pure functions: raw GitHub JSON in, SignalResult out. No HTTP here."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from statistics import median
from typing import Any

from analysis import thresholds as t


class Status(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class SignalResult:
    id: str
    status: Status
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    level: Risk
    reason: str


INSUFFICIENT_DATA = "insufficient_data"


def _parse(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp)


def _by_age(days: float, green: int, amber: int) -> Status:
    if days <= green:
        return Status.GREEN
    return Status.AMBER if days <= amber else Status.RED


def liveness(repo: dict, commits: list[dict], now: datetime) -> SignalResult:
    """Age of the latest default-branch commit; archived is always red."""
    archived = bool(repo.get("archived"))
    dates = [_parse(c["commit"]["committer"]["date"]) for c in commits]
    days = (now - max(dates)).days if dates else None
    evidence = {"archived": archived, "days_since_last_commit": days}

    if archived:
        return SignalResult("liveness", Status.RED, "Repository is archived.", evidence)
    if days is None:
        return SignalResult(
            "liveness", Status.RED, "No commits in the last 12 months.", evidence
        )
    status = _by_age(days, t.LIVENESS_GREEN_DAYS, t.LIVENESS_AMBER_DAYS)
    return SignalResult("liveness", status, f"Last commit {days} days ago.", evidence)


def _is_bot(commit: dict) -> bool:
    author = commit.get("author") or {}
    return author.get("type") == "Bot" or (author.get("login") or "").endswith("[bot]")


def _author_key(commit: dict) -> str:
    author = commit.get("author") or {}
    return author.get("login") or commit["commit"]["author"]["email"]


def bus_factor(commits: list[dict]) -> SignalResult:
    """Share of human commits by the single most active author.

    Merge commits carry the merger's name, not an author's work, so they are
    left out of authorship.
    """
    dates = [c["commit"]["committer"]["date"] for c in commits]
    authored = [c for c in commits if len(c.get("parents", ())) <= 1]
    humans = [c for c in authored if not _is_bot(c)]
    evidence: dict[str, Any] = {
        "human_commits": len(humans),
        "bot_commits": len(authored) - len(humans),
        "merge_commits": len(commits) - len(authored),
        "sample_commits": len(commits),
        "sample_oldest": min(dates, key=_parse, default=None),
        "sample_newest": max(dates, key=_parse, default=None),
        "top_author": None,
        "top_author_share_pct": None,
    }

    if len(humans) < t.BUS_FACTOR_MIN_COMMITS:
        evidence["reason"] = INSUFFICIENT_DATA
        return SignalResult(
            "bus_factor",
            Status.AMBER,
            f"Too little activity to judge ({len(humans)} human commits).",
            evidence,
        )

    author, count = Counter(_author_key(c) for c in humans).most_common(1)[0]
    evidence["top_author"] = author
    evidence["top_author_share_pct"] = round(count * 100 / len(humans), 1)

    if count * 100 < t.BUS_FACTOR_GREEN_BELOW_PCT * len(humans):
        status = Status.GREEN
    elif count * 100 <= t.BUS_FACTOR_AMBER_UP_TO_PCT * len(humans):
        status = Status.AMBER
    else:
        status = Status.RED
    pct = evidence["top_author_share_pct"]
    summary = f"{author} wrote {pct:g}% of {len(humans)} human commits."
    if status is Status.RED:
        summary = f"Commits are concentrated in one author: {summary}"
    return SignalResult("bus_factor", status, summary, evidence)


def responsiveness(issues: list[dict], repo: dict, now: datetime) -> SignalResult:
    """Median time to close issues closed in the last 90 days.

    Pull requests and issues closed as duplicates are left out: neither says
    how fast the maintainers respond.
    """
    window = t.RESPONSIVENESS_WINDOW_DAYS
    cutoff = now - timedelta(days=window)
    open_count = repo.get("open_issues_count", 0)
    durations = [
        (_parse(i["closed_at"]) - _parse(i["created_at"])).total_seconds() / 86400
        for i in issues
        if "pull_request" not in i
        and i.get("state_reason") != "duplicate"
        and _parse(i["closed_at"]) >= cutoff
    ]
    median_days = round(median(durations), 1) if durations else None
    evidence = {
        "closed_count": len(durations),
        "median_close_days": median_days,
        "open_issues_count": open_count,
    }

    if not repo.get("has_issues", True):
        evidence["reason"] = INSUFFICIENT_DATA
        return SignalResult(
            "responsiveness",
            Status.AMBER,
            "Issues disabled: nothing to measure.",
            evidence,
        )
    if not durations and open_count > 0:
        return SignalResult(
            "responsiveness",
            Status.RED,
            f"No issues closed in the last {window} days, {open_count} still open.",
            evidence,
        )
    if len(durations) < t.RESPONSIVENESS_MIN_CLOSED:
        evidence["reason"] = INSUFFICIENT_DATA
        return SignalResult(
            "responsiveness",
            Status.AMBER,
            f"Only {len(durations)} issues closed in the last {window} days.",
            evidence,
        )
    status = _by_age(
        median(durations), t.RESPONSIVENESS_GREEN_DAYS, t.RESPONSIVENESS_AMBER_DAYS
    )
    summary = f"Median issue close time {median_days:g} days ({len(durations)} closed)."
    return SignalResult("responsiveness", status, summary, evidence)


def releases(releases_json: list[dict], now: datetime) -> SignalResult:
    """Age of the most recently published non-draft release.

    The API lists by creation date, so the newest publication can sit anywhere.
    """
    published = [r for r in releases_json if not r.get("draft")]
    latest = max(published, key=lambda r: _parse(r["published_at"]), default=None)
    if latest is None:
        return SignalResult(
            "releases",
            Status.AMBER,
            "No GitHub releases.",
            {
                "days_since_last_release": None,
                "tag_name": None,
                "reason": INSUFFICIENT_DATA,
            },
        )
    days = (now - _parse(latest["published_at"])).days
    status = _by_age(days, t.RELEASES_GREEN_DAYS, t.RELEASES_AMBER_DAYS)
    return SignalResult(
        "releases",
        status,
        f"Latest release {latest['tag_name']} was {days} days ago.",
        {"days_since_last_release": days, "tag_name": latest["tag_name"]},
    )


def license_signal(repo: dict) -> SignalResult:
    """Permissive is green, anything else needs legal review, none is red."""
    spdx_id = (repo.get("license") or {}).get("spdx_id")
    evidence = {"spdx_id": spdx_id}

    if spdx_id is None:
        return SignalResult(
            "license", Status.RED, "GitHub found no license file", evidence
        )
    if spdx_id in t.PERMISSIVE_LICENSES:
        return SignalResult(
            "license", Status.GREEN, f"{spdx_id} (permissive).", evidence
        )
    if spdx_id == t.UNCLEAR_LICENSE:
        why = "license could not be identified"
    elif spdx_id.startswith(t.COPYLEFT_PREFIXES):
        why = "copyleft license"
    else:
        why = "license is not on the reviewed list"
    summary = f"{spdx_id}: {why}, check with legal."
    return SignalResult("license", Status.AMBER, summary, evidence)


STALLED = "no commits in 12 months — you'd likely maintain it yourself"
ARCHIVED = "archived by the owner — you'd maintain it yourself"
NO_LICENSE = (
    "GitHub found no license file — you may have no right to use it; check manually"
)


SIGNAL_NAMES = {
    "liveness": "Last commit",
    "bus_factor": "One author",
    "responsiveness": "Issue response",
    "releases": "Releases",
    "license": "License",
}


def _names(ids: list[str]) -> str:
    return ", ".join(SIGNAL_NAMES[i] for i in ids)


def verdict(signals: list[SignalResult], archived: bool) -> Verdict:
    """Traffic light from signal statuses; the reason names every cause once.

    High: archived, no recent commits, no license, or two reds. Medium: one red,
    or two ambers, not counting an amber license or ambers that only mean
    "not enough data". Low: anything else.
    """
    reds = [s.id for s in signals if s.status is Status.RED]
    ambers = [s.id for s in signals if s.status is Status.AMBER]
    unsure = [s.id for s in signals if s.evidence.get("reason") == INSUFFICIENT_DATA]
    counted = [i for i in ambers if i != "license" and i not in unsure]
    stalled = "liveness" in reds and not archived
    no_license = "license" in reds

    if archived or stalled or no_license or len(reds) >= t.VERDICT_HIGH_RED_COUNT:
        level = Risk.HIGH
    elif reds or len(counted) >= t.VERDICT_MEDIUM_AMBER_COUNT:
        level = Risk.MEDIUM
    else:
        level = Risk.LOW

    sentences = []
    if archived:
        sentences.append(ARCHIVED)
    if stalled:
        sentences.append(STALLED)
    if no_license:
        sentences.append(NO_LICENSE)
    named = []
    if archived or stalled:
        named.append("liveness")
    if no_license:
        named.append("license")
    other_reds = [i for i in reds if i not in named]
    if other_reds:
        label = "also red" if sentences else "red signals"
        sentences.append(f"{label}: {_names(other_reds)}")
    if level is Risk.MEDIUM and len(counted) >= t.VERDICT_MEDIUM_AMBER_COUNT:
        sentences.append(f"amber signals: {_names(counted)}")
    if level is Risk.LOW and len(counted) == 1:
        sentences.append(f"only {SIGNAL_NAMES[counted[0]]} is a minor concern")
    if "license" in ambers:
        sentences.append("check the license")
    if unsure:
        sentences.append(f"not enough data for {_names(unsure)}")
    sentences = sentences or ["every signal is healthy"]
    return Verdict(level, " ".join(f"{x[0].upper()}{x[1:]}." for x in sentences))
