"""TS-HAR-01 (T-04): scripted responses are served; the log records UA, conditional headers and timestamps."""
import httpx
import pytest

from tests.support.fixture_server import Resp

pytestmark = pytest.mark.support


def test_scripted_sequence_and_log(fixture_server):
    url = fixture_server.route("/feed.xml", Resp(status=503), Resp(body=b"<rss/>", headers={"ETag": '"v1"'}),
                               Resp(status=304))
    with httpx.Client() as c:
        assert c.get(url, headers={"User-Agent": "ua-test/1"}).status_code == 503
        r = c.get(url)
        assert (r.status_code, r.content, r.headers["etag"]) == (200, b"<rss/>", '"v1"')
        assert c.get(url, headers={"If-None-Match": '"v1"'}).status_code == 304
        assert c.get(url).status_code == 304  # last response repeats
    log = fixture_server.requests_for("/feed.xml")
    assert len(log) == 4
    assert log[0].headers["user-agent"] == "ua-test/1"
    assert log[2].headers["if-none-match"] == '"v1"'
    assert all(r.end >= r.start for r in log)


def test_unknown_path_404_and_redirect(fixture_server):
    target = fixture_server.route("/b", Resp(body=b"ok"))
    src = fixture_server.route("/a", Resp.redirect(target))
    with httpx.Client() as c:
        assert c.get(fixture_server.url("/nope")).status_code == 404
        r = c.get(src)
        assert r.status_code == 302 and r.headers["location"] == target
    assert fixture_server.requests_for("/b") == []  # redirect not followed by the client
