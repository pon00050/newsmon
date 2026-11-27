"""In-app alerts and feed incidents (M1 v1: FR-21 in-app part, FR-04 "N consecutive failures").

Idempotent by construction: one alert per (kind, article) ever, and at most one open incident per feed, so re-running a
cycle raises nothing new (NFR-05). Alerts go to primary articles only, so a later duplicate joins its group silently.
"""
from __future__ import annotations

from newsmon.repo.base import BaseRepo
from newsmon.repo.sources import poll_finals

ALERT_KINDS = ("flash", "watch", "feed_incident")
STATUSES = ("new", "acknowledged", "dismissed")


class AlertRepo(BaseRepo):
    # --- raising ---------------------------------------------------------------------------------------------------------
    def raise_for_band(self, kind: str, band: str, reason: str, *, since: str, now_s: str, limit: int = 50) -> int:
        """Alert every live, primary, unflagged article first seen since `since` whose final band is `band` and which has
        no `kind` alert yet. Newest first, at most `limit` per call."""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO alert (workspace_id, kind, severity, article_id, reason, status, created_utc) "
            "SELECT a.workspace_id, ?, ?, a.article_id, ?, 'new', ? FROM article a WHERE a.workspace_id = ? "
            "AND a.final_band = ? AND a.status <> 'killed' AND a.dup_of IS NULL AND COALESCE(a.regex_prefilter_hit, 0) = 0 "
            "AND a.first_seen_utc >= ? AND NOT EXISTS (SELECT 1 FROM alert x WHERE x.workspace_id = a.workspace_id "
            "AND x.kind = ? AND x.article_id = a.article_id) ORDER BY a.first_seen_utc DESC LIMIT ?",
            (kind, "high" if kind == "flash" else "normal", reason, now_s, self.workspace_id, band, since, kind, limit))
        return cur.rowcount

    def raise_for_articles(self, kind: str, article_ids: list[int], reason: str, *, since: str, after: str, now_s: str,
                           limit: int = 50) -> int:
        """Alert these articles (a saved search's new matches) under the same rules as band alerts: live, primary,
        unflagged, first seen at or after `since` (the window) and strictly after `after` (when the search was saved),
        one alert per kind and item."""
        import json
        if not article_ids:
            return 0
        # a match that is a duplicate (a later copy or a same-source update such as "(종합)") alerts its primary: the
        # new match is what the monitor needs to hear about, and the queue shows the group under the primary
        return self.db.execute(
            "INSERT OR IGNORE INTO alert (workspace_id, kind, severity, article_id, reason, status, created_utc) "
            "SELECT p.workspace_id, ?, 'normal', p.article_id, ?, 'new', ? FROM article m "
            "JOIN article p ON p.article_id = COALESCE(m.dup_of, m.article_id) AND p.workspace_id = m.workspace_id "
            "WHERE m.workspace_id = ? AND m.article_id IN (SELECT value FROM json_each(?)) AND m.status <> 'killed' "
            "AND COALESCE(m.regex_prefilter_hit, 0) = 0 AND m.first_seen_utc >= ? AND m.first_seen_utc > ? "
            "AND p.status <> 'killed' AND p.dup_of IS NULL AND COALESCE(p.regex_prefilter_hit, 0) = 0 "
            "AND NOT EXISTS (SELECT 1 FROM alert x WHERE x.workspace_id = p.workspace_id AND x.kind = ? "
            "  AND x.article_id = p.article_id) "
            "GROUP BY p.article_id ORDER BY max(m.first_seen_utc) DESC LIMIT ?",
            (kind, reason, now_s, self.workspace_id, json.dumps(article_ids), since, after, kind, limit)).rowcount

    def open_incidents(self, source_key: str | None = None) -> list[dict]:
        """Feeds in an open `failing` incident (the search page's banner, FR-20), optionally for one source."""
        where, params = "", [self.workspace_id]
        if source_key:
            where, params = " AND s.key = ?", [self.workspace_id, source_key]
        return [dict(r) for r in self.db.query(
            "SELECT s.key, s.name, i.opened_utc, i.detail FROM incident i JOIN feed f ON f.feed_id = i.feed_id "
            "JOIN source s ON s.source_id = f.source_id WHERE i.workspace_id = ? AND i.closed_utc IS NULL "
            "AND i.kind = 'failing' AND f.active = 1 AND s.active = 1" + where +
            " ORDER BY s.key", params)]

    def update_incidents(self, *, failures: int, now_s: str) -> tuple[int, int]:
        """Open a `failing` incident for each active feed whose last `failures` runs all failed, and close open ones whose
        latest run succeeded. Each opening and closing raises one `feed_incident` alert. Returns (opened, closed)."""
        opened = closed = 0
        feeds = self.db.query("SELECT f.feed_id, s.name FROM feed f JOIN source s ON s.source_id = f.source_id "
                              "WHERE f.workspace_id = ? AND f.active = 1 AND s.active = 1", (self.workspace_id,))
        for r in self.db.query(  # a feed switched off while failing: its incident ends here, with one closing alert
                "SELECT i.incident_id, s.name FROM incident i JOIN feed f ON f.feed_id = i.feed_id JOIN source s ON "
                "s.source_id = f.source_id WHERE i.workspace_id = ? AND i.closed_utc IS NULL AND (f.active = 0 OR s.active = 0)",
                (self.workspace_id,)):
            with self.db.tx():
                if self.db.execute("UPDATE incident SET closed_utc = ? WHERE incident_id = ? AND workspace_id = ? "
                                   "AND closed_utc IS NULL", (now_s, r["incident_id"], self.workspace_id)).rowcount:
                    self._incident_alert(r["incident_id"], "normal", f"피드 비활성화로 장애 종료: {r['name']}", now_s)
                    closed += 1
        for f in feeds:
            runs = self._last_polls(f["feed_id"], failures)
            open_id = self.db.scalar("SELECT incident_id FROM incident WHERE workspace_id = ? AND feed_id = ? AND "
                                     "closed_utc IS NULL", (self.workspace_id, f["feed_id"]))
            if open_id is None and len(runs) == failures and all(r["status"] == "error" for r in runs):
                last = runs[0]
                detail = f"연속 {failures}회 실패 · {last['error_class'] or '-'}: {(last['error_detail'] or '')[:200]}"
                with self.db.tx():
                    cur = self.db.execute("INSERT OR IGNORE INTO incident (workspace_id, feed_id, kind, opened_utc, "
                                          "detail) VALUES (?, ?, 'failing', ?, ?)",
                                          (self.workspace_id, f["feed_id"], now_s, detail))
                    if cur.rowcount:  # another process may have opened it first (one open incident per feed)
                        self._incident_alert(cur.lastrowid, "high", f"피드 장애: {f['name']} — {detail}", now_s)
                        opened += 1
            elif open_id is not None and runs and runs[0]["status"] != "error":
                with self.db.tx():
                    if self.db.execute("UPDATE incident SET closed_utc = ? WHERE incident_id = ? AND workspace_id = ? "
                                       "AND closed_utc IS NULL", (now_s, open_id, self.workspace_id)).rowcount:
                        self._incident_alert(open_id, "normal", f"피드 복구: {f['name']}", now_s)
                        closed += 1
        return opened, closed

    def _last_polls(self, feed_id: int, n: int) -> list[dict]:
        """The final attempt of each of the last `n` polls, newest first (see `poll_finals`)."""
        rows = self.db.query("SELECT status, error_class, error_detail, attempt FROM fetch_run WHERE workspace_id = ? AND "
                             "feed_id = ? ORDER BY run_id DESC LIMIT ?", (self.workspace_id, feed_id, n * 10))
        return [dict(r) for r in poll_finals(rows)[:n]]

    def _incident_alert(self, incident_id: int, severity: str, reason: str, now_s: str) -> None:
        self.db.execute("INSERT INTO alert (workspace_id, kind, severity, incident_id, reason, status, created_utc) "
                        "VALUES (?, 'feed_incident', ?, ?, ?, 'new', ?)",
                        (self.workspace_id, severity, incident_id, reason, now_s))

    # --- reading ---------------------------------------------------------------------------------------------------------
    _SELECT = ("SELECT al.alert_id, al.kind, al.severity, al.reason, al.status, al.created_utc, al.article_id, "
               "al.incident_id, a.uid, a.status AS article_status, a.final_band, a.restrictions, a.licence_snapshot, "
               "a.canonical_url, a.synthetic, s.key AS source_key, s.name AS source_name, r.headline, i.closed_utc "
               "FROM alert al LEFT JOIN article a ON a.article_id = al.article_id "
               "LEFT JOIN source s ON s.source_id = a.source_id "
               "LEFT JOIN article_revision r ON r.revision_id = a.current_revision_id "
               "LEFT JOIN incident i ON i.incident_id = al.incident_id WHERE al.workspace_id = ? ")

    def list(self, *, statuses: tuple[str, ...] = STATUSES, limit: int = 200) -> list[dict]:
        marks = ",".join("?" * len(statuses))
        return [dict(r) for r in self.db.query(
            self._SELECT + f"AND al.status IN ({marks}) ORDER BY al.alert_id DESC LIMIT ?",
            (self.workspace_id, *statuses, limit))]

    def after(self, alert_id: int, limit: int = 20) -> list[dict]:
        return [dict(r) for r in self.db.query(
            self._SELECT + "AND al.alert_id > ? AND al.status = 'new' ORDER BY al.alert_id LIMIT ?",
            (self.workspace_id, alert_id, limit))]

    def new_count(self) -> int:
        return self.db.scalar("SELECT count(*) FROM alert WHERE workspace_id = ? AND status = 'new'", (self.workspace_id,))

    def last_id(self) -> int:
        return self.db.scalar("SELECT COALESCE(max(alert_id), 0) FROM alert WHERE workspace_id = ?", (self.workspace_id,))

    def set_status(self, alert_id: int, status: str) -> bool:
        if status not in STATUSES:
            raise ValueError(f"unknown alert status {status!r}")
        return self.db.execute("UPDATE alert SET status = ? WHERE alert_id = ? AND workspace_id = ?",
                               (status, alert_id, self.workspace_id)).rowcount > 0

    def acknowledge_all(self) -> int:
        return self.db.execute("UPDATE alert SET status = 'acknowledged' WHERE workspace_id = ? AND status = 'new'",
                               (self.workspace_id,)).rowcount
