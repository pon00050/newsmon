"""Exact dedup, near-dups, revisions, kills and independence through the real pipeline (T-19, T-20, T-21 subset):
FR-07(a)(b)(c), FR-08(b)(c)(d)(e), FR-09(a), FR-27(a), NFR-05."""
import pytest

from tests.support.clock import FrozenClock
from tests.support.fixture_server import Resp
from tests.support.instance import FEEDS, feed_source, fill_inbox, make_app, mock_wire_sources, serve_feeds

pytestmark = pytest.mark.integration


def two_cycles(app):
    app.collect(force=True)
    app.collect(force=True)


@pytest.mark.req("FR-07a")
def test_same_url_two_feeds_one_source(tmp_path, fixture_server):
    body = (FEEDS / "bbc_world.xml").read_bytes()
    a = fixture_server.route("/world.xml", Resp(body=body))
    b = fixture_server.route("/top.xml", Resp(body=body))
    fixture_server.route("/robots.txt", Resp(body=b""))
    app = make_app(tmp_path, fixture_server, [feed_source("bbc_world", a)])
    try:
        app.collect(force=True)
        n_articles = app.articles.counts()["articles"]
        # a second feed of the same source carrying the same URLs, with different GUIDs
        sid = app.sources.source_by_key("bbc_world").source_id
        app.db.execute("INSERT INTO feed (workspace_id, source_id, kind, url_or_path, discovered_from, poll_seconds) "
                       "VALUES (1, ?, 'rss', ?, 'test', 600)", (sid, b))
        fixture_server.route("/top.xml", Resp(body=body.replace(b"<guid", b"<guid_x").replace(b"</guid>", b"</guid_x>")))
        app.collect(force=True)
        assert app.articles.counts()["articles"] == n_articles
        art = app.db.scalar("SELECT article_id FROM article WHERE canonical_url = 'https://www.bbc.com/news/articles/abc123'")
        assert app.db.scalar("SELECT count(*) FROM feed_entry WHERE article_id = ?", (art,)) == 2
    finally:
        app.close()


@pytest.mark.req("FR-07b", "NFR-05", "RA-07")
def test_idempotent(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["yna_nk.xml", "rfi_zh.xml", "gdelt_huawei_syndication.xml"])
    app = make_app(tmp_path, fixture_server, [feed_source("yna_nk", urls["yna_nk.xml"], "ko"),
                                              feed_source("rfi_zh", urls["rfi_zh.xml"], "zh"),
                                              feed_source("gdelt", urls["gdelt_huawei_syndication.xml"])] +
                   mock_wire_sources(), with_inbox=True)
    try:
        fill_inbox(app)
        two_cycles(app)
        before = {k: v for k, v in app.articles.counts().items() if k not in ("fetch_runs",)}
        two_cycles(app)
        after = {k: v for k, v in app.articles.counts().items() if k not in ("fetch_runs",)}
        assert before == after and before["articles"] > 0
    finally:
        app.close()


@pytest.mark.req("FR-07c")
def test_identical_content_two_urls(tmp_path, fixture_server):
    feed = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>'
            b'<item><title>Same story text</title><link>https://a.example.com/1</link><description>Body</description></item>'
            b'<item><title>Same story text</title><link>https://a.example.com/2</link><description>Body</description></item>'
            b'</channel></rss>')
    url = fixture_server.route("/f", Resp(body=feed))
    fixture_server.route("/robots.txt", Resp(body=b""))
    app = make_app(tmp_path, fixture_server, [feed_source("s", url)])
    try:
        app.collect(force=True)
        assert app.articles.counts()["articles"] == 2
        assert app.db.scalar("SELECT kind FROM near_dup_link") == "same_item"
        assert app.articles.counts()["queue_rows"] == 1  # the queue shows one row with a duplicate count
    finally:
        app.close()


@pytest.mark.req("FR-08b")
def test_yonhap_jonghap_revision(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["yna_nk.xml"])
    app = make_app(tmp_path, fixture_server, [feed_source("yna_nk", urls["yna_nk.xml"], "ko",
                                                          story_key_rule=r"\s*\((종합|[0-9]+보)\)\s*$")])
    try:
        app.collect(force=True)
        ids = {r[0] for r in app.db.query(
            "SELECT article_id FROM article WHERE source_uri IN "
            "('https://www.yna.co.kr/view/AKR20261125990000504', 'https://www.yna.co.kr/view/AKR20261125990051504')")}
        assert len(ids) == 2
        links = app.db.query("SELECT a.article_id, b.article_id, l.kind FROM near_dup_link l JOIN article_revision a ON "
                             "a.revision_id = l.a_revision_id JOIN article_revision b ON b.revision_id = l.b_revision_id")
        assert [k for x, y, k in links if {x, y} == ids] == ["revision"]
    finally:
        app.close()


