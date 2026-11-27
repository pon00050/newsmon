"""Saved searches (duty 4): a query and its filters that a monitor keeps watching, with "new since last opened" and an
optional watch alert for new matches."""
from __future__ import annotations

from newsmon.repo.base import BaseRepo

NAME_MAX, QUERY_MAX = 80, 200
_COLS = ("search_id, name, query, lang, source_key, band, hours, video_only, alert, created_by, created_utc, "
         "last_seen_utc, last_error")


class SearchRepo(BaseRepo):
    def add(self, *, name: str, query: str, lang: str | None, source_key: str | None, band: str | None,
            hours: int | None, video_only: bool, alert: bool, editor: str, now_s: str) -> int:
        return self.db.execute(
            "INSERT INTO saved_search (workspace_id, name, query, lang, source_key, band, hours, video_only, alert, "
            "created_by, created_utc, last_seen_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (self.workspace_id, name.strip()[:NAME_MAX], query.strip()[:QUERY_MAX], lang or None, source_key or None,
             band or None, hours or None, int(bool(video_only)), int(bool(alert)), editor, now_s, now_s)).lastrowid

    def all(self) -> list[dict]:
        return [dict(r) for r in self.db.query(f"SELECT {_COLS} FROM saved_search WHERE workspace_id = ? "
                                               "ORDER BY search_id", (self.workspace_id,))]

    def alerting(self) -> list[dict]:
        return [dict(r) for r in self.db.query(f"SELECT {_COLS} FROM saved_search WHERE workspace_id = ? AND alert = 1 "
                                               "ORDER BY search_id", (self.workspace_id,))]

    def get(self, search_id: int) -> dict | None:
        r = self.db.one(f"SELECT {_COLS} FROM saved_search WHERE workspace_id = ? AND search_id = ?",
                        (self.workspace_id, search_id))
        return dict(r) if r else None

    def mark_seen(self, search_id: int, now_s: str) -> None:
        self.db.execute("UPDATE saved_search SET last_seen_utc = ? WHERE workspace_id = ? AND search_id = ?",
                        (now_s, self.workspace_id, search_id))

    def set_alert(self, search_id: int, on: bool) -> bool:
        return self.db.execute("UPDATE saved_search SET alert = ? WHERE workspace_id = ? AND search_id = ?",
                               (int(on), self.workspace_id, search_id)).rowcount > 0

    def set_error(self, search_id: int, error: str | None) -> None:
        self.db.execute("UPDATE saved_search SET last_error = ? WHERE workspace_id = ? AND search_id = ?",
                        ((error or None) and error[:300], self.workspace_id, search_id))

    def delete(self, search_id: int) -> bool:
        return self.db.execute("DELETE FROM saved_search WHERE workspace_id = ? AND search_id = ?",
                               (self.workspace_id, search_id)).rowcount > 0
