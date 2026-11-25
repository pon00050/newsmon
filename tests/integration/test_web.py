"""Local web UI (T-42/T-43/T-44 Release A subset): FR-06(c) on HTML, FR-18(d), FR-19(a), FR-31(a)(b), RA-12, AC-O1-03."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from newsmon.web.app import create_app, wait_idle
from tests.support.instance import FEEDS, feed_source, fill_inbox, make_app, mock_wire_sources, serve_feeds

pytestmark = pytest.mark.integration


@pytest.fixture
def ui(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["bbc_world.xml", "yna_nk.xml", "rfi_zh.xml", "aljazeera_all.xml"])
    sources = [feed_source("bbc_world", urls["bbc_world.xml"]), feed_source("yna_nk", urls["yna_nk.xml"], "ko"),
               feed_source("rfi_zh", urls["rfi_zh.xml"], "zh"), feed_source("aljazeera_all", urls["aljazeera_all.xml"])]
    app = make_app(tmp_path, fixture_server, sources + mock_wire_sources(), with_inbox=True)
    fill_inbox(app)
    app.collect(force=True)
    app.collect(force=True)
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    yield app, client
    client.close()
    app.close()


def all_bands(client, **params):
    q = "&".join(f"band={b}" for b in ("flash", "report", "review", "drop"))
    extra = "".join(f"&{k}={v}" for k, v in params.items())
    return client.get(f"/?{q}{extra}")


@pytest.mark.req("FR-18d", "RA-12", "AC-O1-03")
def test_queue_shows_collected_records(ui):
    app, client = ui
    r = all_bands(client)
    assert r.status_code == 200
    html = r.text
    assert "AI: 꺼짐" in html and "AI 처리 대기" not in html
    rows = re.findall(r'<tr data-uid="([^"]+)">', html)
    assert len(rows) == app.articles.counts()["queue_rows"] > 20
    for uid in rows[:50]:
        a = app.articles.get(uid)
        assert a["headline"] in html or a["headline"].replace("'", "&#39;").replace('"', "&#34;") in html
    for row in re.findall(r'<tr data-uid=.*?</tr>', html, re.S):  # every row: headline, band, source, time
        assert 'class="band band-' in row and 'class="headline"' in row and "muted" in row


@pytest.mark.req("FR-06c", "RA-10")
def test_headline_only_summary_never_rendered(ui):
    app, client = ui
    summaries = [r[0] for r in app.db.query(
        "SELECT r.description_text FROM article a JOIN article_revision r ON r.revision_id = a.current_revision_id "
        "JOIN source s ON s.source_id = a.source_id WHERE s.display = 'headline' AND r.description_text IS NOT NULL "
        "AND length(r.description_text) > 40")]
    assert summaries, "control: headline-only sources do have stored feed summaries"
    pages = [all_bands(client).text, client.get("/search?q=North").text, client.get("/search?q=" + "북한").text,
             client.get("/ai").text, client.get("/sources").text]
    pages += [client.get(f"/article/{a['uid']}").text for a in app.articles.queue(limit=40)]
    for s in summaries:
        probe = s[:40]
        assert all(probe not in p for p in pages), probe


@pytest.mark.req("FR-19a", "FR-31a")
def test_item_detail_and_renditions(ui):
    app, client = ui
    video = app.db.one("SELECT uid FROM article WHERE item_type = 'video'")
    html = client.get(f"/article/{video[0]}").text
    assert "a1b2c3d4e5f6--2--0c4d2e7a.mp4" in html and "Mock wire (demo)" in html
    rend = json.loads(app.db.scalar("SELECT r.renditions FROM article a JOIN article_revision r ON "
                                    "r.revision_id = a.current_revision_id WHERE a.uid = ?", (video[0],)))
    assert rend[0]["href"] == "a1b2c3d4e5f6--2--0c4d2e7a.mp4" and rend[0]["duration"] == 72
    for a in app.articles.queue(limit=30):  # every item shows a source name and a link or nothing to link
        page = client.get(f"/article/{a['uid']}").text
        assert a["source_name"] in page


@pytest.mark.req("FR-31b")
def test_unknown_restriction_renders_headline_only(ui):
    app, client = ui
    uid = app.db.scalar("SELECT uid FROM article WHERE restrictions = 'ZZ-UNKNOWN-RESTRICTION'")
    a = app.articles.get(uid)
    page = client.get(f"/article/{uid}").text
    assert a["headline"] in page and "제목만 표시" in page
    assert a["body_text"] and a["body_text"][:40] not in page


def test_html_in_summary_is_inert(ui):
    _, client = ui
    page = all_bands(client).text + client.get("/search?q=Gaza").text
    assert "<script>alert(1)" not in page and "onerror=alert" not in page and 'href="javascript:' not in page


def test_refresh_requires_same_origin(ui):
    _, client = ui
    assert client.post("/refresh").status_code == 403
    assert client.post("/refresh", headers={"Origin": "https://evil.example"}).status_code == 403
    r = client.post("/refresh", headers={"Origin": "http://127.0.0.1:8765"}, follow_redirects=False)
    assert r.status_code == 303
    wait_idle(client.app)


def test_sources_page_and_healthz(ui):
    _, client = ui
    page = client.get("/sources").text
    assert "bbc_world" in page and "mock_wire_gated" in page
    h = client.get("/healthz").json()
    assert h["ok"] and h["ai"] == "AI: 꺼짐" and h["counts"]["articles"] > 0


def test_filters(ui):
    app, client = ui
    ko = all_bands(client, lang="ko").text
    uids = re.findall(r'<tr data-uid="([^"]+)">', ko)
    assert uids and all(app.articles.get(u)["lang"] == "ko" for u in uids)
