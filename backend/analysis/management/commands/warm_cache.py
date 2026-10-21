"""Fill the report cache for the demo repos so the first visitor sees data.

Goes through the same path as the endpoint: a fresh cache costs no request, and
the quota check still applies. Never fails, so a bad start-up day does not
keep the app down.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from analysis import github_client as gh
from analysis import reports

DEMO_REPOS = ["pallets/flask", "request/request", "sindresorhus/p-map"]


class Command(BaseCommand):
    help = "Pre-warm the report cache for the demo repos."

    def handle(self, *args, **options):
        for slug in DEMO_REPOS:
            owner, repo = slug.split("/")
            self.stdout.write(f"{slug}: {self.warm(owner, repo)}")

    def warm(self, owner: str, repo: str) -> str:
        try:
            meta = reports.get_report(owner, repo, timezone.now())["meta"]
        except gh.RateLimited:
            return "skipped (rate limit)"
        except Exception as exc:  # any failure must leave the exit code at 0
            return f"error ({type(exc).__name__})"
        if meta["stale"]:
            return "skipped (rate limit, stale data kept)"
        return "fresh" if meta["cached"] else "fetched"
