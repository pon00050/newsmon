"""SQL for the optional AI layer (Release A.1): interpretations (cache + audit of fields sent), the daily spend ledger,
operator switches, candidate selection and per-article AI status."""
from __future__ import annotations

import json

from newsmon.repo.base import BaseRepo

BAND_RANK_SQL = "CASE COALESCE(a.rule_band, 'drop') WHEN 'flash' THEN 3 WHEN 'report' THEN 2 WHEN 'review' THEN 1 ELSE 0 END"


class AIRepo(BaseRepo):
    # --- operator switches -------------------------------------------------------------------------------------------
    def get_state(self, key: str, default: str | None = None) -> str | None:
        v = self.db.scalar("SELECT value FROM app_state WHERE workspace_id = ? AND key = ?", (self.workspace_id, key))
        return default if v is None else v

    def set_state(self, key: str, value: str, now: str) -> None:
        self.db.execute("INSERT INTO app_state (workspace_id, key, value, updated_utc) VALUES (?, ?, ?, ?) "
                        "ON CONFLICT (workspace_id, key) DO UPDATE SET value = excluded.value, updated_utc = excluded.updated_utc",
                        (self.workspace_id, key, value, now))

    # --- spend ledger --------------------------------------------------------------------------------------------------
    def spent(self, day: str) -> float:
        return float(self.db.scalar("SELECT usd FROM spend_day WHERE workspace_id = ? AND day = ?", (self.workspace_id, day))
                     or 0.0)

    def add_spend(self, day: str, usd: float, cap: float) -> float:
        with self.db.tx():
            self.db.execute("INSERT INTO spend_day (workspace_id, day, usd, cap_usd, capped) VALUES (?, ?, 0, ?, 0) "
                            "ON CONFLICT (workspace_id, day) DO NOTHING", (self.workspace_id, day, cap))
            self.db.execute("UPDATE spend_day SET usd = usd + ?, cap_usd = ?, capped = CASE WHEN usd + ? >= ? THEN 1 ELSE "
                            "capped END WHERE workspace_id = ? AND day = ?", (usd, cap, usd, cap, self.workspace_id, day))
        return self.spent(day)

    def capped(self, day: str) -> bool:
        return bool(self.db.scalar("SELECT capped FROM spend_day WHERE workspace_id = ? AND day = ?",
                                   (self.workspace_id, day)))

    def mark_capped(self, day: str, cap: float) -> None:
        self.db.execute("INSERT INTO spend_day (workspace_id, day, usd, cap_usd, capped) VALUES (?, ?, 0, ?, 1) "
                        "ON CONFLICT (workspace_id, day) DO UPDATE SET capped = 1", (self.workspace_id, day, cap))

    def usage_totals(self) -> dict:
        r = self.db.one("SELECT count(*), COALESCE(sum(input_tokens), 0), COALESCE(sum(output_tokens), 0), "
                        "COALESCE(sum(cost_usd), 0) FROM ai_interpretation WHERE workspace_id = ?", (self.workspace_id,))
        return {"calls": r[0], "input_tokens": r[1], "output_tokens": r[2], "cost_usd": round(r[3], 6)}

    # --- selection ------------------------------------------------------------------------------------------------------
    def candidates(self, *, min_rank: int, limit: int, sources: tuple[str, ...] = ()) -> list[dict]:
        """Live, primary (non-duplicate) articles still pending enrichment, best rule band first."""
        where = ["a.workspace_id = ?", "a.status <> 'killed'", "a.dup_of IS NULL", "a.enrichment_status = 'pending'",
                 BAND_RANK_SQL + " >= ?"]
        params: list = [self.workspace_id, min_rank]
        if sources:
            where.append("s.key IN (SELECT value FROM json_each(?))")
            params.append(json.dumps(list(sources)))
        params.append(limit)
        return [dict(r) for r in self.db.query(
            "SELECT a.article_id FROM article a JOIN source s ON s.source_id = a.source_id WHERE " + " AND ".join(where) +
            " ORDER BY " + BAND_RANK_SQL + " DESC, COALESCE(a.rule_score, 0) DESC, a.first_seen_utc DESC LIMIT ?", params)]

    def article_input(self, article_id: int) -> dict | None:
        r = self.db.one(
            "SELECT a.article_id, a.uid, a.lang, a.published_utc, a.current_revision_id, a.licence_snapshot, a.restrictions, "
            "a.status, a.regex_prefilter_hit, s.key AS source_key, s.name AS source_name, r.headline, r.description_text, r.body_text "
            "FROM article a JOIN source s ON s.source_id = a.source_id JOIN article_revision r ON "
            "r.revision_id = a.current_revision_id WHERE a.article_id = ? AND a.workspace_id = ?",
            (article_id, self.workspace_id))
        return dict(r) if r else None

    def article_id_for_uid(self, uid: str) -> int | None:
        return self.db.scalar("SELECT article_id FROM article WHERE uid = ? AND workspace_id = ?", (uid, self.workspace_id))

    def set_status(self, article_id: int, status: str) -> None:
        self.db.execute("UPDATE article SET enrichment_status = ? WHERE article_id = ? AND workspace_id = ?",
                        (status, article_id, self.workspace_id))

    def reset_pending(self, article_id: int) -> None:
        self.set_status(article_id, "pending")

    def set_prefilter(self, article_id: int, hit: bool) -> None:
        self.db.execute("UPDATE article SET regex_prefilter_hit = ? WHERE article_id = ? AND workspace_id = ?",
                        (int(hit), article_id, self.workspace_id))

    def unscreened(self) -> list[dict]:  # articles not yet screened by the injection pre-filter (backfill)
        return [dict(r) for r in self.db.query(
            "SELECT a.article_id, r.headline, r.description_text, r.body_text FROM article a JOIN article_revision r ON "
            "r.revision_id = a.current_revision_id WHERE a.workspace_id = ? AND a.regex_prefilter_hit = 0 AND "
            "a.article_id > ?", (self.workspace_id, int(self.get_state("prefilter_last_id", "0"))))]

    # --- interpretations -------------------------------------------------------------------------------------------------
    def cached(self, revision_id: int, model: str, prompt_version: str, schema_version: str, input_sha: str) -> dict | None:
        r = self.db.one("SELECT interp_id, output_json, validation_status, injection_suspected FROM ai_interpretation "
                        "WHERE target_kind = 'revision' AND target_id = ? AND task = 'enrich' AND model = ? AND "
                        "prompt_version = ? AND schema_version = ? AND input_sha256 = ? AND workspace_id = ?",
                        (revision_id, model, prompt_version, schema_version, input_sha, self.workspace_id))
        return dict(r) if r else None

    def save_interpretation(self, *, revision_id: int, output: dict | str, provider: str, endpoint_kind: str, model: str,
                            prompt_version: str, schema_version: str, input_sha: str, fields_sent: list[str],
                            validation_status: str, injection: bool, prefilter: bool, input_tokens: int,
                            output_tokens: int, cost: float, latency_ms: int, now: str) -> int:
        cur = self.db.execute(
            "INSERT INTO ai_interpretation (workspace_id, target_kind, target_id, task, output_json, provider, "
            "endpoint_kind, model, prompt_version, schema_version, input_sha256, fields_sent, validation_status, "
            "injection_suspected, regex_prefilter_hit, input_tokens, output_tokens, cost_usd, latency_ms, created_utc) "
            "VALUES (?, 'revision', ?, 'enrich', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (self.workspace_id, revision_id, json.dumps(output, ensure_ascii=False) if not isinstance(output, str) else output,
             provider, endpoint_kind, model, prompt_version, schema_version, input_sha, json.dumps(fields_sent),
             validation_status, int(injection), int(prefilter), input_tokens, output_tokens, cost, latency_ms, now))
        return cur.lastrowid

    def latest_for_articles(self, article_ids: list[int] | None = None) -> dict[int, dict]:
        """Newest valid interpretation of each article's current revision."""
        only, params = "", [self.workspace_id]
        if article_ids is not None:
            only = " AND a.article_id IN (SELECT value FROM json_each(?))"
            params.append(json.dumps(list(article_ids)))
        rows = self.db.query(
            "SELECT a.article_id, i.output_json, i.model, i.prompt_version, i.validation_status, i.injection_suspected, "
            "i.created_utc FROM article a JOIN ai_interpretation i ON i.target_kind = 'revision' AND "
            "i.target_id = a.current_revision_id AND i.task = 'enrich' WHERE a.workspace_id = ? AND "
            "i.validation_status IN ('valid', 'retried_valid')" + only + " ORDER BY i.interp_id", params)
        return {r[0]: {"output": json.loads(r[1]), "model": r[2], "prompt_version": r[3], "validation_status": r[4],
                       "injection_suspected": bool(r[5]), "created_utc": r[6]} for r in rows}

    def assessed(self) -> dict[int, tuple[str, str, str, str]]:
        """article_id -> (model, prompt version, schema version, input hash) of the newest valid assessment of the
        article's current revision, for articles that have not been withdrawn."""
        rows = self.db.query(
            "SELECT a.article_id, i.model, i.prompt_version, i.schema_version, i.input_sha256 FROM article a JOIN "
            "ai_interpretation i ON i.target_kind = 'revision' AND i.target_id = a.current_revision_id AND "
            "i.task = 'enrich' WHERE a.workspace_id = ? AND a.status <> 'killed' AND "
            "i.validation_status IN ('valid', 'retried_valid') ORDER BY i.interp_id", (self.workspace_id,))
        return {r[0]: (r[1], r[2], r[3], r[4]) for r in rows}

    def status_counts(self) -> dict[str, int]:
        return dict(self.db.query("SELECT enrichment_status, count(*) FROM article WHERE workspace_id = ? GROUP BY 1",
                                  (self.workspace_id,)))

    def review_queue(self, limit: int = 100) -> list[dict]:
        """Articles whose AI result needs review: one row per article, with the fields DisplayPolicy needs."""
        return [dict(r) for r in self.db.query(
            "SELECT a.uid, a.licence_snapshot, a.restrictions, a.canonical_url, r.headline, r.description_text, "
            "r.body_text, (SELECT max(i.created_utc) FROM ai_interpretation i WHERE i.target_kind = 'revision' AND "
            "i.target_id = a.current_revision_id AND i.task = 'enrich') AS last_attempt_utc FROM article a JOIN "
            "article_revision r ON r.revision_id = a.current_revision_id WHERE a.workspace_id = ? AND "
            "a.enrichment_status = 'review' ORDER BY a.article_id DESC LIMIT ?", (self.workspace_id, limit))]
