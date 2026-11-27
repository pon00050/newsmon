"""Sources, feeds, fetch runs, quarantine and the inbox ledger (all SQL for collection bookkeeping)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from newsmon.domain.models import LicenceFlags, PollResult, SourceRef
from newsmon.registry.loader import FEED_KINDS, SourceSpec
from newsmon.repo.base import BaseRepo

FLAG_COLS = ("storage", "display", "ai_processing", "external_ai_allowed", "permitted_ops", "redistribution",
             "licence_owner", "allowed_contexts", "third_party_processors_allowed", "authorised_users",
             "retention_days", "synthetic")


@dataclass(frozen=True)
class FeedRow:
    feed_id: int
    source_id: int
    source_key: str
    kind: str
    url_or_path: str
    poll_seconds: int
    etag: str | None
    last_modified: str | None
    next_due_utc: str | None


def poll_finals(rows) -> list:
    """From fetch_run rows ordered newest first, keep the final attempt of each poll. A retried poll writes one row per
    attempt (attempt 1, 2, ...), so counting rows would count one failed poll as several failures."""
    out, newer = [], None
    for r in rows:
        if newer is None or newer <= 1 or r["attempt"] >= newer:
            out.append(r)
        newer = r["attempt"]
    return out


class SourceRepo(BaseRepo):
    # --- registry sync ------------------------------------------------------------------------------------------------
    def upsert(self, spec: SourceSpec, *, active: bool, reason: str | None, endpoint: str, poll_seconds: int,
               now: str) -> int:
        f = spec.flags()
        vals = {
            "key": spec.key, "name": spec.name, "registrable_domain": spec.registrable_domain, "lang_default": spec.lang,
            "country": spec.country, "is_wire": int(spec.is_wire), "access_method": str(spec.access_method),
            "tos_url": spec.tos_url, "storage": str(f.storage), "display": str(f.display),
            "ai_processing": str(f.ai_processing), "external_ai_allowed": int(f.external_ai_allowed),
            "redistribution": str(f.redistribution), "licence_owner": str(f.licence_owner),
            "allowed_contexts": ",".join(sorted(f.allowed_contexts)), "retention_days": f.retention_days,
            "attribution_text": spec.attribution_text, "permitted_ops": json.dumps(sorted(f.permitted_ops)),
            "third_party_processors_allowed": int(f.third_party_processors_allowed),
            "authorised_users": f.authorised_users, "territory": spec.territory, "licence_holder": spec.licence_holder,
            "agreement_ref": spec.agreement_ref, "valid_until": spec.valid_until.isoformat() if spec.valid_until else None,
            "attested_by": spec.attested_by, "attested_on": spec.attested_on.isoformat() if spec.attested_on else None,
            "synthetic": int(spec.synthetic), "boilerplate_rules": json.dumps(spec.boilerplate_rules, ensure_ascii=False),
            "live_patterns": json.dumps(spec.live_patterns, ensure_ascii=False), "story_key_rule": spec.story_key_rule,
            "active": int(active), "inactive_reason": reason,
        }
        with self.db.tx():
            row = self.db.one("SELECT source_id FROM source WHERE workspace_id = ? AND key = ?", (self.workspace_id, spec.key))
            if row is None:
                self.db.execute(
                    "INSERT INTO source (workspace_id, key, name, registrable_domain, lang_default, country, is_wire, "
                    "access_method, tos_url, storage, display, ai_processing, external_ai_allowed, redistribution, "
                    "licence_owner, allowed_contexts, retention_days, attribution_text, permitted_ops, "
                    "third_party_processors_allowed, authorised_users, territory, licence_holder, agreement_ref, "
                    "valid_until, attested_by, attested_on, synthetic, boilerplate_rules, live_patterns, story_key_rule, "
                    "active, inactive_reason, created_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (self.workspace_id, *vals.values(), now))
                sid = self.db.scalar("SELECT source_id FROM source WHERE workspace_id = ? AND key = ?",
                                     (self.workspace_id, spec.key))
            else:
                sid = row[0]
                self.db.execute(
                    "UPDATE source SET name = ?, registrable_domain = ?, lang_default = ?, country = ?, is_wire = ?, "
                    "access_method = ?, tos_url = ?, storage = ?, display = ?, ai_processing = ?, external_ai_allowed = ?, "
                    "redistribution = ?, licence_owner = ?, allowed_contexts = ?, retention_days = ?, attribution_text = ?, "
                    "permitted_ops = ?, third_party_processors_allowed = ?, authorised_users = ?, territory = ?, "
                    "licence_holder = ?, agreement_ref = ?, valid_until = ?, attested_by = ?, attested_on = ?, "
                    "synthetic = ?, boilerplate_rules = ?, live_patterns = ?, story_key_rule = ?, active = ?, "
                    "inactive_reason = ? WHERE source_id = ? AND workspace_id = ?",
                    (*list(vals.values())[1:], sid, self.workspace_id))
            kind = FEED_KINDS.get(str(spec.access_method), "rss")
            feed = self.db.one("SELECT feed_id FROM feed WHERE workspace_id = ? AND source_id = ?", (self.workspace_id, sid))
            if feed is None:
                self.db.execute("INSERT INTO feed (workspace_id, source_id, kind, url_or_path, discovered_from, poll_seconds, "
                                "active) VALUES (?, ?, ?, ?, 'sources.yaml', ?, ?)",
                                (self.workspace_id, sid, kind, endpoint, poll_seconds, int(active)))
            else:
                self.db.execute("UPDATE feed SET kind = ?, url_or_path = ?, poll_seconds = ?, active = ? "
                                "WHERE feed_id = ? AND workspace_id = ?",
                                (kind, endpoint, poll_seconds, int(active), feed[0], self.workspace_id))
        return sid

    def deactivate_missing(self, keys: set[str]) -> None:
        for row in self.db.query("SELECT source_id, key FROM source WHERE workspace_id = ? AND active = 1",
                                 (self.workspace_id,)):
            if row["key"] not in keys:
                with self.db.tx():
                    self.db.execute("UPDATE source SET active = 0, inactive_reason = 'removed from sources.yaml' "
                                    "WHERE source_id = ? AND workspace_id = ?", (row["source_id"], self.workspace_id))
                    self.db.execute("UPDATE feed SET active = 0 WHERE source_id = ? AND workspace_id = ?",
                                    (row["source_id"], self.workspace_id))

    def set_inactive(self, source_id: int, reason: str) -> None:
        with self.db.tx():
            self.db.execute("UPDATE source SET active = 0, inactive_reason = ? WHERE source_id = ? AND workspace_id = ?",
                            (reason, source_id, self.workspace_id))
            self.db.execute("UPDATE feed SET active = 0 WHERE source_id = ? AND workspace_id = ?",
                            (source_id, self.workspace_id))

    # --- reads -----------------------------------------------------------------------------------------------------------
    def source_ref(self, source_id: int) -> SourceRef:
        r = self.db.one("SELECT * FROM source WHERE source_id = ? AND workspace_id = ?", (source_id, self.workspace_id))
        return self._ref(r)

    def source_by_key(self, key: str) -> SourceRef | None:
        r = self.db.one("SELECT * FROM source WHERE key = ? AND workspace_id = ?", (key, self.workspace_id))
        return self._ref(r) if r else None

    def valid_until(self, source_id: int) -> date | None:
        v = self.db.scalar("SELECT valid_until FROM source WHERE source_id = ? AND workspace_id = ?",
                           (source_id, self.workspace_id))
        return date.fromisoformat(v) if v else None

    def source_rules(self, source_id: int) -> tuple[list[str], list[str], str | None]:
        r = self.db.one("SELECT boilerplate_rules, live_patterns, story_key_rule FROM source WHERE source_id = ? "
                        "AND workspace_id = ?", (source_id, self.workspace_id))
        return json.loads(r[0] or "[]"), json.loads(r[1] or "[]"), r[2]

    def keys(self) -> set[str]:
        return {r[0] for r in self.db.query("SELECT key FROM source WHERE workspace_id = ?", (self.workspace_id,))}

    @staticmethod
    def _ref(r) -> SourceRef:
        flags = LicenceFlags(
            storage=r["storage"], display=r["display"], ai_processing=r["ai_processing"],
            external_ai_allowed=bool(r["external_ai_allowed"]), permitted_ops=frozenset(json.loads(r["permitted_ops"])),
            redistribution=r["redistribution"], licence_owner=r["licence_owner"],
            allowed_contexts=frozenset(r["allowed_contexts"].split(",")),
            third_party_processors_allowed=bool(r["third_party_processors_allowed"]),
            authorised_users=r["authorised_users"], retention_days=r["retention_days"], synthetic=bool(r["synthetic"]))
        return SourceRef(source_id=r["source_id"], key=r["key"], name=r["name"], access_method=r["access_method"],
                         is_wire=bool(r["is_wire"]), lang_default=r["lang_default"],
                         registrable_domain=r["registrable_domain"], flags=flags, active=bool(r["active"]))

    def active_feeds(self) -> list[FeedRow]:
        rows = self.db.query(
            "SELECT f.feed_id, f.source_id, s.key, f.kind, f.url_or_path, f.poll_seconds, f.etag, f.last_modified, "
            "f.next_due_utc FROM feed f JOIN source s ON s.source_id = f.source_id "
            "WHERE f.workspace_id = ? AND f.active = 1 AND s.active = 1 ORDER BY s.key", (self.workspace_id,))
        return [FeedRow(*r) for r in rows]

    # --- fetch runs -----------------------------------------------------------------------------------------------------
    def record_run(self, feed_id: int, started: str, finished: str, r: PollResult, entries: int | None,
                   new_articles: int | None) -> int:
        cur = self.db.execute(
            "INSERT INTO fetch_run (workspace_id, feed_id, started_utc, finished_utc, status, http_status, bytes, entries, "
            "new_articles, error_class, error_detail, attempt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (self.workspace_id, feed_id, started, finished, str(r.status), r.http_status, r.bytes, entries, new_articles,
             str(r.error_class) if r.error_class else None, r.error_detail, r.attempts))
        return cur.lastrowid

    def update_run_counts(self, run_id: int, *, entries: int, new_articles: int, status: str | None = None,
                          error_class: str | None = None, error_detail: str | None = None) -> None:
        if status:
            self.db.execute("UPDATE fetch_run SET entries = ?, new_articles = ?, status = ?, error_class = ?, "
                            "error_detail = ? WHERE run_id = ? AND workspace_id = ?",
                            (entries, new_articles, status, error_class, error_detail, run_id, self.workspace_id))
        else:
            self.db.execute("UPDATE fetch_run SET entries = ?, new_articles = ? WHERE run_id = ? AND workspace_id = ?",
                            (entries, new_articles, run_id, self.workspace_id))

    def save_validators(self, feed_id: int, etag: str | None, last_modified: str | None) -> None:
        self.db.execute("UPDATE feed SET etag = ?, last_modified = ? WHERE feed_id = ? AND workspace_id = ?",
                        (etag, last_modified, feed_id, self.workspace_id))

    def feed_cursor(self, feed_id: int) -> str | None:
        return self.db.scalar("SELECT cursor FROM feed WHERE feed_id = ? AND workspace_id = ?", (feed_id, self.workspace_id))

    def save_cursor(self, feed_id: int, cursor: str) -> None:
        self.db.execute("UPDATE feed SET cursor = ? WHERE feed_id = ? AND workspace_id = ?",
                        (cursor, feed_id, self.workspace_id))

    def set_next_due(self, feed_id: int, when: str) -> None:
        self.db.execute("UPDATE feed SET next_due_utc = ? WHERE feed_id = ? AND workspace_id = ?",
                        (when, feed_id, self.workspace_id))

    def quarantine(self, run_id: int | None, raw_ref: str, reason: str, now: str) -> None:
        self.db.execute("INSERT INTO quarantine (workspace_id, run_id, raw_ref, reason, created_utc) VALUES (?, ?, ?, ?, ?)",
                        (self.workspace_id, run_id, raw_ref, reason[:500], now))

    # --- inbox ledger (child of feed) -------------------------------------------------------------------------------------
    def ledger_has(self, feed_id: int, rel_path: str, sha256: str) -> bool:
        return self.db.one("SELECT 1 FROM inbox_ledger l JOIN feed f ON f.feed_id = l.feed_id WHERE l.feed_id = ? "
                           "AND f.workspace_id = ? AND l.rel_path = ? AND l.sha256 = ?",
                           (feed_id, self.workspace_id, rel_path, sha256)) is not None

    def ledger_record(self, feed_id: int, rel_path: str, size: int, mtime_ns: int, sha256: str, fmt: str | None,
                      status: str, reason: str | None, now: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO inbox_ledger (feed_id, rel_path, size, mtime_ns, sha256, detected_format, "
                        "status, reason, seen_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (feed_id, rel_path, size, mtime_ns, sha256, fmt, status, reason, now))

    def ledger_present(self, feed_id: int) -> list[tuple[str, str]]:
        return [(r[0], r[1]) for r in self.db.query(
            "SELECT rel_path, sha256 FROM inbox_ledger WHERE feed_id = ? AND status <> 'gone'", (feed_id,))]

    def ledger_mark_gone(self, feed_id: int, rel_path: str, sha256: str) -> None:
        self.db.execute("UPDATE inbox_ledger SET status = 'gone' WHERE feed_id = ? AND rel_path = ? AND sha256 = ?",
                        (feed_id, rel_path, sha256))

    # --- status (UI-8 subset, diagnostics) ------------------------------------------------------------------------------
    def status_rows(self) -> list[dict]:
        rows = self.db.query(
            "SELECT s.source_id, s.key, s.name, s.access_method, s.active, s.inactive_reason, s.storage, s.display, "
            "s.synthetic, f.feed_id, f.url_or_path, f.poll_seconds, f.next_due_utc, "
            "(SELECT count(*) FROM article a WHERE a.source_id = s.source_id AND a.workspace_id = s.workspace_id) AS articles "
            "FROM source s LEFT JOIN feed f ON f.source_id = s.source_id AND f.workspace_id = s.workspace_id "
            "WHERE s.workspace_id = ? ORDER BY s.active DESC, s.key", (self.workspace_id,))
        out = []
        for r in rows:
            d = dict(r)
            runs = poll_finals(self.db.query(
                "SELECT status, error_class, error_detail, http_status, started_utc, entries, new_articles, attempt "
                "FROM fetch_run WHERE feed_id = ? AND workspace_id = ? ORDER BY run_id DESC LIMIT 60",
                (r["feed_id"], self.workspace_id))) if r["feed_id"] else []
            d["last_run"] = dict(runs[0]) if runs else None
            streak = 0
            for x in runs:
                if x["status"] != "error":
                    break
                streak += 1
            d["error_streak"] = streak
            d["last_success_utc"] = self.db.scalar(
                "SELECT max(started_utc) FROM fetch_run WHERE feed_id = ? AND workspace_id = ? AND status <> 'error'",
                (r["feed_id"], self.workspace_id)) if r["feed_id"] else None
            out.append(d)
        return out

    def recent_runs(self, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self.db.query(
            "SELECT r.run_id, s.key, r.started_utc, r.status, r.http_status, r.error_class, r.error_detail, r.attempt, "
            "r.entries, r.new_articles FROM fetch_run r JOIN feed f ON f.feed_id = r.feed_id JOIN source s ON "
            "s.source_id = f.source_id WHERE r.workspace_id = ? ORDER BY r.run_id DESC LIMIT ?", (self.workspace_id, limit))]

    def recent_quarantine(self, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self.db.query(
            "SELECT q_id, run_id, raw_ref, reason, created_utc FROM quarantine WHERE workspace_id = ? ORDER BY q_id DESC "
            "LIMIT ?", (self.workspace_id, limit))]
