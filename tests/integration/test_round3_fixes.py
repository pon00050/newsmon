"""Regression tests for the Round 3 review (2026-11-25): restrictions, withheld and embargoed items, withdrawn copies,
malformed inbox files, feed entries without id or link, AI routing of restricted items, and stale AI assessments."""
import json
import os
import subprocess
import sys

import pytest
import yaml
from fastapi.testclient import TestClient

from newsmon.connectors.feed import FeedParseError, parse_feed_bytes
from newsmon.connectors.wire import WireParseError, parse_wire
from newsmon.licence.policy import _shares_20_chars
from newsmon.web.app import create_app
from tests.support.ai_stub import AIStub
from tests.support.fixture_server import Resp
from tests.support.instance import feed_source, make_app, mock_wire_sources, write_config
from tests.support.wire_recipes import INBOX_DIR

pytestmark = pytest.mark.integration
AI_ON = {"use_context": "private", "ai": {"capabilities": {"enrich": True},
                                           "selection": {"min_band": "drop", "max_items_per_cycle": 100}}}
GATED, DEMO = "inbox/mock_wire_gated", "inbox/mock_wire_demo"  # gated: display=full, no AI; demo: AI permitted
BODY = "The full licensed body text of this synthetic item."


def plain(uid, version, headline="Talks resume in Geneva", body=BODY, restrictions=None, pubstatus="usable"):
    extra = f"RESTRICTIONS: {restrictions}\n" if restrictions else ""
    return (f"SYNTHETIC: true\nID: {uid}\nVERSION: {version}\nVERSIONCREATED: 2026-11-24T10:0{version}:00+00:00\n"
            f"LANGUAGE: en\nURGENCY: 4\nSLUG: X\nHEADLINE: {headline}\nDATELINE: Geneva\nPUBSTATUS: {pubstatus}\n{extra}"
            f"BODY:\n{body}\n").encode()


def ninjs(uid, **extra):
    return json.dumps({"uri": uid, "version": 1, "versioncreated": "2026-11-24T10:00:00Z", "language": "en",
                       "headline": "Ministers agree a water-sharing plan", "body_text": BODY, **extra}).encode()


def wire_app(tmp_path, ai=False):
    app = make_app(tmp_path, None, mock_wire_sources(), settings=AI_ON if ai else None, with_inbox=True)
    stub = AIStub()
    if ai:
        app.use_ai_provider(stub)
    return app, stub


def drop(app, inbox, name, data):
    (app.resolve_inbox(inbox) / name).write_bytes(data)
    app.collect(force=True)  # the watcher ingests a file once it is unchanged across two scans
    return app.collect(force=True)


def row(app, uri):
    return app.db.one("SELECT uid, status, restrictions, dup_of, enrichment_status FROM article WHERE source_uri = ?", (uri,))


def page(app, uid):
    with TestClient(create_app(app), base_url="http://127.0.0.1:8765") as client:
        return client.get(f"/article/{uid}").text


@pytest.mark.req("FR-31b")
def test_same_text_version_adding_a_restriction_caps_display(tmp_path):
    app, _ = wire_app(tmp_path)
    try:
        drop(app, GATED, "v1.txt", plain("S-1", 1))
        assert BODY in page(app, row(app, "S-1")["uid"])
        drop(app, GATED, "v2.txt", plain("S-1", 2, restrictions="NO ARCHIVE"))  # the text is unchanged
        assert row(app, "S-1")["restrictions"] == "NO ARCHIVE"
        assert BODY not in page(app, row(app, "S-1")["uid"])
    finally:
        app.close()


@pytest.mark.req("FR-31b")
def test_late_older_version_carrying_a_restriction_is_kept(tmp_path):
    app, _ = wire_app(tmp_path)
    try:
        drop(app, GATED, "v2.txt", plain("L-1", 2, body="Second version of the body text, unrestricted."))
        drop(app, GATED, "v1.txt", plain("L-1", 1, restrictions="EMBARGO UNTIL 12:00"))  # arrives out of order
        assert row(app, "L-1")["restrictions"] == "EMBARGO UNTIL 12:00"
        assert "Second version of the body text" not in page(app, row(app, "L-1")["uid"])
    finally:
        app.close()


