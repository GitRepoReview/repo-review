import io
from datetime import timedelta

from django.core.management import call_command

from analysis.management.commands import warm_cache
from analysis.test_report import frozen_now, seed_cache  # noqa: F401  (autouse fixture)


def test_fresh_cache_makes_no_requests(github, monkeypatch):
    monkeypatch.setattr(warm_cache, "DEMO_REPOS", ["pallets/flask"])
    seed_cache(timedelta(hours=1))
    out = io.StringIO()

    call_command("warm_cache", stdout=out)

    assert out.getvalue().strip() == "pallets/flask: fresh"
    assert len(github.calls) == 0
