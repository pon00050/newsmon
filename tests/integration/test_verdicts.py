"""Editorial verdicts and the shift report (duty "중요 자료 정리 및 보고 (PC등록)"; FR-18(b)(c), INTERFACE_SPEC §2).

Wire inputs only (no feed server), on a frozen clock, so verdict times and the report window are exact.
"""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from newsmon.config.settings import Settings
from newsmon.pipeline.normalise import iso
from newsmon.web.app import create_app
from tests.support.clock import FrozenClock
from tests.support.instance import fill_inbox, make_app, mock_wire_sources

pytestmark = pytest.mark.integration

ORIGIN = {"Origin": "http://127.0.0.1:8765"}
# entity-encoded, because ingest strips literal tags and then unescapes: this is how markup reaches a stored headline
HOSTILE = "&lt;script&gt;alert(1)&lt;/script&gt; [x](javascript:alert(1)) Synthetic hostile headline"


def wire(app, name: str, id_: str, headline: str, body: str, *, version: int = 1,
         pubstatus: str | None = None, restrictions: str | None = None, key: str = "mock_wire_demo") -> Path:
    lines = ["SYNTHETIC: true", f"ID: {id_}", f"VERSION: {version}", "VERSIONCREATED: 2026-11-26T16:00:00+00:00",
             "LANGUAGE: en", "URGENCY: 3", "SLUG: TEST", f"HEADLINE: {headline}", "DATELINE: NOWHERE"]
    if pubstatus:
        lines.append(f"PUBSTATUS: {pubstatus}")
    if restrictions:
        lines.append(f"RESTRICTIONS: {restrictions}")
    p = app.resolve_inbox(f"inbox/{key}") / "plain" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\nBODY:\n" + body + "\n", encoding="utf-8")
    return p


def settle(app) -> None:
    """A wire file is ingested once its size and mtime are unchanged across two scans."""
    app.collect(force=True)
    app.collect(force=True)


def uid_of(app, source_uri: str) -> str:
    return app.db.scalar("SELECT uid FROM article WHERE source_uri = ?", (source_uri,))


def post(client, uid: str, verdict: str, note: str = "", next_: str | None = None, headers=ORIGIN):
    data = {"verdict": verdict, "note": note}
    if next_ is not None:
        data["next"] = next_
    return client.post(f"/article/{uid}/verdict", data=data, headers=headers, follow_redirects=False)


@pytest.fixture
def desk(tmp_path):
    clock = FrozenClock("2026-11-26T17:00:00+00:00")  # 02:00 KST, inside a 01:00-09:00 shift
    app = make_app(tmp_path, None, mock_wire_sources(), clock=clock, with_inbox=True,
                   settings={"use_context": "private", "desk_editor": "kim"})
    fill_inbox(app, "mock_wire_demo")
    fill_inbox(app, "mock_wire_gated")
    # distinct texts, so near-duplicate detection keeps all three as separate queue rows
    wire(app, "t_hostile.txt", "TEST-HOSTILE-1", HOSTILE, "Glaciers in the fictional range of Norvale retreated sharply.")
    wire(app, "t_story_v1.txt", "TEST-STORY-1", "Fictional port of Ostrava Bay reopens after storm",
         "Harbour officials in the invented city said cargo cranes resumed work on Thursday morning.")
    wire(app, "t_kill.txt", "TEST-KILL-1", "Imaginary parliament of Veltria passes budget",
         "Lawmakers in the made-up republic approved spending after a twelve-hour session.")
    settle(app)
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    yield app, client, clock
    client.close()
    app.close()


@pytest.mark.req("FR-18b")
def test_verdict_writes_one_row_with_editor_and_time(desk):
    app, client, clock = desk
    uid = uid_of(app, "TEST-STORY-1")
    ai_before = app.db.scalar("SELECT count(*) FROM ai_interpretation")
    r = post(client, uid, "report_to_desk", "요지: 테스트\n검증: 미확인")
    assert r.status_code == 303 and r.headers["location"].startswith(f"/article/{uid}?msg=")
    rows = app.db.query("SELECT editor, verdict, note, created_utc, target_kind FROM editorial_assessment")
    assert len(rows) == 1
    assert tuple(rows[0]) == ("kim", "report_to_desk", "요지: 테스트\n검증: 미확인", iso(clock.now()), "article")
    assert app.db.scalar("SELECT count(*) FROM ai_interpretation") == ai_before


