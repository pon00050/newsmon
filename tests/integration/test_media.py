"""Wire footage check, classification and ingest tracking (duty 2 "외신 영상 분류작업 및 인제스트", v1).

Clips are generated with ffmpeg at test time (nothing is committed). Detector trust follows collection-integrity rule 2:
a clean clip must report no fault (nonsense control) and a clip with planted black and silence must report both at the
right times (known answer). Tests that need ffmpeg skip without it; the rest use a stub tool.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newsmon.adapters.ffmpeg_media import MediaToolError
from newsmon.web.app import create_app
from tests.integration.test_verdicts import settle
from tests.support.clock import FrozenClock
from tests.support.instance import make_app, mock_wire_sources

pytestmark = pytest.mark.integration
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not on PATH")

ORIGIN = {"Origin": "http://127.0.0.1:8765"}
START = "2026-11-26T17:00:00+00:00"


def make_clip(path: Path, *, seconds: int = 12, black: tuple | None = None, silence: tuple | None = None) -> Path:
    vf = "null" if not black else f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,{black[0]},{black[1]})'"
    af = "anull" if not silence else f"volume=enable='between(t,{silence[0]},{silence[1]})':volume=0"
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=25:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={seconds}", "-vf", vf, "-af", af,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True, timeout=120)
    return path


def sidecar(app, name: str, uri: str, headline: str, href: str, *, key: str = "mock_wire_demo", version: int = 1,
            restrictions: str | None = None, located: str = "Nowhere") -> Path:
    d = {"x_synthetic": True, "uri": uri, "type": "video", "version": str(version),
         "versioncreated": "2026-11-26T16:00:00Z", "pubstatus": "usable", "urgency": 4, "headline": headline,
         "slugline": uri.upper(), "located": located, "language": "en",
         "description_text": "Synthetic footage for a test.", "body_text": "Synthetic footage for a test.",
         "renditions": [{"name": "main", "href": href, "contenttype": "video/mp4"}], "associations": {}}
    if restrictions:
        d["restrictions"] = restrictions
    p = app.resolve_inbox(f"inbox/{key}") / "video" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def clip_dir(app, key: str = "mock_wire_demo") -> Path:
    return app.resolve_inbox(f"inbox/{key}") / "video"


def check_of(app, uri: str) -> dict | None:
    r = app.db.one("SELECT c.* FROM media_check c JOIN media_asset m ON m.asset_id = c.asset_id JOIN article a ON "
                   "a.article_id = m.article_id WHERE a.source_uri = ?", (uri,))
    return dict(r) if r else None


class StubTool:
    """Stands in for ffmpeg: fixed facts, configurable faults, a tiny thumbnail."""

    def __init__(self, faults=None, fail=False):
        self.faults, self.fail, self.probed = faults or {}, fail, []

    def probe(self, path):
        self.probed.append(Path(path).name)
        if self.fail:
            raise MediaToolError("Invalid data found when processing input")
        return {"container": "mov,mp4", "duration_s": 10.0, "size_bytes": 1000,
                "video": {"codec": "h264", "width": 320, "height": 240, "fps": 25.0},
                "audio": {"codec": "aac", "channels": 2, "sample_rate": 48000}}

    def detect(self, path, *, has_video, has_audio, duration):
        return {"black": [], "silence": [], "freeze": [], **self.faults}

    def thumbnail(self, path, out, duration):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\xff\xd8\xff\xe0stub-jpeg")
        return True


def fake_clip(path: Path, content: bytes = b"") -> Path:
    """Bytes that the watcher recognises as MP4 (ftyp box) without being a playable file; for the stub tool."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + content)
    return path


@pytest.fixture
def desk(tmp_path):
    app = make_app(tmp_path, None, mock_wire_sources(), clock=FrozenClock(START), with_inbox=True)
    yield app
    app.close()


