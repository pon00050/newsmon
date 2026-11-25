"""Release A acceptance (P-011): RA-01, RA-04, RA-06, RA-08, RA-10, RA-11, RA-14, RA-15 end to end.

RA-02/03 are proven by tests/e2e/test_smoke_o1.py, RA-05/07/09/12 by the component suites (see their req markers),
and RA-13 (regression gate + architecture tests green) by the gate command itself, run by tools/progress.py.
"""
import random
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from newsmon.cli import main
from tests.support.clock import FrozenClock
from tests.support.fixture_server import Resp
from tests.support.instance import (
    FEEDS, ROOT, feed_source, fill_inbox, make_app, mock_wire_sources, serve_feeds, write_config,
)

pytestmark = pytest.mark.e2e
GOOD = ["bbc_world.xml", "guardian_world.xml", "aljazeera_all.xml", "france24_en.xml", "cna_sg_all.xml",
        "yna_news.xml", "yna_nk.xml", "donga_intl.xml", "khan_total.xml", "rfi_zh.xml", "voa_zh.xml", "cna_tw_intl.xml"]


def sources_for(urls):
    lang = {"yna": "ko", "don": "ko", "kha": "ko", "rfi": "zh", "voa": "zh", "cna_tw": "zh"}
    out = []
    for name, url in urls.items():
        key = name.removesuffix(".xml")
        code = next((v for k, v in lang.items() if key.startswith(k)), "en")
        out.append(feed_source(key, url, code))
    return out


