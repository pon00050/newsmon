"""Release A.1 through the real pipeline with the AI stub: FR-10(d)-like gating, FR-11(b)(c), FR-12(b)(c), FR-13(a)(b),
FR-14(a), FR-15(a)-(d), FR-22(e)-like gating, FR-25, NFR-15 (fields_sent), and the A.1 acceptance criteria."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from newsmon.web.app import create_app
from tests.support.ai_stub import AIStub
from tests.support.fixture_server import Resp
from tests.support.instance import feed_source, fill_inbox, make_app, mock_wire_sources, serve_feeds

pytestmark = pytest.mark.integration
AI_ON = {"use_context": "private", "ai": {"capabilities": {"enrich": True}, "daily_cap_usd": 5.0,
                                           "selection": {"min_band": "drop", "max_items_per_cycle": 100}}}


def ai_app(tmp_path, server=None, sources=None, settings=None, stub=None, inbox=True, gated_only=False):
    app = make_app(tmp_path, server, sources if sources is not None else mock_wire_sources(), settings=settings or AI_ON,
                   with_inbox=inbox)
    stub = stub or AIStub()
    app.use_ai_provider(stub)
    if inbox:
        if not gated_only:
            fill_inbox(app, "mock_wire_demo")
        fill_inbox(app, "mock_wire_gated")
    return app, stub


def keyed(app, key):
    return app.db.query("SELECT a.article_id, a.uid, a.enrichment_status, a.final_band, a.rule_band, a.restrictions, a.status FROM article a "
                        "JOIN source s USING (source_id) WHERE s.key = ?", (key,))


@pytest.mark.req("FR-15a", "FR-11b")
def test_off_by_default_zero_calls(tmp_path):
    app = make_app(tmp_path, None, mock_wire_sources(), with_inbox=True)  # O1 settings
    stub = AIStub()
    app.use_ai_provider(stub)
    try:
        fill_inbox(app)
        app.collect(force=True)
        rep = app.collect(force=True)
        assert stub.calls == [] and rep.ai is None
        assert app.ai_status.header_label() == "AI: 꺼짐"
        assert app.db.scalar("SELECT count(*) FROM ai_interpretation") == 0
    finally:
        app.close()


@pytest.mark.req("FR-15d", "FR-10d")
def test_gated_wire_sends_nothing(tmp_path):
    app, stub = ai_app(tmp_path, gated_only=True)
    try:
        app.collect(force=True)
        rep = app.collect(force=True)
        gated = keyed(app, "mock_wire_gated")
        assert gated and stub.calls == [] and rep.ai.called == 0
        assert {r["enrichment_status"] for r in gated if r["rule_band"]} <= {"not_allowed", "pending"}
        assert any(r["enrichment_status"] == "not_allowed" for r in gated)
    finally:
        app.close()


@pytest.mark.req("FR-12c", "FR-11c", "NFR-30")
def test_enrichment_cached_and_recorded(tmp_path):
    app, stub = ai_app(tmp_path)
    try:
        app.collect(force=True)
        rep = app.collect(force=True)
        demo = keyed(app, "mock_wire_demo")
        assert rep.ai and rep.ai.done > 0
        # demo wire items were assessed, with model, prompt version, cost and fields sent recorded (FR-11(c), NFR-15)
        rows = app.db.query("SELECT model, prompt_version, cost_usd, fields_sent, input_tokens FROM ai_interpretation")
        assert rows and all(r[0] == "claude-haiku-5-5" and r[1] and r[2] > 0 and json.loads(r[3]) and r[4] for r in rows)
        assert app.ai_repo.spent(__import__("newsmon.ai.enrich", fromlist=["kst_day"]).kst_day(app.clock.now())) == \
            pytest.approx(len(stub.calls) * stub.cost_per_call)
        n = len(stub.calls)
        assert n == sum(1 for r in demo if r["enrichment_status"] == "done")
        # unchanged content: zero further calls (FR-12(c)), even when manually re-selected
        app.collect(force=True)
        app.enrich(uids=[r["uid"] for r in demo if r["enrichment_status"] == "done"])
        assert len(stub.calls) == n
    finally:
        app.close()


@pytest.mark.req("FR-12b", "NFR-15")
def test_fields_sent_follow_flags(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["bbc_world.xml"])
    src = [feed_source("bbc_world", urls["bbc_world.xml"], permitted_ops=["classify"])] + mock_wire_sources()
    app, stub = ai_app(tmp_path, fixture_server, src)
    try:
        app.collect(force=True)
        app.collect(force=True)
        unknown = [c for c in stub.calls if c.fields_sent and "body" not in c.fields_sent]
        assert unknown, "the ai_processing=unknown feed items were assessed"
        assert all(set(c.fields_sent) <= {"headline", "summary"} for c in unknown)
        assert all("summary_ko" not in c.schema["properties"] and "headline_ko" not in c.schema["properties"]
                   for c in unknown)  # classify only: no translation or summary requested
        assert any("body" in c.fields_sent for c in stub.calls)  # mock_wire_demo is ai_processing=yes, storage full
        assert all(c.system and "<article>" in c.user for c in stub.calls)
    finally:
        app.close()


@pytest.mark.req("FR-13a", "FR-13b")
def test_invalid_output_retried_once_then_review(tmp_path):
    stub = AIStub(responder=lambda call: {"rationale_ko": "This is English, not Korean."})
    app, stub = ai_app(tmp_path, stub=stub)
    try:
        app.collect(force=True)
        rep = app.collect(force=True)
        reviewed = [r for r in keyed(app, "mock_wire_demo") if r["enrichment_status"] == "review"]
        assert reviewed and rep.ai.review == len(reviewed)
        assert len(stub.calls) == 2 * len(reviewed)  # exactly one retry each, never a bulk retry loop
        statuses = {r[0] for r in app.db.query("SELECT validation_status FROM ai_interpretation")}
        assert statuses == {"invalid", "review"}
        app.collect(force=True)
        assert len(stub.calls) == 2 * len(reviewed)  # review items are not re-sent automatically
    finally:
        app.close()


@pytest.mark.req("FR-11a")
def test_ai_band_raises_to_report_not_flash(tmp_path):
    stub = AIStub(responder=lambda call: {"relevance_band": "report"})
    app, stub = ai_app(tmp_path, stub=stub)
    try:
        app.collect(force=True)
        app.collect(force=True)
        rows = keyed(app, "mock_wire_demo")
        raised = [r for r in rows if r["rule_band"] in ("drop", "review") and r["enrichment_status"] == "done"]
        assert raised and all(r["final_band"] == "report" for r in raised)
        assert not any(r["final_band"] == "flash" and r["rule_band"] != "flash" for r in rows)
    finally:
        app.close()


@pytest.mark.req("FR-14a")
def test_injection_flag_forces_review(tmp_path):
    stub = AIStub(responder=lambda call: {"relevance_band": "report", "injection_suspected": "Sudan" in call.user,
                                          "injection_note": "test"})
    app, stub = ai_app(tmp_path, stub=stub)
    try:
        app.collect(force=True)
        app.collect(force=True)
        sudan = app.db.one("SELECT final_band FROM article WHERE source_uri = 'PTW-20261124-0004'")
        assert sudan[0] == "review"
    finally:
        app.close()


@pytest.mark.req("FR-15c")
def test_spend_cap(tmp_path):
    settings = json.loads(json.dumps(AI_ON))
    settings["ai"]["daily_cap_usd"] = 0.01
    app, stub = ai_app(tmp_path, settings=settings, stub=AIStub(cost_per_call=0.004))
    try:
        app.collect(force=True)
        rep = app.collect(force=True)
        assert len(stub.calls) == 3  # $0.004 x 3 = $0.012 >= cap: the 4th call is not made
        assert "daily cap" in rep.ai.stopped
        assert app.db.scalar("SELECT capped FROM spend_day") == 1
        assert app.ai_status.header_label() == "AI: 중단"
        assert app.collect(force=True).ai.called == 0  # stays degraded until midnight KST
        # one minute past the next KST midnight, relative to the clock the cap was set on (a fixed date here went
        # stale once the real date reached it)
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        kst_now = app.clock.now().astimezone(ZoneInfo("Asia/Seoul"))
        next_day = (kst_now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
        app.clock = app.enricher.clock = __import__("tests.support.clock", fromlist=["FrozenClock"]).FrozenClock(next_day)
        assert app.enrich().called > 0
    finally:
        app.close()


@pytest.mark.req("FR-15b", "RA-11")
def test_outage_keeps_deterministic_core_running(tmp_path, fixture_server):
    urls = serve_feeds(fixture_server, ["bbc_world.xml", "yna_nk.xml"])
    src = [feed_source("bbc_world", urls["bbc_world.xml"]), feed_source("yna_nk", urls["yna_nk.xml"], "ko")]
    src += mock_wire_sources()
    stub = AIStub(down=True)
    app, stub = ai_app(tmp_path, fixture_server, src, stub=stub)
    try:
        app.collect(force=True)
        rep = app.collect(force=True)
        assert "unavailable" in (rep.ai.stopped or "")
        assert app.ai_status.header_label() == "AI: 중단"
        assert app.articles.counts()["articles"] > 20 and app.articles.search("Sudan")  # collection + search continue
        assert app.articles.queue(bands=["flash", "report", "review", "drop"])  # queue usable
        pending = [r for r in keyed(app, "mock_wire_demo") if r["enrichment_status"] == "pending"]
        assert pending  # nothing lost, nothing marked failed
        stub.down = False
        app.enricher.down_until = None
        app.enrich()
        primaries = {r[0] for r in app.db.query("SELECT article_id FROM article WHERE dup_of IS NULL AND status <> 'killed'")}
        demo = [r for r in keyed(app, "mock_wire_demo") if r["article_id"] in primaries]
        assert demo and all(r["enrichment_status"] in ("done", "review") for r in demo if not r["restrictions"])
        assert all(r["enrichment_status"] == "not_allowed" for r in demo if r["restrictions"])  # restricted: never sent
    finally:
        app.close()


@pytest.mark.req("FR-25a", "FR-19b", "FR-25b")
def test_ui_labels_ai_and_renders_inert(tmp_path):
    evil = {"rationale_ko": "중요한 국제 기사입니다 <img src=x onerror=alert(1)> [링크](http://exfil.example/c) http://exfil.example",
            "headline_ko": "번역된 제목 <script>alert(1)</script>"}
    app, stub = ai_app(tmp_path, stub=AIStub(responder=lambda call: evil))
    try:
        app.collect(force=True)
        app.collect(force=True)
        client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
        q = client.get("/?band=flash&band=report&band=review&band=drop&dups=1").text
        assert "AI: 켜짐" in q and 'data-ai="1"' in q and "AI 생성" in q
        uid = [r["uid"] for r in keyed(app, "mock_wire_demo") if r["enrichment_status"] == "done"][0]
        page = client.get(f"/article/{uid}").text
        box = re.search(r'<div class="ai-box" data-ai="1">(.*?)</div>\s*\n', page, re.S).group(1)
        assert "AI 생성" in box and "claude-haiku-5-5" in box and "assess-p1" in box
        for bad in ("<img", "<script", "exfil.example", "onerror", 'href="http'):
            assert bad not in box, bad
        assert "AI 미적용 (라이선스)" in q  # gated items are tagged, not silently skipped
        client.close()
    finally:
        app.close()


def test_toggle_and_manual_selection(tmp_path):
    settings = json.loads(json.dumps(AI_ON))
    settings["ai"]["selection"] = {"min_band": "report", "max_items_per_cycle": 100}
    app, stub = ai_app(tmp_path, settings=settings)
    try:
        app.collect(force=True)
        app.collect(force=True)
        auto = len(stub.calls)
        target = [r for r in keyed(app, "mock_wire_demo") if r["enrichment_status"] == "pending" and not r["restrictions"]
                  and r["status"] != "killed"][0]  # a restricted or withdrawn item is never sent
        client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
        assert client.post(f"/article/{target['uid']}/enrich").status_code == 403  # same-origin required
        r = client.post(f"/article/{target['uid']}/enrich", headers={"Origin": "http://127.0.0.1:8765"},
                        follow_redirects=False)
        assert r.status_code == 303 and len(stub.calls) == auto + 1  # manual selection of a below-threshold item
        client.post("/ai/toggle", headers={"Origin": "http://127.0.0.1:8765"})
        assert app.enricher.paused and app.ai_status.header_label() == "AI: 꺼짐"
        before = len(stub.calls)
        app.collect(force=True)
        assert len(stub.calls) == before
        assert "AI 다시 켜기" in client.get("/ai").text
        client.post("/ai/toggle", headers={"Origin": "http://127.0.0.1:8765"})
        assert not app.enricher.paused
        client.close()
    finally:
        app.close()


def test_ai_defect_cannot_break_collection(tmp_path):
    def boom(call):
        raise ZeroDivisionError("bug in a provider adapter")
    app, stub = ai_app(tmp_path, stub=AIStub(responder=boom))
    try:
        app.collect(force=True)
        rep = app.collect(force=True)
        assert rep.ai_error and "ZeroDivisionError" in rep.ai_error
        assert rep.feeds and not rep.failed and app.articles.counts()["articles"] > 0
    finally:
        app.close()