@needs_ffmpeg
def test_known_answer_and_nonsense_controls(desk):
    app = desk
    make_clip(clip_dir(app) / "clean.mp4")
    make_clip(clip_dir(app) / "faulty.mp4", black=(3, 5), silence=(7, 9))
    sidecar(app, "clean.json", "clipclean", "Synthetic clean clip", "clean.mp4")
    sidecar(app, "faulty.json", "clipfaulty", "Synthetic faulty clip", "faulty.mp4")
    settle(app)
    clean, faulty = check_of(app, "clipclean"), check_of(app, "clipfaulty")
    assert clean and faulty, "control: both clips were checked in the cycle"
    assert clean["status"] == "ok" and json.loads(clean["faults_json"]) == {"black": [], "silence": []}
    probe = json.loads(clean["probe_json"])
    assert probe["video"] == {"codec": "h264", "width": 320, "height": 240, "fps": 25.0}
    assert probe["audio"]["codec"] == "aac" and probe["audio"]["sample_rate"] == 48000
    assert faulty["status"] == "needs_check"
    f = json.loads(faulty["faults_json"])
    assert len(f["black"]) == 1 and abs(f["black"][0][0] - 3) < 0.2 and abs(f["black"][0][1] - 5) < 0.2
    assert len(f["silence"]) == 1 and abs(f["silence"][0][0] - 7) < 0.2 and abs(f["silence"][0][1] - 9) < 0.2
    freeze = json.loads(faulty["notes_json"])["freeze"]
    assert not any(s < 5 and 3 < e for s, e in freeze)  # black is not double-reported as a frozen picture
    page = TestClient(create_app(app), base_url="http://127.0.0.1:8765").get("/media").text
    assert "블랙 00:03" in page and "무음 00:07" in page and "320×240 · h264 25fps · aac 1ch 48kHz · 12.0s" in page


