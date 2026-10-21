import pytest
import respx
from django.core.cache import cache
from django.core.management import call_command


@pytest.fixture(autouse=True)
def report_cache(db, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    call_command("createcachetable")
    yield
    cache.clear()


@pytest.fixture
def github():
    """Any request not mocked here fails: the tests never touch the network."""
    with respx.mock(base_url="https://api.github.com", assert_all_called=False) as mock:
        yield mock
