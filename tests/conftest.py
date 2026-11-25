"""Shared fixtures (T-04).

- autouse `netguard`: any non-loopback connection or name lookup fails the test, even if the code under test swallowed
  the exception.
- autouse AI-key scrub: ANTHROPIC_API_KEY and OPENAI_API_KEY are unset for every non-live test (O1 by default).
- `req` markers are copied into junit `<property name="req">` entries for tools/req_coverage.py.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.support.clock import FrozenClock
from tests.support.fixture_server import FixtureServer
from tests.support.netguard import NetGuard

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
AI_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def pytest_collection_modifyitems(config, items):
    live = os.environ.get("NEWSMON_LIVE") == "1"
    for item in items:
        for m in item.iter_markers("req"):
            for rid in m.args:
                item.user_properties.append(("req", rid))
        if item.get_closest_marker("corpus") and not CORPUS_PRESENT:
            item.add_marker(pytest.mark.skip(reason="needs the private corpus fixtures (tests/fixtures/feeds, gold)"))
        if item.get_closest_marker("live") and not live:
            item.add_marker(pytest.mark.skip(reason="live test: set NEWSMON_LIVE=1"))


# Fixtures built from captured third-party news (tests/fixtures/feeds, tests/fixtures/gold) are private research data
# and are not distributed. Where they are absent, a test that fails only because it tried to open one is reported as
# skipped, with the reason, instead of failed. Nothing changes where they are present.
CORPUS_DIRS = (FIXTURES / "feeds", FIXTURES / "gold")
CORPUS_PRESENT = all(d.is_dir() for d in CORPUS_DIRS)


def _needs_missing_corpus(excinfo) -> bool:
    if CORPUS_PRESENT or excinfo is None or not excinfo.errisinstance(FileNotFoundError):
        return False
    missing = Path(str(getattr(excinfo.value, "filename", "") or "")).resolve()
    return any(missing.is_relative_to(d.resolve()) for d in CORPUS_DIRS)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.failed and call.when in ("setup", "call") and _needs_missing_corpus(call.excinfo):
        rep.outcome = "skipped"
        rep.longrepr = (str(item.path), item.location[1] or 0,
                        "Skipped: needs the private corpus fixtures (tests/fixtures/feeds, tests/fixtures/gold)")


@pytest.fixture(scope="session", autouse=True)
def _cache_fixed_setup_costs():
    """Every App builds an httpx client (0.6 s for a TLS context the loopback tests never use) and an LSH index
    (0.09 s of parameter optimisation). Both are pure functions of their arguments, so compute them once per session."""
    import functools

    import datasketch.lsh
    import httpx._transports.default as transport

    mp = pytest.MonkeyPatch()
    mp.setattr(transport, "create_ssl_context", functools.cache(transport.create_ssl_context))
    mp.setattr(datasketch.lsh, "_optimal_param", functools.cache(datasketch.lsh._optimal_param))
    yield
    mp.undo()


@pytest.fixture(autouse=True)
def netguard(request):
    if request.node.get_closest_marker("live"):  # opt-in provider tests (NEWSMON_LIVE=1) are the only network users
        yield None
        return
    guard = NetGuard().install()
    try:
        yield guard
    finally:
        guard.uninstall()
    leaked = guard.take()
    if leaked and not request.node.get_closest_marker("netguard_expected"):
        pytest.fail(f"netguard: non-loopback network attempts: {leaked}")


@pytest.fixture(autouse=True)
def _scrub_ai_keys(request, monkeypatch):
    if not request.node.get_closest_marker("live"):
        for k in AI_KEYS:
            monkeypatch.delenv(k, raising=False)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def fixture_server():
    srv = FixtureServer().start()
    yield srv
    srv.stop()


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock()
