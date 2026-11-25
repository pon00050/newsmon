"""HttpFetcher and robots against the loopback fixture server (T-11, T-12):
FR-02(a)(b)(c)(d)(e), NFR-06, TS-SEC-09, TS-FET-01."""
import threading
import time

import pytest

from newsmon.fetcher.client import HttpxFetcher
from newsmon.fetcher.robots import RobotsCache
from newsmon.fetcher.ssrf import SsrfPolicy
from tests.support.clock import FrozenClock
from tests.support.fixture_server import FixtureServer, Resp

pytestmark = pytest.mark.integration
UA = "newsmon-test/1.0 (+contact: test@example.invalid)"


def fetcher(server, **kw):
    return HttpxFetcher(user_agent=UA, policy=SsrfPolicy(allow_loopback_ports=frozenset({server.port})), **kw)


@pytest.mark.req("FR-02c", "NFR-03")
def test_every_request_carries_the_ua(fixture_server):
    f = fetcher(fixture_server)
    fixture_server.route("/robots.txt", Resp(body=b"User-agent: *\nAllow: /\n"))
    url = fixture_server.route("/a", Resp(body=b"x"))
    RobotsCache(f, UA).allowed(url)
    f.get(url)
    f.get(url)
    assert fixture_server.log and all(r.headers["user-agent"] == UA for r in fixture_server.log)


@pytest.mark.req("FR-02d", "NFR-06")
def test_ssrf_blocked_targets(fixture_server):
    sentinel = FixtureServer().start()  # a listener on a port the policy does NOT allow
    try:
        sentinel.route("/x", Resp(body=b"secret"))
        f = fetcher(fixture_server)
        for url in ("http://127.0.0.1:%d/x" % sentinel.port, "http://10.0.0.5/x", "http://169.254.169.254/latest/meta-data/"):
            r = f.get(url)
            assert r.error_class == "ssrf_blocked", url
        # an allowed host that redirects to a private address is blocked at the redirect hop
        hop = fixture_server.route("/hop", Resp.redirect(f"http://127.0.0.1:{sentinel.port}/x"))
        r = f.get(hop)
        assert r.error_class == "ssrf_blocked"
        assert sentinel.log == []  # the private listener never saw a connection
    finally:
        sentinel.stop()


@pytest.mark.parametrize("url", ["http://[::1]/", "http://[fc00::1]/", "http://[::ffff:127.0.0.1]/", "http://0.0.0.0/",
                                 "http://2130706433/", "http://0x7f.1/", "http://localhost/", "file:///C:/Windows/win.ini",
                                 "gopher://127.0.0.1/", "http://100.64.0.1/", "http://224.0.0.1/"])
def test_ssrf_extended(url, fixture_server):
    r = fetcher(fixture_server).get(url)
    assert r.error_class in ("ssrf_blocked", "io"), (url, r)
    assert r.status is None


def test_production_policy_refuses_loopback():
    assert SsrfPolicy() == SsrfPolicy(allow_loopback_ports=frozenset())
    with pytest.raises(Exception):
        SsrfPolicy().check_ip("127.0.0.1", 80)


@pytest.mark.req("FR-02e", "NFR-03")
def test_one_request_per_host(fixture_server):
    a = fixture_server.route("/feed-a", Resp(body=b"a", delay=0.3))
    b = fixture_server.route("/feed-b", Resp(body=b"b", delay=0.3))
    f = fetcher(fixture_server)
    ts = [threading.Thread(target=f.get, args=(u,)) for u in (a, b)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    ra, rb = fixture_server.requests_for("/feed-a")[0], fixture_server.requests_for("/feed-b")[0]
    assert ra.end <= rb.start or rb.end <= ra.start, "two requests to one host overlapped"


@pytest.mark.req("NFR-06")
def test_size_and_time_caps(fixture_server):
    big = fixture_server.route("/big", Resp(body=b"x" * (11 * 1024 * 1024)))
    r = fetcher(fixture_server).get(big)
    assert r.error_class == "io" and r.error_detail == "oversize"
    slow = fixture_server.route("/slow", Resp(body=b"x", delay=2.0))
    t0 = time.monotonic()
    r = fetcher(fixture_server, timeout=0.5).get(slow)
    assert r.error_class == "timeout" and time.monotonic() - t0 < 1.8


@pytest.mark.req("FR-02a")
def test_conditional_get(fixture_server):
    url = fixture_server.route("/c", Resp(status=304))
    fetcher(fixture_server).get(url, etag='"abc"', last_modified="Wed, 25 Nov 2026 00:00:00 GMT")
    h = fixture_server.requests_for("/c")[0].headers
    assert h["if-none-match"] == '"abc"' and h["if-modified-since"] == "Wed, 25 Nov 2026 00:00:00 GMT"


@pytest.mark.req("FR-02b")
def test_robots_disallowed_path_never_requested(fixture_server):
    fixture_server.route("/robots.txt", Resp(body=b"User-agent: *\nDisallow: /r?\n", content_type="text/plain"))
    blocked = fixture_server.url("/r?id=1")
    allowed = fixture_server.route("/rss", Resp(body=b"<rss/>"))
    rc = RobotsCache(fetcher(fixture_server), UA)
    assert rc.allowed(blocked)[0] is False
    assert rc.allowed(allowed)[0] is True
    assert len(fixture_server.requests_for("/robots.txt")) == 1  # cached per host


def test_robots_5xx_disallows_and_cache_expires(fixture_server):
    fixture_server.route("/robots.txt", Resp(status=503), Resp(body=b"User-agent: *\nAllow: /\n"))
    clock = FrozenClock()
    rc = RobotsCache(fetcher(fixture_server), UA, clock=clock)
    assert rc.allowed(fixture_server.url("/x"))[0] is False
    clock.advance(hours=25)
    assert rc.allowed(fixture_server.url("/x"))[0] is True