@pytest.mark.req("FR-31b", "FR-15d")
def test_withheld_item_is_headline_only_and_never_sent(tmp_path):
    app, stub = wire_app(tmp_path, ai=True)
    try:
        drop(app, GATED, "w.txt", plain("W-1", 1, pubstatus="withheld"))
        drop(app, DEMO, "w.txt", plain("W-2", 1, headline="A different withheld item", body="Other body text entirely.",
                                       pubstatus="withheld"))
        assert row(app, "W-1")["restrictions"] == "pubstatus: withheld"
        assert BODY not in page(app, row(app, "W-1")["uid"])
        assert stub.calls == [] and row(app, "W-2")["enrichment_status"] == "not_allowed"
    finally:
        app.close()


@pytest.mark.req("FR-31b", "FR-15d")
def test_embargoed_item_is_restricted_until_release(tmp_path):
    app, stub = wire_app(tmp_path, ai=True)
    try:
        drop(app, DEMO, "e.json", ninjs("E-1", embargoed="2099-01-01T00:00:00Z"))
        drop(app, DEMO, "p.json", ninjs("E-2", embargoed="2001-01-01T00:00:00Z", headline="An embargo that has passed",
                                        body_text="A body that was released long ago."))
        assert row(app, "E-1")["restrictions"] == "embargoed until 2099-01-01T00:00:00Z"
        assert row(app, "E-2")["restrictions"] is None
        assert [c for c in stub.calls if "water-sharing" in c.user] == []
        assert any("An embargo that has passed" in c.user for c in stub.calls)  # the control: unrestricted items are sent
    finally:
        app.close()


def test_embargo_is_read_from_newsml_g2_and_nitf():
    g2 = next(p.read_bytes() for p in sorted(INBOX_DIR.rglob("*.xml")) if b"</itemMeta>" in p.read_bytes())
    assert parse_wire(g2)[1][0]["embargoed"] is None
    with_embargo = g2.replace(b"</itemMeta>", b"<embargoed>2099-01-01T09:00:00+09:00</embargoed></itemMeta>", 1)
    assert parse_wire(with_embargo)[1][0]["embargoed"] == "2099-01-01T00:00:00Z"
    nitf = next(p.read_bytes() for p in sorted(INBOX_DIR.rglob("*.xml")) if b"<docdata" in p.read_bytes())
    marked = nitf.replace(b"</docdata>", b'<date.release norm="20990101T000000Z"/></docdata>', 1)
    assert marked != nitf and parse_wire(marked)[1][0]["embargoed"] == "2099-01-01T00:00:00Z"


@pytest.mark.req("FR-08d")
def test_copy_arriving_after_a_withdrawal_stays_visible(tmp_path):
    app, _ = wire_app(tmp_path)
    try:
        drop(app, GATED, "a1.txt", plain("K-1", 1))
        drop(app, GATED, "a2.txt", plain("K-1", 2, pubstatus="canceled"))
        assert row(app, "K-1")["status"] == "killed"
        drop(app, GATED, "b1.txt", plain("K-2", 1))  # the same text under another id, still live
        live = row(app, "K-2")
        assert live["status"] != "killed" and live["dup_of"] is None
        with TestClient(create_app(app), base_url="http://127.0.0.1:8765") as client:
            assert "Talks resume in Geneva" in client.get("/").text
    finally:
        app.close()


