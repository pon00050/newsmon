"""Wire footage checks and ingest tracking (duty 2 "외신 영상 분류작업 및 인제스트", v1).

A clip is a `media_asset` (written when a sidecar names it, hashed when the file itself arrives in the watched folder).
Its file is found through the inbox ledger, never through the sidecar's own path text. One `media_check` row per asset,
for the file hash it was checked at: a new hash means a new file, so it is checked again and its ingest mark resets.
"""
from __future__ import annotations

import json

from newsmon.repo.base import BaseRepo

_ASSET = ("FROM media_asset m JOIN article a ON a.article_id = m.article_id "
          "JOIN source s ON s.source_id = a.source_id "
          "JOIN article_revision r ON r.revision_id = a.current_revision_id "
          "LEFT JOIN media_check c ON c.asset_id = m.asset_id "
          "WHERE a.workspace_id = ? AND m.kind IN ('video', 'audio') ")


class MediaRepo(BaseRepo):
    def pending(self, limit: int = 5) -> list[dict]:
        """Clips whose file has arrived (hashed) and has not been checked at that hash. Newest first. Each row carries
        the ledger path of the file and the directory feed it arrived through."""
        return [dict(r) for r in self.db.query(
            "SELECT m.asset_id, m.href, m.sha256, a.article_id, a.status, a.restrictions, a.licence_snapshot, "
            "l.rel_path, f.url_or_path AS feed_path "
            "FROM media_asset m JOIN article a ON a.article_id = m.article_id "
            "LEFT JOIN media_check c ON c.asset_id = m.asset_id "
            "JOIN inbox_ledger l ON l.sha256 = m.sha256 AND l.status IN ('media', 'gone') "
            "JOIN feed f ON f.feed_id = l.feed_id AND f.workspace_id = a.workspace_id "
            "WHERE a.workspace_id = ? AND m.kind IN ('video', 'audio') AND m.sha256 IS NOT NULL "
            "AND (c.asset_id IS NULL OR c.sha256 <> m.sha256) "
            "AND l.rowid = (SELECT max(l2.rowid) FROM inbox_ledger l2 JOIN feed f2 ON f2.feed_id = l2.feed_id "
            "  WHERE l2.sha256 = m.sha256 AND l2.status IN ('media', 'gone') AND f2.workspace_id = a.workspace_id) "
            "ORDER BY m.asset_id DESC LIMIT ?", (self.workspace_id, limit))]

    def save(self, asset_id: int, sha256: str, now_s: str, *, status: str, probe: dict | None = None,
             faults: dict | None = None, notes: dict | None = None, thumb: str | None = None,
             error: str | None = None) -> None:
        dumps = lambda x: json.dumps(x, ensure_ascii=False) if x is not None else None  # noqa: E731
        with self.db.tx():
            self.db.execute(
                "INSERT INTO media_check (asset_id, sha256, checked_utc, status, probe_json, faults_json, notes_json, "
                "thumb_path, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (asset_id) DO UPDATE SET "
                "ingest_state = CASE WHEN media_check.sha256 = excluded.sha256 THEN media_check.ingest_state "
                "  ELSE 'pending' END, "
                "ingest_by = CASE WHEN media_check.sha256 = excluded.sha256 THEN media_check.ingest_by ELSE NULL END, "
                "ingest_utc = CASE WHEN media_check.sha256 = excluded.sha256 THEN media_check.ingest_utc ELSE NULL END, "
                "sha256 = excluded.sha256, checked_utc = excluded.checked_utc, status = excluded.status, "
                "probe_json = excluded.probe_json, faults_json = excluded.faults_json, notes_json = excluded.notes_json, "
                "thumb_path = excluded.thumb_path, error = excluded.error",
                (asset_id, sha256, now_s, status, dumps(probe), dumps(faults), dumps(notes), thumb, error))
            if probe:
                v = probe.get("video") or {}
                self.db.execute("UPDATE media_asset SET duration_s = ?, width = ?, height = ? WHERE asset_id = ?",
                                (probe.get("duration_s"), v.get("width"), v.get("height"), asset_id))

    def list(self, limit: int = 200) -> list[dict]:
        rows = self.db.query(
            "SELECT m.asset_id, m.kind, m.href, m.sha256, m.size_bytes, m.recorded_utc, a.article_id, a.uid, a.status, "
            "a.restrictions, a.licence_snapshot, a.urgency, a.located, a.slugline, a.first_seen_utc, a.final_band, "
            "a.synthetic, a.canonical_url, s.key AS source_key, s.name AS source_name, r.headline, "
            "c.sha256 AS checked_sha, c.checked_utc, c.status AS check_status, c.probe_json, c.faults_json, c.notes_json, "
            "c.thumb_path, c.error, c.ingest_state, c.ingest_by, c.ingest_utc "
            + _ASSET + "ORDER BY m.asset_id DESC LIMIT ?", (self.workspace_id, limit))
        out = []
        for r in rows:
            d = dict(r)
            for k in ("probe_json", "faults_json", "notes_json"):
                d[k[:-5]] = json.loads(d.pop(k)) if d.get(k) else None
            out.append(d)
        return out

    def for_article(self, article_id: int) -> list[dict]:
        return [r for r in self.list(limit=1000) if r["article_id"] == article_id]

    def thumb(self, asset_id: int) -> dict | None:
        r = self.db.one("SELECT c.thumb_path, a.licence_snapshot, a.restrictions, a.status " + _ASSET + "AND m.asset_id = ?",
                        (self.workspace_id, asset_id))
        return dict(r) if r else None

    def set_ingest(self, asset_id: int, filed: bool, editor: str, now_s: str) -> bool:
        """Mark a checked clip as filed in the broadcaster's system (or undo). Only a clip that has been checked."""
        return self.db.execute(
            "UPDATE media_check SET ingest_state = ?, ingest_by = ?, ingest_utc = ? WHERE asset_id = ? AND asset_id IN "
            "(SELECT m.asset_id FROM media_asset m JOIN article a ON a.article_id = m.article_id WHERE a.workspace_id = ? "
            "AND a.status <> 'killed')",
            ("filed" if filed else "pending", editor if filed else None, now_s if filed else None, asset_id,
             self.workspace_id)).rowcount > 0

    def attention_count(self) -> int:
        """Clips a person should look at: faults, unreadable or missing files, not yet marked filed."""
        return self.db.scalar(
            "SELECT count(*) FROM media_check c JOIN media_asset m ON m.asset_id = c.asset_id JOIN article a ON "
            "a.article_id = m.article_id WHERE a.workspace_id = ? AND c.status IN ('needs_check','unreadable','missing') "
            "AND c.ingest_state = 'pending' AND a.status <> 'killed'", (self.workspace_id,))