@pytest.mark.req("FR-08c")
def test_guardian_liveblogs_not_linked(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["guardian_world.xml"])
    app = make_app(tmp_path, fixture_server, [feed_source("guardian_world", urls["guardian_world.xml"],
                                                          live_patterns=[r"(?i)\blive\b\s*:"])])
    try:
        app.collect(force=True)
        live = app.db.query("SELECT article_id FROM article WHERE is_live = 1")
        assert len(live) >= 2
        ids = tuple(r[0] for r in live)
        linked = app.db.scalar(
            "SELECT count(*) FROM near_dup_link l JOIN article_revision a ON a.revision_id = l.a_revision_id "
            "JOIN article_revision b ON b.revision_id = l.b_revision_id WHERE a.article_id IN (SELECT value FROM json_each(?)) "
            "OR b.article_id IN (SELECT value FROM json_each(?))", (str(list(ids)), str(list(ids))))
        assert linked == 0
    finally:
        app.close()


@pytest.mark.req("FR-08d", "FR-08e")
def test_wire_version_and_kill(tmp_path):
    app = make_app(tmp_path, None, mock_wire_sources(), with_inbox=True)
    try:
        fill_inbox(app)
        two_cycles(app)
        floods = app.db.one("SELECT article_id, status FROM article WHERE source_uri = 'urn:newsml:synthetic.example:20261124:gx-0001'")
        revs = app.db.query("SELECT version, change_kind FROM article_revision WHERE article_id = ? ORDER BY version", (floods[0],))
        assert [(r[0], r[1]) for r in revs] == [(1, "initial"), (2, "update")]
        killed = app.db.one("SELECT uid, status FROM article WHERE source_uri LIKE '%gx-0003'")
        assert killed["status"] == "killed"
        assert killed["uid"] not in {r["uid"] for r in app.articles.queue(limit=1000, include_dups=True)}
    finally:
        app.close()


def test_independent_sources_fold_subdomains(tmp_path, fixture_server):
    """Release A subset of FR-09: 10 iHeart subdomain copies count as ONE registrable domain inside their duplicate
    group. The full FR-09(a) count (3) needs event grouping to place the differently-worded FMT item in the same event:
    deferred with T-27 (P-011), so this test does not claim FR-09a."""
    urls = serve_feeds(fixture_server, ["gdelt_huawei_syndication.xml"])
    app = make_app(tmp_path, fixture_server, [feed_source("gdelt", urls["gdelt_huawei_syndication.xml"])])
    try:
        app.collect(force=True)
        inputs = app.articles.ranking_inputs()
        big = max({r["dup_of"] or r["article_id"] for r in inputs},
                  key=lambda g: sum(1 for r in inputs if (r["dup_of"] or r["article_id"]) == g))
        members = [r for r in inputs if (r["dup_of"] or r["article_id"]) == big]
        assert len(members) == 11  # 10 iHeart copies + AP's near-identical lead
        assert {r["reg_domain"] for r in members} == {"iheart.com", "apnews.com"}
        assert members[0]["independent_sources"] == 2
    finally:
        app.close()


@pytest.mark.req("FR-27a")
def test_rss_and_plain_wire_same_story_linked(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["bbc_world.xml"])
    app = make_app(tmp_path, fixture_server, [feed_source("bbc_world", urls["bbc_world.xml"])] + mock_wire_sources(),
                   with_inbox=True)
    try:
        fill_inbox(app)
        two_cycles(app)
        rss = app.db.one("SELECT article_id FROM article WHERE canonical_url = 'https://news.example.com/world/un-sudan-session'")
        wire = app.db.one("SELECT article_id, dup_of FROM article WHERE source_uri = 'PTW-20261124-0004'")
        assert rss and wire and wire["dup_of"] == rss[0]
    finally:
        app.close()


def test_restart_reloads_dedup_index(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["gdelt_huawei_syndication.xml"])
    src = [feed_source("gdelt", urls["gdelt_huawei_syndication.xml"])]
    app = make_app(tmp_path, fixture_server, src)
    app.collect(force=True)
    app.close()
    app2 = make_app(tmp_path, fixture_server, src)
    try:
        assert app2.articles.load_index() > 0
    finally:
        app2.close()