@pytest.mark.req("FR-29d")
def test_malformed_file_is_quarantined_without_stopping_the_inbox(tmp_path):
    app, _ = wire_app(tmp_path)
    try:
        root = app.resolve_inbox(GATED)
        (root / "a_bad.json").write_bytes(ninjs("B-1", headline={"text": "SECRET-SOURCE-TEXT"}))
        (root / "b_good.txt").write_bytes(plain("B-2", 1))
        app.collect(force=True)
        rep = app.collect(force=True)
        assert not rep.failed and row(app, "B-2") is not None and row(app, "B-1") is None
        reasons = [r["reason"] for r in app.sources.recent_quarantine()]
        assert any(r.startswith("parse: malformed ninjs") for r in reasons)
        assert not any("SECRET-SOURCE-TEXT" in r for r in reasons)
        assert not app.collect(force=True).failed  # and the bad file is not retried into an error on later cycles
    finally:
        app.close()


def test_file_that_cannot_even_be_classified_is_quarantined_once(tmp_path):
    app, _ = wire_app(tmp_path)
    try:
        root = app.resolve_inbox(GATED)
        (root / "a_deep.json").write_bytes(b'{"uri":"D-1","x":' + b"[" * 200000 + b"]" * 200000 + b"}")
        (root / "b_good.txt").write_bytes(plain("D-2", 1))
        app.collect(force=True)
        rep = app.collect(force=True)
        assert not rep.failed and row(app, "D-2") is not None
        assert len(app.sources.recent_quarantine()) == 1
        assert not app.collect(force=True).failed and len(app.sources.recent_quarantine()) == 1
    finally:
        app.close()


def test_quarantine_reason_never_quotes_a_field_value(tmp_path):
    app, _ = wire_app(tmp_path)
    try:
        drop(app, GATED, "v.json", ninjs("Q-1", version="CONFIDENTIAL-WIRE-BODY"))
        drop(app, GATED, "t.json", ninjs("Q-2", embargoed="tomorrow CONFIDENTIAL-WIRE-BODY"))
        reasons = [r["reason"] for r in app.sources.recent_quarantine()]
        assert len(reasons) == 2 and not any("CONFIDENTIAL" in r for r in reasons)
        with TestClient(create_app(app), base_url="http://127.0.0.1:8765") as client:
            assert "CONFIDENTIAL" not in client.get("/sources").text
    finally:
        app.close()


@pytest.mark.req("FR-31b")
def test_ai_text_made_before_a_restriction_is_hidden(tmp_path):
    app, stub = wire_app(tmp_path, ai=True)
    try:
        drop(app, DEMO, "v1.txt", plain("A-1", 1))
        uid = row(app, "A-1")["uid"]
        assert len(stub.calls) == 1 and "AI 생성" in page(app, uid)  # the control: AI text shows while unrestricted
        drop(app, DEMO, "v2.txt", plain("A-1", 2, restrictions="NO ARCHIVE"))
        view = app.articles.get(uid)
        ai = app.ai_repo.latest_for_articles([view["article_id"]])[view["article_id"]]
        shown = page(app, uid)
        for key in ("summary_ko", "headline_ko", "rationale_ko"):
            text = ai["output"].get(key)
            assert not text or text not in shown
    finally:
        app.close()


def test_wrong_typed_field_is_a_parse_error_not_a_crash():
    with pytest.raises(WireParseError, match="malformed ninjs: "):
        parse_wire(ninjs("B-3", headline=["a", "list"]))


@pytest.mark.req("FR-07b")
def test_feed_entry_without_id_or_link_is_stored_once(tmp_path, fixture_server):
    feed = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>'
            b"<item><title>An entry with neither guid nor link</title><description>Body text</description></item>"
            b"</channel></rss>")
    url = fixture_server.route("/bare.xml", Resp(body=feed))
    fixture_server.route("/robots.txt", Resp(body=b""))
    app = make_app(tmp_path, fixture_server, [feed_source("bare", url)])
    try:
        app.collect(force=True)
        assert app.articles.counts()["articles"] == 1
        app.collect(force=True)
        assert app.articles.counts()["articles"] == 1 and app.sources.recent_quarantine() == []
    finally:
        app.close()


