"""Editorial verdicts (FR-18, the "PC등록" registration of INTERFACE_SPEC §2) and the rows a shift report selects.

Append-only: a new verdict adds a row and the latest row per article is the current verdict. Nothing here updates or
deletes an assessment, so the table is also the history of who decided what and when.
"""
from __future__ import annotations

import json

from newsmon.repo.base import BaseRepo

VERDICTS = ("report_to_desk", "verify", "ignore")  # 'archived' exists in the schema; no surface uses it yet
NOTE_MAX = 1000

# the newest assessment row per article (assess_id is monotonic, so it breaks ties within one second)
_LATEST = ("SELECT e.* FROM editorial_assessment e WHERE e.workspace_id = ? AND e.target_kind = 'article' AND e.assess_id = "
           "(SELECT max(x.assess_id) FROM editorial_assessment x WHERE x.workspace_id = e.workspace_id "
           "AND x.target_kind = 'article' AND x.target_id = e.target_id)")


class AssessmentRepo(BaseRepo):
    def add(self, article_id: int, verdict: str, note: str | None, editor: str, now_s: str) -> int:
        if verdict not in VERDICTS:
            raise ValueError(f"unknown verdict {verdict!r}")
        note = (note or "").strip()[:NOTE_MAX] or None
        # the AI assessment on screen when the verdict was made, if any: the newest one for the current revision
        based_on = self.db.scalar(
            "SELECT max(i.interp_id) FROM ai_interpretation i JOIN article a ON i.target_kind = 'revision' AND "
            "i.target_id = a.current_revision_id WHERE i.workspace_id = ? AND a.article_id = ?",
            (self.workspace_id, article_id))
        cur = self.db.execute("INSERT INTO editorial_assessment (workspace_id, target_kind, target_id, editor, verdict, note, "
                              "based_on_interp_id, created_utc) VALUES (?, 'article', ?, ?, ?, ?, ?, ?)",
                              (self.workspace_id, article_id, editor, verdict, note, based_on, now_s))
        return cur.lastrowid

    def latest_for_articles(self, article_ids: list[int]) -> dict[int, dict]:
        if not article_ids:
            return {}
        rows = self.db.query(_LATEST + " AND e.target_id IN (SELECT value FROM json_each(?))",
                             (self.workspace_id, json.dumps(article_ids)))
        return {r["target_id"]: dict(r) for r in rows}

    def history(self, article_id: int) -> list[dict]:
        return [dict(r) for r in self.db.query(
            "SELECT assess_id, editor, verdict, note, created_utc FROM editorial_assessment WHERE workspace_id = ? AND "
            "target_kind = 'article' AND target_id = ? ORDER BY assess_id DESC", (self.workspace_id, article_id))]

    def report_rows(self, since: str, until: str, verdicts: tuple[str, ...] = ("report_to_desk", "verify")) -> list[dict]:
        """Articles whose *current* verdict was made in [since, until) and is one of `verdicts`. Selected by verdict, not
        by queue membership, so an item later killed or re-pointed as a duplicate still appears (and is marked)."""
        sql = ("SELECT v.assess_id, v.verdict, v.note, v.editor, v.created_utc AS verdict_utc, "
               "a.article_id, a.uid, a.canonical_url, a.lang, a.urgency, a.first_seen_utc, a.published_utc, a.final_band, "
               "a.rule_score, a.status, a.item_type, a.located, a.slugline, a.restrictions, a.licence_snapshot, a.dup_of, "
               "a.synthetic, s.key AS source_key, s.name AS source_name, r.headline, r.description_text, r.body_text, "
               "r.version, r.fetched_utc AS revision_utc, "
               "(SELECT count(*) FROM article d WHERE d.dup_of = a.article_id) AS dup_count "
               "FROM (" + _LATEST + ") v JOIN article a ON a.article_id = v.target_id AND a.workspace_id = v.workspace_id "
               "JOIN source s ON s.source_id = a.source_id JOIN article_revision r ON r.revision_id = a.current_revision_id "
               "WHERE v.created_utc >= ? AND v.created_utc < ? AND v.verdict IN (SELECT value FROM json_each(?)) "
               "ORDER BY CASE v.verdict WHEN 'report_to_desk' THEN 0 ELSE 1 END, v.created_utc")
        return [dict(r) for r in self.db.query(sql, (self.workspace_id, since, until, json.dumps(list(verdicts))))]