@pytest.mark.req("RA-01")
def test_installed_console_script():
    exe = Path(sys.executable).parent / ("newsmon.exe" if sys.platform == "win32" else "newsmon")
    out = subprocess.run([str(exe), "--version"], capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.startswith("newsmon ")


@pytest.mark.req("RA-04")
def test_rss_feeds_collected(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, GOOD)
    app = make_app(tmp_path, fixture_server, sources_for(urls))
    try:
        rep = app.collect(force=True)
        assert len(rep.feeds) == len(GOOD) and not rep.failed
        per_source = dict(app.db.query("SELECT s.key, count(*) FROM article a JOIN source s USING (source_id) GROUP BY 1"))
        assert set(per_source) == {n.removesuffix(".xml") for n in GOOD}
        assert {r[0] for r in app.db.query("SELECT DISTINCT lang FROM article")} >= {"en", "ko", "zh"}
        # FR-06(a): metadata-only sources: only the feed URLs and robots.txt were requested, never article pages
        assert {r.path for r in fixture_server.log} <= {f"/feeds/{n}" for n in GOOD} | {"/robots.txt"}
    finally:
        app.close()


@pytest.mark.req("RA-06", "NFR-04")
def test_records_persist_across_restart(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, GOOD[:4])
    src = sources_for(urls) + mock_wire_sources()
    app = make_app(tmp_path, fixture_server, src, with_inbox=True)
    fill_inbox(app)
    app.collect(force=True)
    app.collect(force=True)
    before = app.articles.counts()
    queue = [(r["uid"], r["final_band"]) for r in app.articles.queue(limit=1000)]
    app.close()
    app2 = make_app(tmp_path, fixture_server, src, with_inbox=True)  # same data dir: a restart
    try:
        assert app2.db.integrity_ok()
        assert {k: v for k, v in app2.articles.counts().items()} == before
        assert [(r["uid"], r["final_band"]) for r in app2.articles.queue(limit=1000)] == queue
        rep = app2.collect(force=True)
        assert rep.new_articles == 0  # nothing re-ingested after the restart
        assert app2.articles.counts()["articles"] == before["articles"]
    finally:
        app2.close()


@pytest.mark.req("RA-08", "FR-16a")
def test_profile_edit_changes_queue_without_restart(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["france24_en.xml", "aljazeera_all.xml"])
    app = make_app(tmp_path, fixture_server, sources_for(urls))
    try:
        app.collect(force=True)
        target = app.db.one("SELECT a.uid, r.headline FROM article a JOIN article_revision r ON "
                            "r.revision_id = a.current_revision_id WHERE a.final_band = 'drop' LIMIT 1")
        assert target, "control: some item is unranked under the default profile"
        uid, headline = target
        word = max(headline.split(), key=len).strip(".,:;'\"")
        visible = ["flash", "report", "review"]
        assert uid not in {r["uid"] for r in app.articles.queue(bands=visible)}  # not in the default (non-drop) queue
        prof_path = app.config_path("profiles") / "foreign_desk.yaml"
        prof = yaml.safe_load(prof_path.read_text(encoding="utf-8"))
        prof["topics"].append({"label": "test", "keywords": {"en": [word]}, "weight": 2.0})
        prof_path.write_text(yaml.safe_dump(prof, allow_unicode=True), encoding="utf-8")
        app.collect()  # next evaluation: profiles reload, no restart, no code change
        queue = app.articles.queue(bands=visible)
        row = [r for r in queue if r["uid"] == uid]
        assert row and row[0]["final_band"] in ("review", "report")
        assert any(h["rule_id"] == "topic:test" for h in app.articles.rule_hits(app.articles.get(uid)["article_id"]))
        assert app.db.scalar("SELECT max(version) FROM profile WHERE key = 'foreign_desk'") == 2  # versioned
    finally:
        app.close()


@pytest.mark.req("RA-10", "FR-06a", "FR-06b")
def test_storage_restrictions_enforced(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["bbc_world.xml"])
    rows = [feed_source("bbc_world", urls["bbc_world.xml"])] + mock_wire_sources()
    rows[2]["storage"] = "transient"  # mock_wire_demo: body may be used, never kept
    app = make_app(tmp_path, fixture_server, rows, with_inbox=True)
    try:
        fill_inbox(app, "mock_wire_demo")
        fill_inbox(app, "mock_wire_gated")
        app.collect(force=True)
        app.collect(force=True)
        body = lambda key: app.db.scalar(  # noqa: E731
            "SELECT count(*) FROM article a JOIN source s USING (source_id) JOIN article_revision r ON "
            "r.article_id = a.article_id WHERE s.key = ? AND r.body_text IS NOT NULL", (key,))
        assert body("bbc_world") == 0          # metadata: no body
        assert body("mock_wire_demo") == 0     # transient: discarded
        assert body("mock_wire_gated") > 0     # full: kept
        demo = app.db.scalar("SELECT count(*) FROM article a JOIN source s USING (source_id) WHERE s.key = 'mock_wire_demo'")
        assert demo > 0
    finally:
        app.close()


@pytest.mark.req("RA-11", "FR-27c")
def test_failed_sources_do_not_halt_collection(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["bbc_world.xml", "yna_nk.xml", "malformed.xml", "xxe_rss.xml", "empty.xml"])
    fixture_server.route("/down.xml", Resp(status=500))
    fixture_server.route("/gone.xml", Resp(status=404))
    sources = [feed_source("bbc_world", urls["bbc_world.xml"]), feed_source("yna_nk", urls["yna_nk.xml"], "ko"),
               feed_source("broken", urls["malformed.xml"]), feed_source("xxe", urls["xxe_rss.xml"]),
               feed_source("empty", urls["empty.xml"]), feed_source("down", fixture_server.url("/down.xml")),
               feed_source("gone", fixture_server.url("/gone.xml")),
               feed_source("internal", "http://10.0.0.5/rss.xml")] + mock_wire_sources()
    app = make_app(tmp_path, fixture_server, sources, with_inbox=True)
    try:
        rep = app.collect(force=True)
        by = {f.source_key: f for f in rep.feeds}
        assert by["bbc_world"].new > 0 and by["yna_nk"].new > 0
        assert (by["broken"].error_class, by["broken"].stage) == ("parse", "parse")
        assert by["xxe"].error_class == "parse"
        assert by["empty"].status == "empty"
        assert by["down"].error_class == "http_5xx" and by["down"].attempts == 3
        assert by["gone"].error_class == "http_4xx" and by["gone"].attempts == 1
        assert by["internal"].error_class == "ssrf_blocked"
        status = {r["key"]: r for r in app.sources.status_rows()}
        assert status["down"]["error_streak"] == 3 and status["bbc_world"]["error_streak"] == 0
    finally:
        app.close()


@pytest.mark.req("RA-14", "IR-06")
def test_documented_commands(tmp_path, monkeypatch, capsys):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for cmd in ("newsmon init", "newsmon collect", "newsmon serve", "newsmon status", "newsmon search", "newsmon rerank",
                "NEWSMON_CONFIG_DIR", "NEWSMON_DATA_DIR"):
        assert cmd in readme, cmd
    cfg = write_config(tmp_path / "cfg", mock_wire_sources())
    for k in ("mock_wire_gated", "mock_wire_demo"):
        (cfg / "inbox" / k).mkdir(parents=True)
    monkeypatch.setenv("NEWSMON_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("NEWSMON_DATA_DIR", str(tmp_path / "data"))
    from tests.support.wire_recipes import copy_inbox
    copy_inbox(cfg / "inbox" / "mock_wire_demo")
    for argv in (["init"], ["collect"], ["collect", "--force"], ["status"], ["search", "Sudan"], ["rerank"]):
        assert main(argv) == 0, argv
    out = capsys.readouterr().out
    assert "UN Security Council" in out  # the search found the plain-text wire item
    with pytest.raises(SystemExit) as e:
        main(["serve", "--help"])
    assert e.value.code == 0


@pytest.mark.req("RA-15", "NFR-05")
def test_repeated_collection_reliability(tmp_path, fixture_server):
    """30 cycles over 6 feeds whose content changes between cycles, with transient 503s, inbox drops and a restart in
    the middle: every cycle completes, no duplicates appear, the database stays intact."""
    rnd = random.Random(7)
    pools = {}
    import feedparser
    for name in GOOD[:6]:
        d = feedparser.parse((FEEDS / name).read_bytes())
        pools[name] = [(e.get("title", ""), e.get("link", ""), e.get("id", e.get("link", ""))) for e in d.entries
                       if e.get("title") and e.get("link")]

    def feed_xml(name, k):
        items = pools[name][: max(1, k)]
        body = "".join(f"<item><title>{t.replace('&', '&amp;').replace('<', '&lt;')}</title><link>{l.replace('&', '&amp;')}</link>"
                       f"<guid>{g.replace('&', '&amp;')}</guid></item>" for t, l, g in items)
        return f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>{name}</title>{body}</channel></rss>'.encode()

    fixture_server.route("/robots.txt", Resp(body=b""))
    urls = {n: fixture_server.url(f"/r/{n}") for n in GOOD[:6]}
    clock = FrozenClock()
    src = sources_for(urls) + mock_wire_sources()
    app = make_app(tmp_path, fixture_server, src, clock=clock, with_inbox=True)
    inbox_files = sorted(p for p in (ROOT / "tests" / "fixtures" / "wire" / "inbox").rglob("*") if p.is_file())
    try:
        for cycle in range(30):
            k = 2 + cycle // 3  # feeds grow over time: new items appear
            for n in GOOD[:6]:
                responses = [Resp(status=503)] if rnd.random() < 0.2 else []
                fixture_server.route(f"/r/{n}", *responses, Resp(body=feed_xml(n, k)))
            if cycle % 5 == 0 and inbox_files:  # customer files keep arriving
                root = app.resolve_inbox("inbox/mock_wire_demo")
                for p in inbox_files[:4]:
                    dst = root / p.relative_to(ROOT / "tests" / "fixtures" / "wire" / "inbox")
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(p.read_bytes())
                inbox_files = inbox_files[4:]
            if cycle == 15:  # restart in the middle of the run
                app.close()
                app = make_app(tmp_path, fixture_server, src, clock=clock, with_inbox=True)
            clock.advance(seconds=601)
            rep = app.collect()
            assert rep.rank_error is None
            assert all(f.status in ("ok", "empty", "not_modified") for f in rep.feeds
                       if f.source_key.startswith("mock")), rep.feeds
        assert app.db.integrity_ok()
        dup_urls = app.db.scalar("SELECT count(*) FROM (SELECT source_id, canonical_url FROM article "
                                 "WHERE canonical_url IS NOT NULL GROUP BY 1, 2 HAVING count(*) > 1)")
        assert dup_urls == 0
        feed_articles = app.db.scalar("SELECT count(*) FROM article a JOIN source s USING (source_id) "
                                      "WHERE s.access_method = 'feed'")
        assert feed_articles == sum(min(len(v), 2 + 29 // 3) for v in pools.values())  # every item exactly once
        wire = app.db.scalar("SELECT count(DISTINCT source_uri) FROM article a JOIN source s USING (source_id) "
                             "WHERE s.key = 'mock_wire_demo'")
        assert wire >= 15
        runs = app.db.scalar("SELECT count(*) FROM fetch_run")
        assert runs >= 30 * 6
    finally:
        app.close()
