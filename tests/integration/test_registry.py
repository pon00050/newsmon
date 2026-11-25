"""Source registry (T-13): FR-01(a)(b)(c), TS-SEC-12, FR-30(b)."""
import json
from pathlib import Path

import pytest
import yaml

from newsmon.config.loader import ConfigError
from newsmon.registry.loader import AdapterNotImplemented, parse_sources
from tests.support.clock import FrozenClock
from tests.support.instance import EXAMPLE, feed_source, make_app, mock_wire_sources, serve_feeds

pytestmark = pytest.mark.integration
FLAG_COLS = ("storage", "display", "ai_processing", "external_ai_allowed", "permitted_ops", "redistribution", "training",
             "licence_owner", "allowed_contexts", "third_party_processors_allowed", "synthetic", "active")
P_ONLY = {"guardian_world", "cna_sg_all", "yna_news", "yna_intl", "yna_nk", "khan_total", "cna_tw_intl", "cna_tw_mainland"}


def seed_rows():
    return yaml.safe_load((EXAMPLE / "sources.yaml").read_text(encoding="utf-8"))["sources"]


@pytest.mark.req("FR-01a")
def test_seed(tmp_path):
    rows = seed_rows()
    assert len(rows) == 29 and sum(r["access_method"] != "directory" for r in rows) == 27
    for r in rows:  # point inbox paths at the test dir; feeds are not polled in this test
        if r["access_method"] == "directory":
            r["path"] = f"inbox/{r['key']}"
    app = make_app(tmp_path, None, rows)
    try:
        assert app.db.scalar("SELECT count(*) FROM source") == 29
        for col in FLAG_COLS:
            assert app.db.scalar(f"SELECT count(*) FROM source WHERE {col} IS NULL") == 0, col
        yna = app.sources.source_by_key("yna_intl")
        assert yna.flags.external_ai_allowed is False  # V1-03
    finally:
        app.close()


@pytest.mark.req("FR-01b")
def test_defaults():
    spec = parse_sources({"sources": [{"key": "x", "name": "x", "access_method": "feed", "url": "https://e.com/r"}]})[0]
    f = spec.flags()
    assert (f.storage, f.display, f.ai_processing, f.external_ai_allowed, f.permitted_ops, f.redistribution, f.training) == \
        ("metadata", "headline", "unknown", False, frozenset(), "none", "no")


@pytest.mark.req("FR-01c")
def test_context(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["guardian_world.xml", "bbc_world.xml"])
    sources = [feed_source("guardian_world", urls["guardian_world.xml"], allowed_contexts=["private"]),
               feed_source("bbc_world", urls["bbc_world.xml"])]
    app = make_app(tmp_path, fixture_server, sources, settings={"use_context": "internal"})
    try:
        app.collect(force=True)
        assert fixture_server.requests_for("/feeds/guardian_world.xml") == []
        assert fixture_server.requests_for("/feeds/bbc_world.xml")
        g = [r for r in app.sources.status_rows() if r["key"] == "guardian_world"][0]
        assert not g["active"] and "use_context=internal" in g["inactive_reason"]
    finally:
        app.close()
    seed = parse_sources({"sources": seed_rows()})
    from datetime import date
    inactive = {s.key for s in seed if not s.activation("internal", date(2026, 11, 25))[0]}
    assert P_ONLY <= inactive


def test_adapters_off():
    row = {"key": "cd", "name": "cd", "access_method": "changedetection", "active": True}
    with pytest.raises(AdapterNotImplemented, match="adapter not implemented"):
        from datetime import date
        parse_sources({"sources": [row]})[0].activation("private", date(2026, 11, 25))


def test_training_and_bad_rows_rejected():
    with pytest.raises(ConfigError):
        parse_sources({"sources": [{"key": "x", "name": "x", "access_method": "feed", "url": "https://e/", "training": "yes"}]})
    with pytest.raises(ConfigError, match="duplicate"):
        parse_sources({"sources": [{"key": "x", "name": "x", "access_method": "feed", "url": "https://e/"}] * 2})


@pytest.mark.req("FR-30b")
def test_valid_until_stops_ingestion(tmp_path):
    rows = mock_wire_sources()
    rows[1]["valid_until"] = "2026-12-31"
    clock = FrozenClock("2026-12-30T00:00:00+00:00")
    app = make_app(tmp_path, None, rows, clock=clock, with_inbox=True)
    try:
        assert any(f.source_key == "mock_wire_demo" for f in app.collect(force=True).feeds)
        clock.advance(days=3)
        rep = app.collect(force=True)
        demo = [f for f in rep.feeds if f.source_key == "mock_wire_demo"]
        assert demo and demo[0].status == "skipped" and demo[0].stage == "permission"
        assert not app.sources.source_by_key("mock_wire_demo").active
    finally:
        app.close()
