"""Watched inbox (T-33) and media references (T-34): FR-28(a)-(f), FR-29(c)(e)."""
import hashlib
import shutil
from pathlib import Path

import pytest

from tests.support.instance import fill_inbox, make_app, mock_wire_sources
from tests.support.wire_recipes import WIRE_DIR, make_oversize, make_symlink_escape

pytestmark = pytest.mark.integration


def snapshot(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def demo(rep):
    return [f for f in rep.feeds if f.source_key == "mock_wire_demo"][0]


@pytest.mark.req("FR-28a", "FR-28b", "FR-28e", "RA-05")
def test_ingest_within_two_scans_then_nothing_new(tmp_path):
    app = make_app(tmp_path, None, mock_wire_sources(), with_inbox=True)
    try:
        copied = fill_inbox(app)
        root = app.resolve_inbox("inbox/mock_wire_demo")
        before = snapshot(root)
        assert len(copied) >= 18
        app.collect(force=True)
        second = demo(app.collect(force=True))
        assert second.entries == 20 and second.quarantined == 0
        ledger = app.db.query("SELECT status, count(*) FROM inbox_ledger GROUP BY status")
        assert dict((r[0], r[1]) for r in ledger) == {"ingested": 19, "media": 1}
        third = demo(app.collect(force=True))
        assert third.entries == 0 and third.new == 0
        assert snapshot(root) == before  # customer files untouched
        assert not list((tmp_path / "data").rglob("*.mp4"))  # media never copied (FR-29(e))
    finally:
        app.close()


@pytest.mark.req("FR-28c")
def test_file_being_written_waits(tmp_path):
    app = make_app(tmp_path, None, mock_wire_sources(), with_inbox=True)
    try:
        root = app.resolve_inbox("inbox/mock_wire_demo")
        src = WIRE_DIR / "inbox" / "plain" / "ptw_0005_philippines_shoal.txt"
        dst = root / "growing.txt"
        data = src.read_bytes()
        dst.write_bytes(data[: len(data) // 2])
        app.collect(force=True)
        with open(dst, "ab") as fh:  # still being written
            fh.write(data[len(data) // 2:])
        assert demo(app.collect(force=True)).entries == 0
        assert demo(app.collect(force=True)).entries == 1  # stable across two scans now
    finally:
        app.close()


@pytest.mark.req("FR-28d")
def test_symlink_escape_refused(tmp_path):
    app = make_app(tmp_path, None, mock_wire_sources(), with_inbox=True)
    try:
        root = app.resolve_inbox("inbox/mock_wire_demo")
        outside = tmp_path / "outside.txt"
        shutil.copy(WIRE_DIR / "inbox" / "plain" / "ptw_0005_philippines_shoal.txt", outside)
        link = make_symlink_escape(root, outside)
        if link is None:
            pytest.skip("the OS refused to create a symlink (Windows without developer mode); proven on Linux CI")
        app.collect(force=True)
        rep = demo(app.collect(force=True))
        assert rep.entries == 0 and rep.quarantined >= 1
        q = app.sources.recent_quarantine()
        assert any("io: symlink escapes" in x["reason"] for x in q)
    finally:
        app.close()


@pytest.mark.req("FR-28f")
def test_deleted_file_marked_gone_item_kept(tmp_path):
    app = make_app(tmp_path, None, mock_wire_sources(), with_inbox=True)
    try:
        fill_inbox(app)
        app.collect(force=True)
        app.collect(force=True)
        root = app.resolve_inbox("inbox/mock_wire_demo")
        (root / "plain" / "ptw_0005_philippines_shoal.txt").unlink()
        n = app.articles.counts()["articles"]
        app.collect(force=True)
        assert app.articles.counts()["articles"] == n
        assert app.db.scalar("SELECT status FROM inbox_ledger WHERE rel_path = 'plain/ptw_0005_philippines_shoal.txt'") == "gone"
    finally:
        app.close()


@pytest.mark.req("FR-29c", "RA-11")
def test_bad_files_quarantined_good_ones_ingested(tmp_path):
    app = make_app(tmp_path, None, mock_wire_sources(), with_inbox=True)
    try:
        root = app.resolve_inbox("inbox/mock_wire_demo")
        shutil.copytree(WIRE_DIR / "bad", root / "bad")
        shutil.copy(WIRE_DIR / "inbox" / "plain" / "ptw_0001_taiwan_quake_flash.txt", root / "good.txt")
        make_oversize(root / "huge.txt", app.settings.inbox.max_file_bytes + 10)
        app.collect(force=True)
        rep = demo(app.collect(force=True))
        assert rep.new == 1
        reasons = [q["reason"] for q in app.sources.recent_quarantine()]
        bad_count = sum(1 for p in (WIRE_DIR / "bad").rglob("*") if p.is_file())
        assert sum(r.startswith("parse:") for r in reasons) == bad_count
        assert any("oversize" in r for r in reasons)
        assert app.db.scalar("SELECT count(*) FROM inbox_ledger WHERE status = 'quarantined'") == bad_count + 1
        assert demo(app.collect(force=True)).quarantined == 0  # refused files are not re-reported every scan
    finally:
        app.close()


@pytest.mark.req("FR-29e")
def test_video_is_a_media_reference(tmp_path):
    app = make_app(tmp_path, None, mock_wire_sources(), with_inbox=True)
    try:
        fill_inbox(app)
        app.collect(force=True)
        app.collect(force=True)
        rows = app.db.query("SELECT kind, href, sha256, size_bytes FROM media_asset")
        assert len(rows) == 1
        mp4 = WIRE_DIR / "inbox" / "ninjs" / "a1b2c3d4e5f6--2--0c4d2e7a.mp4"
        assert tuple(rows[0]) == ("video", mp4.name, hashlib.sha256(mp4.read_bytes()).hexdigest(), mp4.stat().st_size)
    finally:
        app.close()


def test_missing_root_is_an_error_not_a_crash(tmp_path):
    app = make_app(tmp_path, None, mock_wire_sources(), with_inbox=False)
    try:
        rep = app.collect(force=True)
        assert {f.status for f in rep.feeds} == {"error"} and all(f.error_class == "io" for f in rep.feeds)
    finally:
        app.close()