def test_verdict_route_refuses_bad_requests(desk):
    app, client, _ = desk
    uid = uid_of(app, "TEST-STORY-1")
    assert post(client, uid, "report_to_desk", headers={}).status_code == 403
    assert post(client, uid, "report_to_desk", headers={"Origin": "https://evil.example"}).status_code == 403
    assert post(client, uid, "archived").status_code == 400
    assert post(client, uid, "delete").status_code == 400
    assert post(client, "a_doesnotexist", "verify").status_code == 404
    assert app.db.scalar("SELECT count(*) FROM editorial_assessment") == 0
    # the return path stays on this app, and the queue filters survive
    assert post(client, uid, "verify", next_="//evil.example/x").headers["location"].startswith(f"/article/{uid}?")
    assert post(client, uid, "verify", next_="https://evil.example").headers["location"].startswith(f"/article/{uid}?")
    loc = post(client, uid, "verify", next_="/?band=flash&band=report").headers["location"]
    assert loc.startswith("/?band=flash&band=report&msg=")


def test_note_is_capped(desk):
    app, client, _ = desk
    uid = uid_of(app, "TEST-STORY-1")
    assert post(client, uid, "verify", "가" * 1000).status_code == 303  # the textarea maximum fits the form limit
    assert post(client, uid, "verify", "a" * 5000).status_code == 303
    assert [len(r[0]) for r in app.db.query("SELECT note FROM editorial_assessment ORDER BY assess_id")] == [1000, 1000]
    assert post(client, uid, "verify", "가" * 5000).status_code == 413  # 45 KB encoded
    assert app.db.scalar("SELECT count(*) FROM editorial_assessment") == 2


def test_latest_verdict_wins_and_ignore_leaves_the_report(desk):
    app, client, clock = desk
    uid = uid_of(app, "TEST-STORY-1")
    post(client, uid, "report_to_desk", "first")
    clock.advance(60)
    post(client, uid, "verify", "second")
    page = client.get("/shift-report").text
    verify_part = page.split("확인 중 (검증 필요)")[1]
    assert f'data-shift-uid="{uid}"' in verify_part and "second" in verify_part and "first" not in page
    clock.advance(60)
    post(client, uid, "ignore")
    assert f'data-shift-uid="{uid}"' not in client.get("/shift-report").text
    item = client.get(f"/article/{uid}").text
    assert item.count("<li><b>") == 3 and "현재" in item  # full history on the item page, newest first
    queue = client.get("/?band=flash&band=report&band=review&band=drop").text
    row = re.search(rf'<tr data-uid="{uid}">.*?</tr>', queue, re.S).group(0)
    assert "✔ 무시" in row and "kim" in row


def test_report_window_follows_the_clock(desk):
    app, client, clock = desk
    uid = uid_of(app, "TEST-STORY-1")
    post(client, uid, "report_to_desk")
    assert f'data-shift-uid="{uid}"' in client.get("/shift-report").text
    clock.advance(hours=9)
    assert f'data-shift-uid="{uid}"' not in client.get("/shift-report").text  # default window 8 h
    assert f'data-shift-uid="{uid}"' in client.get("/shift-report?hours=12").text
    assert "(48시간)" in client.get("/shift-report?hours=999").text  # clamped


