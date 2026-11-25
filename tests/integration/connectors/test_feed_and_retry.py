"""Connector contract, retry policy and the feed connector (T-14, T-15): FR-02(a), FR-03(a)-(d), FR-27(b)(c), TS-SEC-06x."""
from pathlib import Path

import pytest

from newsmon.connectors.base import poll_with_retry
from newsmon.connectors.feed import FeedConnector, FeedParseError, parse_feed_bytes
from newsmon.domain.models import LicenceFlags
from newsmon.fetcher.client import HttpxFetcher
from newsmon.fetcher.ssrf import SsrfPolicy
from tests.support.clock import FrozenClock
from tests.support.fixture_server import Resp
from tests.support.instance import FEEDS, feed_source, make_app, serve_feeds

pytestmark = pytest.mark.integration


def feed_conn(server, url, **kw):
    f = HttpxFetcher(user_agent="t/1", policy=SsrfPolicy(allow_loopback_ports=frozenset({server.port})))
    return FeedConnector(source_key="s", url=url, licence_snapshot=LicenceFlags().snapshot_json(), fetcher=f,
                         robots=None, clock=FrozenClock(), **kw)


@pytest.mark.req("FR-03a")
@pytest.mark.corpus  # globs the private corpus fixtures
def test_30_runs(tmp_path, fixture_server):
    names = sorted(p.name for p in FEEDS.glob("*.xml") if p.name not in ("malformed.xml", "xxe_rss.xml"))[:10]
    urls = serve_feeds(fixture_server, names)
    app = make_app(tmp_path, fixture_server, [feed_source(f"f{i}", urls[n]) for i, n in enumerate(names)])
    try:
        for _ in range(3):
            app.collect(force=True)
        assert app.articles.counts()["fetch_runs"] == 30
    finally:
        app.close()


@pytest.mark.req("FR-03b")
def test_503_503_200(fixture_server):
    url = fixture_server.route("/f", Resp(status=503), Resp(status=503), Resp.file(FEEDS / "bbc_world.xml"))
    results = poll_with_retry(feed_conn(fixture_server, url).poll, sleep=lambda s: None)
    assert [r.attempts for r in results] == [1, 2, 3]
    assert [r.label for r in results] == ["error:http_5xx", "error:http_5xx", "ok"]


@pytest.mark.req("FR-03c")
def test_404_once(fixture_server):
    url = fixture_server.route("/f", Resp(status=404))
    results = poll_with_retry(feed_conn(fixture_server, url).poll, sleep=lambda s: None)
    assert len(results) == 1 and results[0].label == "error:http_4xx"
    assert len(fixture_server.requests_for("/f")) == 1


def test_429_and_timeout_are_retried(fixture_server):
    url = fixture_server.route("/f", Resp(status=429), Resp(status=429), Resp(status=429))
    assert [r.label for r in poll_with_retry(feed_conn(fixture_server, url).poll, sleep=lambda s: None)] == \
        ["error:rate_limited"] * 3


@pytest.mark.req("FR-03d")
def test_malformed(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["malformed.xml"])
    app = make_app(tmp_path, fixture_server, [feed_source("bad", urls["malformed.xml"])])
    try:
        rep = app.collect(force=True)
        assert rep.feeds[0].error_class == "parse" and rep.feeds[0].attempts == 1
        runs = app.sources.recent_runs()
        assert len(runs) == 1 and runs[0]["status"] == "error" and runs[0]["error_class"] == "parse"
    finally:
        app.close()


@pytest.mark.req("FR-02a")
def test_304(tmp_path, fixture_server):
    body = (FEEDS / "bbc_world.xml").read_bytes()
    url = fixture_server.route("/f", Resp(body=body, headers={"ETag": '"v1"', "Last-Modified": "Wed, 25 Nov 2026 00:00:00 GMT"}),
                               Resp(status=304))
    fixture_server.route("/robots.txt", Resp(body=b""))
    app = make_app(tmp_path, fixture_server, [feed_source("bbc_world", url)])
    try:
        first = app.collect(force=True)
        n = app.articles.counts()["articles"]
        second = app.collect(force=True)
        assert first.feeds[0].new > 0 and second.feeds[0].status == "not_modified" and second.feeds[0].new == 0
        assert app.articles.counts()["articles"] == n
        h = fixture_server.requests_for("/f")[1].headers
        assert h["if-none-match"] == '"v1"' and h["if-modified-since"] == "Wed, 25 Nov 2026 00:00:00 GMT"
    finally:
        app.close()


@pytest.mark.req("FR-27b")
def test_provenance(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["bbc_world.xml"])
    app = make_app(tmp_path, fixture_server, [feed_source("bbc_world", urls["bbc_world.xml"])])
    try:
        app.collect(force=True)
        rows = app.db.query("SELECT a.licence_snapshot, r.raw_sha256, r.parser FROM article a JOIN article_revision r "
                            "ON r.revision_id = a.current_revision_id")
        assert rows and all(r[0] and r[1] and r[2] for r in rows)
    finally:
        app.close()


@pytest.mark.req("FR-27c", "RA-11")
def test_fault_injection_never_raises(fixture_server):
    class Exploding:
        def get(self, *a, **k):
            raise ConnectionResetError("reset by peer")
    c = FeedConnector(source_key="s", url="http://x.invalid/", licence_snapshot="{}", fetcher=Exploding(), robots=None,
                      clock=FrozenClock())
    results = poll_with_retry(c.poll, sleep=lambda s: None)
    assert results[-1].label == "error:io" and "ConnectionResetError" in results[-1].error_detail


@pytest.mark.netguard_expected
def test_dns_failure_is_an_error_status(fixture_server, netguard):
    r = feed_conn(fixture_server, "http://no-such-host.invalid/rss").poll()
    assert r.label == "error:io"
    netguard.take()


def test_rss_external_entity_refused(monkeypatch):
    data = (FEEDS / "xxe_rss.xml").read_bytes()
    opened = []
    import builtins
    real = builtins.open
    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (opened.append(str(f)), real(f, *a, **k))[1])
    with pytest.raises(FeedParseError, match="entity"):
        parse_feed_bytes(data)
    assert not any("win.ini" in f for f in opened)


def test_parse_maps_entries():
    c = FeedConnector(source_key="bbc_world", url="u", licence_snapshot="{}", fetcher=None, robots=None, clock=FrozenClock())
    from newsmon.connectors.base import raw_unit
    items = c.parse(raw_unit("u", (FEEDS / "bbc_world.xml").read_bytes(), FrozenClock().now()))
    assert len(items) == 5 and all(i.raw_sha256 and i.parser.startswith("feedparser") for i in items)
    assert any(i.url and "?at_medium" in i.url for i in items)  # canonicalisation happens in normalise, not here