@pytest.mark.req("FR-15d")
def test_restricted_or_withdrawn_item_is_not_sent_on_manual_request(tmp_path):
    app, stub = wire_app(tmp_path, ai=True)
    try:
        drop(app, DEMO, "r.txt", plain("M-1", 1, restrictions="NO ARCHIVE"))
        drop(app, DEMO, "k1.txt", plain("M-2", 1, headline="A later withdrawn item", body="Body of the withdrawn item."))
        sent = len(stub.calls)
        assert sent >= 1 and not any("Talks resume in Geneva" in c.user for c in stub.calls)
        drop(app, DEMO, "k2.txt", plain("M-2", 2, headline="A later withdrawn item", body="Body of the withdrawn item.",
                                        pubstatus="canceled"))
        app.enrich(uids=[row(app, "M-1")["uid"], row(app, "M-2")["uid"]])
        assert len(stub.calls) == sent
        assert row(app, "M-1")["enrichment_status"] == "not_allowed"
    finally:
        app.close()


def test_stale_assessments_are_counted_and_refreshed_only_on_request(tmp_path):
    app, stub = wire_app(tmp_path, ai=True)
    try:
        drop(app, DEMO, "s.txt", plain("T-1", 1))
        assert len(stub.calls) == 1 and app.stale_ai() == []
        path = app.config_path("profiles") / "foreign_desk.yaml"
        prof = yaml.safe_load(path.read_text(encoding="utf-8"))
        prof["ai"]["instructions"] = "유럽 경제 뉴스를 중시한다."
        path.write_text(yaml.safe_dump(prof, allow_unicode=True), encoding="utf-8")
        app.collect(force=True)  # the edited profile is loaded; nothing is reassessed by itself
        assert len(stub.calls) == 1 and len(app.stale_ai()) == 1
        with TestClient(create_app(app), base_url="http://127.0.0.1:8765") as client:
            assert "newsmon enrich --stale" in client.get("/ai").text
        rep = app.enrich(stale=True)
        assert rep.called == 1 and len(stub.calls) == 2 and app.stale_ai() == []
    finally:
        app.close()


def test_status_prints_korean_when_output_is_redirected_to_a_legacy_code_page(tmp_path):
    cfg = write_config(tmp_path / "cfg", [])
    env = {**os.environ, "NEWSMON_CONFIG_DIR": str(cfg), "NEWSMON_DATA_DIR": str(tmp_path / "data"),
           "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    for argv in (["init"], ["status"]):
        out = subprocess.run([sys.executable, "-c", "import sys; from newsmon.cli import main; sys.exit(main())", *argv], capture_output=True, env=env)
        assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    assert "AI: 꺼짐" in out.stdout.decode("utf-8")


def test_copied_run_is_found_despite_case_and_punctuation():
    source = "Ministers agreed on Tuesday to share the river's water"
    assert _shares_20_chars("MINISTERS AGREED, ON TUESDAY, TO SHARE", source)
    assert _shares_20_chars("ministers  agreed on tuesday to share", source)
    assert not _shares_20_chars("장관들이 화요일에 강물을 나누기로 합의했다고 밝혔습니다", source)


def test_entity_declaration_refused_in_utf32():
    doc = '<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY x "y">]><rss version="2.0"><channel/></rss>'
    for enc in ("utf-32-le", "utf-32-be", "utf-16-le"):
        with pytest.raises(FeedParseError):
            parse_feed_bytes(doc.encode(enc))
    for enc in ("cp037", "utf-7"):  # encodings in which the declaration is spelt with other bytes
        declared = doc.replace('version="1.0"', f'version="1.0" encoding="{enc}"')
        with pytest.raises(FeedParseError):
            parse_feed_bytes(declared.encode(enc))
    ok = '<?xml version="1.0" encoding="EUC-KR"?><rss version="2.0"><channel><title>뉴스</title></channel></rss>'
    assert parse_feed_bytes(ok.encode("euc-kr")).feed.title == "뉴스"  # the control: a real feed encoding still parses