def test_killed_and_revised_after_verdict_are_flagged(desk):
    app, client, clock = desk
    story, kill = uid_of(app, "TEST-STORY-1"), uid_of(app, "TEST-KILL-1")
    post(client, story, "report_to_desk")
    post(client, kill, "report_to_desk")
    clock.advance(120)
    wire(app, "t_story_v2.txt", "TEST-STORY-1", "Fictional port of Ostrava Bay reopens after storm",
         "Harbour officials in the invented city said cargo cranes resumed work; two berths stay closed.", version=2)
    wire(app, "t_kill_cancel.txt", "TEST-KILL-1", "Imaginary parliament of Veltria passes budget",
         "Withdrawn.", version=2, pubstatus="canceled")
    settle(app)
    assert app.db.scalar("SELECT status FROM article WHERE uid = ?", (kill,)) == "killed"
    page = client.get("/shift-report").text
    rows = {u: m for u, m in re.findall(r'<tr data-shift-uid="([^"]+)">(.*?)</tr>', page, re.S)}
    assert "철회(KILL)" in rows[kill] and "판정 후 개정" not in rows[kill]
    assert "판정 후 개정 v2" in rows[story] and "철회" not in rows[story]
    assert post(client, kill, "verify").status_code == 409  # a withdrawn item takes no new verdict
    assert f'data-uid="{kill}"' not in client.get("/").text  # and stays out of the queue


def test_report_carries_only_whitelisted_fields(desk):
    """Recipient gating is not built, so the report never carries a summary, a body or AI text, whatever the source's
    display level; restricted items stay headline-only; licence marks are shown."""
    app, client, _ = desk
    rows = app.db.query(
        "SELECT a.uid, r.headline, r.description_text, r.body_text, s.key, a.restrictions FROM article a "
        "JOIN article_revision r ON r.revision_id = a.current_revision_id JOIN source s ON s.source_id = a.source_id "
        "WHERE a.status <> 'killed' AND (r.body_text IS NOT NULL OR a.restrictions IS NOT NULL)")
    assert len(rows) >= 5 and any(r[4] == "mock_wire_gated" for r in rows) and any(r[5] for r in rows), "control"
    for r in rows:
        post(client, r[0], "report_to_desk")
    for page in (client.get("/shift-report?hours=48").text, client.get("/shift-report?hours=48&download=1").text):
        for _uid, headline, desc, body, key, restrictions in rows:
            if body:
                for para in body.split("\n\n"):
                    assert para[:60] not in page, para[:60]
            if desc and desc != headline:
                assert desc[:60] not in page
        assert page.count('data-shift-uid="') == len(rows)
        assert "사용 제한: 제목만" in page and "재배포 금지" in page and "합성" in page and "내부용" in page


def test_download_is_a_standalone_attachment(desk):
    app, client, _ = desk
    post(client, uid_of(app, "TEST-STORY-1"), "report_to_desk")
    r = client.get("/shift-report?download=1")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith('attachment; filename="shift_report_20261126T1700Z')
    assert "<header>" not in r.text and "/refresh" not in r.text and 'href="/article/' not in r.text
    assert "<header>" in client.get("/shift-report").text


def test_hostile_text_is_inert_in_report_and_pages(desk):
    app, client, _ = desk
    uid = uid_of(app, "TEST-HOSTILE-1")
    assert "<script>alert(1)</script>" in app.articles.get(uid)["headline"], "control: the markup is really stored"
    post(client, uid, "report_to_desk", '<img src=x onerror=alert(1)> "quoted" note')
    pages = [client.get("/shift-report").text, client.get("/shift-report?download=1").text, client.get(f"/article/{uid}").text]
    for page in pages:
        assert "<script>alert(1)" not in page and "<img src=x" not in page and 'href="javascript:' not in page
        assert "&lt;img src=x onerror=alert(1)&gt;" in page
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


@pytest.mark.req("FR-18c")
def test_queue_offers_keyboard_verdicts_without_firing_while_typing(desk):
    _, client, _ = desk
    page = client.get("/").text
    assert re.search(r'<tr data-uid="[^"]+">', page)  # the row element itself is unchanged
    for key in "rvx":
        assert f'data-key="{key}"' in page
    assert "t.tagName === 'TEXTAREA'" in page and "t.isContentEditable" in page and "e.ctrlKey" in page
    assert "<th>처리</th>" in page


def test_desk_editor_setting():
    assert Settings().desk_editor == "local"
    with pytest.raises(ValidationError):
        Settings(desk_editor="")
    with pytest.raises(ValidationError):
        Settings(desk_editor="x" * 41)