@needs_ffmpeg
def test_thumbnail_only_where_the_licence_stores_content(tmp_path):
    rows = mock_wire_sources()
    next(r for r in rows if r["key"] == "mock_wire_gated")["storage"] = "metadata"
    app = make_app(tmp_path, None, rows, clock=FrozenClock(START), with_inbox=True)
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    try:
        make_clip(clip_dir(app) / "full.mp4", seconds=6)
        make_clip(clip_dir(app) / "restricted.mp4", seconds=6)
        make_clip(clip_dir(app, "mock_wire_gated") / "meta.mp4", seconds=6)
        sidecar(app, "full.json", "clipfull", "Synthetic clip, full storage", "full.mp4")
        sidecar(app, "restricted.json", "cliprestr", "Synthetic clip, restricted", "restricted.mp4",
                restrictions="ZZ-TEST-RESTRICTION")
        sidecar(app, "meta.json", "clipmeta", "Synthetic clip, metadata storage", "meta.mp4", key="mock_wire_gated")
        settle(app)
        full, restr, meta = (check_of(app, u) for u in ("clipfull", "cliprestr", "clipmeta"))
        assert full["thumb_path"] and (app.cfg.paths.data_dir / full["thumb_path"]).is_file()
        assert restr["thumb_path"] is None and meta["thumb_path"] is None
        assert restr["status"] == "ok" and meta["status"] == "ok"  # still checked: technical facts are not content
        r = client.get(f"/media/thumb/{full['asset_id']}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"
        assert client.get(f"/media/thumb/{restr['asset_id']}").status_code == 404
        assert client.get(f"/media/thumb/{meta['asset_id']}").status_code == 404
        # a restriction that arrives later withdraws the thumbnail at serving time
        app.db.execute("UPDATE article SET restrictions = 'ZZ-LATER' WHERE source_uri = 'clipfull'")
        assert client.get(f"/media/thumb/{full['asset_id']}").status_code == 404
    finally:
        client.close()
        app.close()


@needs_ffmpeg
def test_an_unplayable_file_is_recorded_as_unreadable(desk):
    app = desk
    fake_clip(clip_dir(app) / "broken.mp4", b"not really video")
    sidecar(app, "broken.json", "clipbroken", "Synthetic broken clip", "broken.mp4")
    settle(app)
    c = check_of(app, "clipbroken")
    assert c["status"] == "unreadable" and c["error"] and c["thumb_path"] is None


def test_classification_states_and_csv(desk):
    app = desk
    app.media_tool = StubTool()
    fake_clip(clip_dir(app) / "nk.mp4", b"1")
    fake_clip(clip_dir(app) / "other.mp4", b"2")
    sidecar(app, "nk.json", "clipnk", "North Korea fires missile, synthetic footage", "nk.mp4", located="Pyongyang")
    sidecar(app, "other.json", "clipother", "=HYPERLINK(\"http://evil.example\") synthetic weather footage", "other.mp4")
    sidecar(app, "wait.json", "clipwait", "Synthetic clip whose file has not arrived", "never.mp4")
    settle(app)
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    try:
        page = client.get("/media").text
        rows = {m[0]: m[1] for m in re.findall(r'<tr data-asset-id="(\d+)">(.*?)</tr>', page, re.S)}
        assert len(rows) == 3
        nk = next(v for v in rows.values() if "North Korea" in v)
        other = next(v for v in rows.values() if "HYPERLINK" in v)
        wait = next(v for v in rows.values() if "not arrived" in v)
        assert "한반도" in nk and "인제스트 준비됨" in nk
        assert "미분류" in other
        assert "파일 대기" in wait and "확인 전" in wait
        csv = client.get("/media.csv")
        assert csv.headers["content-disposition"].startswith('attachment; filename="ingest_sheet_')
        assert csv.text.startswith("﻿상태,철회,사용 제한,제목")
        assert "'=HYPERLINK" in csv.text and ",=HYPERLINK" not in csv.text
    finally:
        client.close()


def test_filed_mark_resets_when_a_new_file_version_arrives(desk):
    app = desk
    app.media_tool = StubTool()
    clip = fake_clip(clip_dir(app) / "story.mp4", b"version one")
    sidecar(app, "story.json", "clipstory", "Synthetic story footage", "story.mp4")
    settle(app)
    c = check_of(app, "clipstory")
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    try:
        assert client.post(f"/media/{c['asset_id']}/filed").status_code == 403
        assert client.post(f"/media/{c['asset_id']}/filed", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post(f"/media/{c['asset_id']}/delete", headers=ORIGIN).status_code == 404
        assert client.post("/media/999999/filed", headers=ORIGIN).status_code == 404
        assert client.post(f"/media/{c['asset_id']}/filed", headers=ORIGIN, follow_redirects=False).status_code == 303
        c = check_of(app, "clipstory")
        assert c["ingest_state"] == "filed" and c["ingest_by"] == "local"
        assert "인제스트 완료" in client.get("/media").text
        fake_clip(clip, b"version two, a different file")  # the agency re-delivers the clip
        settle(app)
        c2 = check_of(app, "clipstory")
        assert c2["sha256"] != c["sha256"] and c2["ingest_state"] == "pending" and c2["ingest_by"] is None
        assert app.media_tool.probed.count("story.mp4") == 2
        settle(app)  # nothing new: no third check
        assert app.media_tool.probed.count("story.mp4") == 2
    finally:
        client.close()


def test_a_file_outside_the_inbox_is_never_opened(desk, tmp_path):
    app = desk
    app.media_tool = StubTool()
    fake_clip(clip_dir(app) / "inside.mp4", b"inside")
    sidecar(app, "inside.json", "clipinside", "Synthetic clip", "inside.mp4")
    app.media_tool = None  # ingest first without checking
    settle(app)
    fake_clip(tmp_path / "outside.mp4", b"outside")
    app.db.execute("UPDATE inbox_ledger SET rel_path = '../../../outside.mp4' WHERE status = 'media'")
    app.media_tool = tool = StubTool()
    app.check_media()
    c = check_of(app, "clipinside")
    assert c["status"] == "missing" and "outside" in c["error"] and tool.probed == []


def test_faults_mark_the_clip_and_the_nav_count(desk):
    app = desk
    app.media_tool = StubTool(faults={"black": [(2.0, 4.0)], "freeze": [(6.0, 9.0)]})
    fake_clip(clip_dir(app) / "bad.mp4", b"bad")
    sidecar(app, "bad.json", "clipbad", "Synthetic clip with a fault", "bad.mp4")
    settle(app)
    assert check_of(app, "clipbad")["status"] == "needs_check" and app.media.attention_count() == 1
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    try:
        home = client.get("/").text
        assert re.search(r'영상 <span class="tag err">1</span>', home)
        page = client.get("/media").text
        assert "확인 필요" in page and "블랙 00:02.0–00:04.0" in page and "정지 화면 00:06.0–00:09.0" in page
        asset = check_of(app, "clipbad")["asset_id"]
        client.post(f"/media/{asset}/filed", headers=ORIGIN)
        assert app.media.attention_count() == 0  # filed clips no longer need attention
    finally:
        client.close()


def test_a_media_defect_never_stops_collection(desk, monkeypatch):
    app = desk
    monkeypatch.setattr(app, "check_media", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    rep = app.collect(force=True)
    assert rep.media_error == "RuntimeError: boom" and rep.rank_error is None


def test_without_ffmpeg_nothing_is_checked_and_the_page_says_so(desk):
    app = desk
    app.media_tool = None
    fake_clip(clip_dir(app) / "x.mp4", b"x")
    sidecar(app, "x.json", "clipx", "Synthetic clip", "x.mp4")
    settle(app)
    assert check_of(app, "clipx") is None and app.check_media()["tool"] is False
    page = TestClient(create_app(app), base_url="http://127.0.0.1:8765").get("/media").text
    assert "ffmpeg/ffprobe가 없어" in page and "확인 대기" in page


def test_tool_failure_is_recorded_not_raised(desk):
    app = desk
    app.media_tool = StubTool(fail=True)
    fake_clip(clip_dir(app) / "y.mp4", b"y")
    sidecar(app, "y.json", "clipy", "Synthetic clip", "y.mp4")
    rep = app.collect(force=True)
    rep = app.collect(force=True)
    assert rep.media_error is None
    assert check_of(app, "clipy")["status"] == "unreadable"


# --- review findings (2026-11-27): each would have passed the tests above while broken ---------------------------------
def test_a_clip_over_the_inbox_size_limit_is_still_checked(tmp_path):
    """Broadcast clips are far above the text-file limit; they must reach the check, not the quarantine."""
    app = make_app(tmp_path, None, mock_wire_sources(), clock=FrozenClock(START), with_inbox=True,
                   settings={"use_context": "private", "inbox": {"max_file_bytes": 1024}})
    try:
        app.media_tool = StubTool()
        fake_clip(clip_dir(app) / "big.mp4", b"x" * 4096)
        sidecar(app, "big.json", "clipbig", "Synthetic large clip", "big.mp4")
        settle(app)
        assert app.db.scalar("SELECT status FROM inbox_ledger WHERE rel_path = 'video/big.mp4'") == "media"
        assert app.db.scalar("SELECT count(*) FROM quarantine") == 0
        assert check_of(app, "clipbig")["status"] == "ok"
        big = (tmp_path / "cfg" / "inbox" / "mock_wire_demo" / "video" / "huge.txt")
        big.write_text("ID: X\nHEADLINE: oversize text\nBODY:\n" + "y" * 4096, encoding="utf-8")
        settle(app)  # a large non-media file is still refused, as before
        assert app.db.scalar("SELECT status FROM inbox_ledger WHERE rel_path = 'video/huge.txt'") == "quarantined"
    finally:
        app.close()


def test_a_withdrawn_clip_is_never_offered_for_filing(desk):
    app = desk
    app.media_tool = StubTool()
    fake_clip(clip_dir(app) / "k.mp4", b"k")
    sidecar(app, "k.json", "clipkill", "Synthetic clip that will be withdrawn", "k.mp4")
    settle(app)
    asset = check_of(app, "clipkill")["asset_id"]
    assert check_of(app, "clipkill")["thumb_path"]
    p = app.resolve_inbox("inbox/mock_wire_demo") / "video" / "k_cancel.json"
    p.write_text(json.dumps({"uri": "clipkill", "type": "video", "version": "2", "pubstatus": "canceled",
                             "headline": "Synthetic clip that will be withdrawn", "language": "en"}), encoding="utf-8")
    settle(app)
    assert app.db.scalar("SELECT status FROM article WHERE source_uri = 'clipkill'") == "killed"
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    try:
        row = re.search(rf'<tr data-asset-id="{asset}">.*?</tr>', client.get("/media").text, re.S).group(0)
        assert "철회 · 인제스트 금지" in row and "인제스트 완료</button>" not in row and "/media/thumb/" not in row
        assert client.post(f"/media/{asset}/filed", headers=ORIGIN).status_code == 404
        assert client.get(f"/media/thumb/{asset}").status_code == 404
        line = next(x for x in client.get("/media.csv").text.splitlines() if "withdrawn" in x)
        assert line.startswith("철회 · 인제스트 금지,철회,")
    finally:
        client.close()


def test_a_later_restriction_withdraws_the_thumbnail_even_at_headline_display(tmp_path):
    rows = mock_wire_sources()
    next(r for r in rows if r["key"] == "mock_wire_demo")["display"] = "headline"  # the default display level
    app = make_app(tmp_path, None, rows, clock=FrozenClock(START), with_inbox=True)
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    try:
        app.media_tool = StubTool()
        fake_clip(clip_dir(app) / "h.mp4", b"h")
        sidecar(app, "h.json", "cliph", "Synthetic clip at headline display", "h.mp4")
        settle(app)
        asset = check_of(app, "cliph")["asset_id"]
        assert client.get(f"/media/thumb/{asset}").status_code == 200, "control: served before the restriction"
        app.db.execute("UPDATE article SET restrictions = 'ZZ-LATER' WHERE source_uri = 'cliph'")
        assert client.get(f"/media/thumb/{asset}").status_code == 404
        assert "/media/thumb/" not in client.get("/media").text
    finally:
        client.close()
        app.close()


def test_an_updated_clip_under_a_new_file_name_is_checked_as_a_new_file(desk):
    app = desk
    app.media_tool = StubTool()
    fake_clip(clip_dir(app) / "abc--1--aaa.mp4", b"first cut")
    sidecar(app, "abc_v1.json", "clipabc", "Synthetic updated clip", "abc--1--aaa.mp4")
    settle(app)
    first = check_of(app, "clipabc")
    TestClient(create_app(app), base_url="http://127.0.0.1:8765").post(f"/media/{first['asset_id']}/filed", headers=ORIGIN)
    fake_clip(clip_dir(app) / "abc--2--bbb.mp4", b"second cut, longer")
    sidecar(app, "abc_v2.json", "clipabc", "Synthetic updated clip", "abc--2--bbb.mp4", version=2)
    settle(app)
    rows = app.db.query("SELECT m.href, c.ingest_state FROM media_asset m JOIN media_check c ON c.asset_id = m.asset_id "
                        "JOIN article a ON a.article_id = m.article_id WHERE a.source_uri = 'clipabc' ORDER BY m.asset_id")
    assert [tuple(r) for r in rows] == [("abc--1--aaa.mp4", "filed"), ("abc--2--bbb.mp4", "pending")]


def test_in_the_web_server_checks_run_beside_collection_not_inside_it(desk):
    import threading
    app = desk
    gate = threading.Event()

    class SlowTool(StubTool):
        def probe(self, path):
            gate.wait(10)  # held until the cycle has returned
            return super().probe(path)

    app.media_tool = SlowTool()
    app.media_async = True
    fake_clip(clip_dir(app) / "slow.mp4", b"slow")
    sidecar(app, "slow.json", "clipslow", "Synthetic slow clip", "slow.mp4")
    app.collect(force=True)
    rep = app.collect(force=True)  # returns although the check is blocked
    assert rep.media == {"tool": True, "started": True} and check_of(app, "clipslow") is None
    assert app.kick_media()["started"] is False  # one worker at a time
    gate.set()
    app._media_thread.join(10)
    assert check_of(app, "clipslow")["status"] == "ok"


def test_any_failure_on_one_clip_is_recorded_and_the_next_clip_still_runs(desk):
    app = desk

    class Flaky(StubTool):
        def probe(self, path):
            if Path(path).name == "a.mp4":
                raise IndexError("list index out of range")
            return super().probe(path)

    app.media_tool = Flaky()
    fake_clip(clip_dir(app) / "a.mp4", b"a")
    fake_clip(clip_dir(app) / "b.mp4", b"b")
    sidecar(app, "a.json", "clipa", "Synthetic clip A", "a.mp4")
    sidecar(app, "b.json", "clipb", "Synthetic clip B", "b.mp4")
    settle(app)
    assert check_of(app, "clipa")["status"] == "unreadable" and "IndexError" in check_of(app, "clipa")["error"]
    assert check_of(app, "clipb")["status"] == "ok"


def test_a_file_removed_before_its_check_is_reported_missing(desk):
    app = desk
    app.media_tool = None
    clip = fake_clip(clip_dir(app) / "gone.mp4", b"gone")
    sidecar(app, "gone.json", "clipgone", "Synthetic clip removed early", "gone.mp4")
    settle(app)
    clip.unlink()
    settle(app)
    assert app.db.scalar("SELECT status FROM inbox_ledger WHERE rel_path = 'video/gone.mp4'") == "gone"
    app.media_tool = StubTool()
    app.check_media()
    c = check_of(app, "clipgone")
    assert c["status"] == "missing" and "no longer" in c["error"]


# --- end-of-day fixes (2026-11-27) -----------------------------------------------------------------------------------------
def test_recheck_queues_a_failed_clip_again(desk):
    app = desk
    app.media_tool = StubTool(fail=True)
    fake_clip(clip_dir(app) / "t.mp4", b"t")
    sidecar(app, "t.json", "cliptimeout", "Synthetic clip that timed out", "t.mp4")
    settle(app)
    c = check_of(app, "cliptimeout")
    assert c["status"] == "unreadable"
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    try:
        assert "다시 확인</button>" in client.get("/media").text
        assert client.post(f"/media/{c['asset_id']}/recheck").status_code == 403
        assert client.post(f"/media/{c['asset_id']}/recheck", headers=ORIGIN, follow_redirects=False).status_code == 303
        assert "확인 대기" in client.get("/media").text
        app.media_tool = StubTool()  # the cause went away
        app.check_media()
        assert check_of(app, "cliptimeout")["status"] == "ok"
    finally:
        client.close()


def test_unused_thumbnails_are_removed(desk):
    app = desk
    app.media_tool = StubTool()
    fake_clip(clip_dir(app) / "keep.mp4", b"keep")
    fake_clip(clip_dir(app) / "kill.mp4", b"kill")
    sidecar(app, "keep.json", "clipkeep", "Synthetic clip kept", "keep.mp4")
    sidecar(app, "kill.json", "clipkill2", "Synthetic clip withdrawn", "kill.mp4")
    settle(app)
    thumbs = app.cfg.paths.data_dir / "thumbs"
    keep, kill = (check_of(app, u)["thumb_path"] for u in ("clipkeep", "clipkill2"))
    stray = thumbs / "stray_from_an_old_check.jpg"
    stray.write_bytes(b"old")
    other = thumbs / "notes.txt"  # never a .jpg: never touched
    other.write_text("x")
    app.db.execute("UPDATE article SET status = 'killed' WHERE source_uri = 'clipkill2'")
    assert app.cleanup_thumbs() == 2
    assert (app.cfg.paths.data_dir / keep).is_file() and not (app.cfg.paths.data_dir / kill).exists()
    assert not stray.exists() and other.exists()


def test_page_says_when_it_is_capped_and_the_sheet_is_complete(desk, monkeypatch):
    from newsmon.web.service import Service
    app = desk
    app.media_tool = StubTool()
    for i in range(3):
        fake_clip(clip_dir(app) / f"c{i}.mp4", f"c{i}".encode())
        sidecar(app, f"c{i}.json", f"clipcap{i}", f"Synthetic capped clip {i}", f"c{i}.mp4")
    settle(app)
    monkeypatch.setattr(Service, "CLIP_PAGE", 2)
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    try:
        page = client.get("/media").text
        assert page.count('data-asset-id="') == 2 and "최근 2건만 표시" in page
        monkeypatch.setattr(Service, "CLIP_PAGE", 3)  # exactly as many clips as the page holds: no cap note
        assert "건만 표시" not in client.get("/media").text
        assert sum("Synthetic capped clip" in line for line in client.get("/media.csv").text.splitlines()) == 3
    finally:
        client.close()


def test_recheck_never_touches_a_filed_clip(desk):
    app = desk
    app.media_tool = StubTool(faults={"silence": [(1.0, 3.0)]})
    fake_clip(clip_dir(app) / "f.mp4", b"f")
    sidecar(app, "f.json", "clipfiled", "Synthetic filed clip", "f.mp4")
    settle(app)
    asset = check_of(app, "clipfiled")["asset_id"]
    client = TestClient(create_app(app), base_url="http://127.0.0.1:8765")
    try:
        client.post(f"/media/{asset}/filed", headers=ORIGIN)
        assert client.post(f"/media/{asset}/recheck", headers=ORIGIN).status_code == 404
        assert check_of(app, "clipfiled")["ingest_state"] == "filed"
    finally:
        client.close()
