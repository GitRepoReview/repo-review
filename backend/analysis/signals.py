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
    """Share of human commits by the single most active author."""
    humans = [c for c in commits if not _is_bot(c)]
    evidence: dict[str, Any] = {
        "human_commits": len(humans),
        "bot_commits": len(commits) - len(humans),
        "top_author": None,
        "top_author_share_pct": None,
    }

    if len(humans) < t.BUS_FACTOR_MIN_COMMITS:
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
    return SignalResult("bus_factor", status, summary, evidence)


def responsiveness(issues: list[dict], repo: dict, now: datetime) -> SignalResult:
    """Median time to close issues (not PRs) closed in the last 90 days."""
    window = t.RESPONSIVENESS_WINDOW_DAYS
    cutoff = now - timedelta(days=window)
    open_count = repo.get("open_issues_count", 0)
    durations = [
        (_parse(i["closed_at"]) - _parse(i["created_at"])).total_seconds() / 86400
        for i in issues
        if "pull_request" not in i and _parse(i["closed_at"]) >= cutoff
    ]
    median_days = round(median(durations), 1) if durations else None
    evidence = {
        "closed_count": len(durations),
        "median_close_days": median_days,
        "open_issues_count": open_count,
    }

    if not durations and open_count > 0:
        return SignalResult(
            "responsiveness",
            Status.RED,
            f"No issues closed in the last {window} days, {open_count} still open.",
            evidence,
        )
    if len(durations) < t.RESPONSIVENESS_MIN_CLOSED:
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
    """Age of the latest non-draft release."""
    latest = next((r for r in releases_json if not r.get("draft")), None)
    if latest is None:
        return SignalResult(
            "releases",
            Status.AMBER,
            "No GitHub releases.",
            {"days_since_last_release": None, "tag_name": None},
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
        return SignalResult("license", Status.RED, "No license declared.", evidence)
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


def verdict(signals: list[SignalResult], archived: bool) -> Verdict:
    """Traffic light from signal statuses.

    High means you would end up maintaining it yourself: archived, no license,
    no recent commits (liveness red) or several red signals.
    """
    reds = [s.id for s in signals if s.status is Status.RED]
    ambers = [s.id for s in signals if s.status is Status.AMBER]
    no_license = "license" in reds
    stalled = "liveness" in reds and not archived

    if archived or no_license or stalled or len(reds) >= t.VERDICT_HIGH_RED_COUNT:
        causes = []
        if archived:
            causes.append("the repository is archived")
        if no_license:
            causes.append("it has no license")
        if stalled:
            causes.append("liveness is red, nobody is committing")
        if len(reds) >= t.VERDICT_HIGH_RED_COUNT:
            causes.append(f"red signals: {', '.join(reds)}")
        reason = f"High risk, you'd likely maintain it yourself: {'; '.join(causes)}."
        return Verdict(Risk.HIGH, reason)
    if reds or len(ambers) >= t.VERDICT_MEDIUM_AMBER_COUNT:
        flagged = ", ".join(reds + ambers)
        return Verdict(Risk.MEDIUM, f"Medium risk: needs a closer look at {flagged}.")
    if ambers:
        return Verdict(Risk.LOW, f"Low risk: only {ambers[0]} is a minor concern.")
    return Verdict(Risk.LOW, "Low risk: every signal is healthy.")
