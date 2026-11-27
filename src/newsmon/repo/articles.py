"""Articles, revisions, observations, dedup links, media references and the search index (T-19, T-20, T-32).

Ingestion is idempotent through natural keys: (source, uri), (source, canonical_url) and (article, content_sha256).
Licence gating happens here, at the only place text is written: a body is stored only for storage=full, and the
search index only ever holds stored text (11 §5).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime

from newsmon.domain.models import SourceRef
from newsmon.licence.policy import LicenceGate
from newsmon.pipeline import dedup
from newsmon.pipeline.domains import registrable_domain
from newsmon.pipeline.normalise import Normalised, iso
from newsmon.pipeline.tokenize import build_match, index_text
from newsmon.repo.base import BaseRepo

BAND_ORDER = "CASE a.final_band WHEN 'flash' THEN 3 WHEN 'report' THEN 2 WHEN 'review' THEN 1 ELSE 0 END"


@dataclass
class StoreResult:
    action: str  # new | observed | unchanged | revision | killed | not_stored
    article_id: int | None = None
    links: list[dedup.Link] = field(default_factory=list)


def article_uid(source_key: str, natural: str) -> str:
    return "a_" + hashlib.sha256(f"{source_key}\x1f{natural}".encode("utf-8")).hexdigest()[:20]


class ArticleRepo(BaseRepo):
    def __init__(self, db, workspace_id: int = 1) -> None:
        super().__init__(db, workspace_id)
        self.index = dedup.NearDupIndex()
        self._index_loaded = False

    # --- near-dup index ------------------------------------------------------------------------------------------------
    def load_index(self) -> int:
        rows = self.db.query(
            "SELECT r.revision_id, a.article_id, a.source_id, a.first_seen_utc, a.story_key, a.is_live, r.minhash "
            "FROM article_revision r JOIN article a ON a.current_revision_id = r.revision_id "
            "WHERE a.workspace_id = ? AND r.minhash IS NOT NULL", (self.workspace_id,))
        for r in rows:
            self.index.add(dedup.Candidate(r[0], r[1], r[2], datetime.fromisoformat(r[3]), r[4], bool(r[5])),
                           dedup.from_blob(r[6]))
        self._index_loaded = True
        return len(rows)

    # --- ingest ---------------------------------------------------------------------------------------------------------
    def store(self, src: SourceRef, n: Normalised, *, feed_id: int | None, now: datetime) -> StoreResult:
        if not self._index_loaded:
            self.load_index()
        gate = LicenceGate.storage(src.flags)
        if not gate.store:
            return StoreResult("not_stored")
        it = n.item
        description = it.description_text if gate.keep_description else None
        body = it.body_text if gate.keep_body else None  # transient bodies are never written (FR-06(b))
        natural = it.uri or n.canonical_url or n.content_sha256
        feed_guid = it.uri or n.canonical_url or n.content_sha256
        now_s = iso(now)
        with self.db.tx():
            existing = None
            if it.uri:
                existing = self.db.one("SELECT article_id, current_revision_id, status FROM article WHERE workspace_id = ? "
                                       "AND source_id = ? AND source_uri = ?", (self.workspace_id, src.source_id, it.uri))
            if existing is None and n.canonical_url:
                existing = self.db.one("SELECT article_id, current_revision_id, status FROM article WHERE workspace_id = ? "
                                       "AND source_id = ? AND canonical_url = ?",
                                       (self.workspace_id, src.source_id, n.canonical_url))
            if existing is None:  # an entry with neither id nor link is identified by its content (the uid)
                existing = self.db.one("SELECT article_id, current_revision_id, status FROM article WHERE workspace_id = ? "
                                       "AND uid = ?", (self.workspace_id, article_uid(src.key, natural)))
            if existing is not None:
                return self._update_existing(src, n, existing, feed_id, feed_guid, description, body, now_s)
            return self._insert_new(src, n, natural, feed_id, feed_guid, description, body, now, now_s)

    def _observe(self, src: SourceRef, feed_id: int | None, article_id: int, guid: str, now_s: str) -> bool:
        cur = self.db.execute("INSERT OR IGNORE INTO feed_entry (workspace_id, source_id, feed_id, article_id, feed_guid, "
                              "seen_utc) VALUES (?, ?, ?, ?, ?, ?)",
                              (self.workspace_id, src.source_id, feed_id, article_id, guid, now_s))
        return cur.rowcount > 0

    def _insert_revision(self, article_id: int, n: Normalised, description, body, change_kind: str, now_s: str) -> int | None:
        it = n.item
        sig = dedup.signature(n.match_text)
        cur = self.db.execute(
            "INSERT OR IGNORE INTO article_revision (article_id, fetched_utc, version, headline, description_text, body_text, "
            "parser, raw_ref, raw_sha256, content_sha256, minhash, change_kind, renditions, associations) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (article_id, now_s, it.version, it.headline, description, body, it.parser, it.raw_ref, it.raw_sha256,
             n.content_sha256, dedup.to_blob(sig), change_kind,
             json.dumps(it.renditions, ensure_ascii=False) if it.renditions else None,
             json.dumps(it.associations, ensure_ascii=False) if it.associations else None))
        return cur.lastrowid if cur.rowcount else None

    def _update_existing(self, src, n, existing, feed_id, guid, description, body, now_s) -> StoreResult:
        article_id, cur_rev, status = existing
        it = n.item
        observed = self._observe(src, feed_id, article_id, f"{guid}", now_s)
        if it.pubstatus == "canceled":
            if status == "killed":
                return StoreResult("unchanged", article_id)
            rev = self._insert_revision(article_id, n, description, body, "kill", now_s)
            self.db.execute("UPDATE article SET status = 'killed', pubstatus = 'canceled', current_revision_id = "
                            "COALESCE(?, current_revision_id) WHERE article_id = ? AND workspace_id = ?",
                            (rev, article_id, self.workspace_id))
            self._repoint_duplicates(article_id)
            return StoreResult("killed", article_id)
        if it.restrictions and it.restrictions.strip():
            # a restriction applies as soon as any version carries it, whether or not that version's text is new or
            # the version is the current one; once present it is kept (stricter wins)
            self.db.execute("UPDATE article SET restrictions = ? WHERE article_id = ? AND workspace_id = ?",
                            (it.restrictions, article_id, self.workspace_id))
        # an updated clip usually arrives under a new file name (ItemID--2--...), even when its text is unchanged
        for href in it.media_refs:
            self.db.execute("INSERT INTO media_asset (article_id, kind, href, recorded_utc) SELECT ?, ?, ?, ? WHERE NOT "
                            "EXISTS (SELECT 1 FROM media_asset WHERE article_id = ? AND href = ?)",
                            (article_id, "video" if str(it.type) == "video" else "image", href, now_s, article_id, href))
        same = self.db.one("SELECT revision_id FROM article_revision WHERE article_id = ? AND content_sha256 = ?",
                           (article_id, n.content_sha256))
        if same is not None:
            return StoreResult("observed" if observed else "unchanged", article_id)
        cur_version = self.db.scalar("SELECT version FROM article_revision WHERE revision_id = ?", (cur_rev,)) or 1
        if it.version < cur_version:
            return StoreResult("unchanged", article_id)  # an older version arriving late never replaces a newer one
        rev = self._insert_revision(article_id, n, description, body, "update", now_s)
        # a restriction, once present, is kept (stricter wins); new usage terms replace old ones; the AI view belongs
        # to a revision, so a new revision is pending again
        self.db.execute("UPDATE article SET current_revision_id = ?, urgency = COALESCE(?, urgency), lang = ?, "
                        "restrictions = COALESCE(NULLIF(?, ''), restrictions), usageterms = COALESCE(?, usageterms), "
                        "pubstatus = ?, enrichment_status = 'pending' WHERE article_id = ? AND workspace_id = ?",
                        (rev, it.urgency, n.lang, it.restrictions, it.usageterms, str(it.pubstatus), article_id,
                         self.workspace_id))
        self._index(article_id, it.headline, description, body)
        return StoreResult("revision", article_id)

    def _insert_new(self, src, n, natural, feed_id, guid, description, body, now: datetime, now_s: str) -> StoreResult:
        it = n.item
        uid = article_uid(src.key, natural)
        reg = registrable_domain(n.canonical_url) or src.registrable_domain or src.key
        killed = it.pubstatus == "canceled"
        cur = self.db.execute(
            "INSERT INTO article (workspace_id, uid, source_id, source_uri, canonical_url, item_type, lang, slugline, located, "
            "urgency, pubstatus, usageterms, restrictions, subjects, first_seen_utc, published_utc, published_raw, status, "
            "story_key, is_live, licence_snapshot, synthetic, reg_domain, enrichment_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (self.workspace_id, uid, src.source_id, it.uri, n.canonical_url, str(it.type), n.lang, it.slugline, it.located,
             it.urgency, str(it.pubstatus), it.usageterms, it.restrictions,
             json.dumps(it.subjects, ensure_ascii=False) if it.subjects else None, now_s, n.published_utc,
             n.published_raw, "killed" if killed else "live", n.story_key, int(n.is_live), src.flags.snapshot_json(),
             int(src.flags.synthetic), reg, "pending"))
        article_id = cur.lastrowid
        rev = self._insert_revision(article_id, n, description, body, "kill" if killed else "initial", now_s)
        self.db.execute("UPDATE article SET current_revision_id = ? WHERE article_id = ?", (rev, article_id))
        self._observe(src, feed_id, article_id, guid, now_s)
        links: list[dedup.Link] = []
        exact = self.db.one(
            "SELECT r.revision_id, a.article_id FROM article_revision r JOIN article a ON a.article_id = r.article_id "
            "WHERE r.content_sha256 = ? AND a.article_id <> ? AND a.workspace_id = ? AND a.status <> 'killed' "
            "ORDER BY a.article_id LIMIT 1",
            (n.content_sha256, article_id, self.workspace_id))
        if exact:
            links.append(dedup.Link(exact[0], exact[1], 1.0, "same_item"))
        sig = dedup.signature(n.match_text)
        for link in self.index.links_for(sig, source_id=src.source_id, first_seen=now, story_key=n.story_key,
                                         is_live=n.is_live, exclude_article=article_id):
            if not any(x.other_article_id == link.other_article_id for x in links):
                links.append(link)
        for link in links:
            self.db.execute("INSERT OR IGNORE INTO near_dup_link (a_revision_id, b_revision_id, jaccard_est, kind, method) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (link.other_revision_id, rev, round(link.jaccard, 4), link.kind,
                             "sha256" if link.jaccard == 1.0 and link.kind == "same_item" else
                             ("story_key" if link.jaccard == 0.0 else dedup.METHOD)))
        # a withdrawn article never becomes the visible copy of a group: only live matches can be the primary
        live = [x.other_article_id for x in links if self.db.scalar(
            "SELECT status FROM article WHERE article_id = ?", (x.other_article_id,)) != "killed"]
        if live:
            root = self.db.scalar("SELECT COALESCE(dup_of, article_id) FROM article WHERE article_id = ?", (min(live),))
            self.db.execute("UPDATE article SET dup_of = ? WHERE article_id = ?", (root, article_id))
        self.index.add(dedup.Candidate(rev, article_id, src.source_id, now, n.story_key, n.is_live), sig)
        self._index(article_id, it.headline, description, body)
        for href in it.media_refs:
            self.db.execute("INSERT INTO media_asset (article_id, kind, href, recorded_utc) VALUES (?, ?, ?, ?)",
                            (article_id, "video" if str(it.type) == "video" else "image", href, now_s))
        return StoreResult("killed" if killed else "new", article_id, links)

    def _repoint_duplicates(self, killed_id: int) -> None:
        """A killed primary must not hide live copies from other sources: the earliest live member becomes the new
        primary of the group (or the group dissolves)."""
        members = [r[0] for r in self.db.query(
            "SELECT article_id FROM article WHERE dup_of = ? AND workspace_id = ? AND status <> 'killed' "
            "ORDER BY article_id", (killed_id, self.workspace_id))]
        if not members:
            return
        new_root, rest = members[0], members[1:]
        self.db.execute("UPDATE article SET dup_of = NULL WHERE article_id = ? AND workspace_id = ?",
                        (new_root, self.workspace_id))
        for m in rest:
            self.db.execute("UPDATE article SET dup_of = ? WHERE article_id = ? AND workspace_id = ?",
                            (new_root, m, self.workspace_id))

    def update_media(self, href: str, sha256: str, size: int, content_type: str) -> int:
        cur = self.db.execute("UPDATE media_asset SET sha256 = ?, size_bytes = ?, content_type = ? WHERE href = ? AND "
                              "article_id IN (SELECT article_id FROM article WHERE workspace_id = ?)",
                              (sha256, size, content_type, href, self.workspace_id))
        return cur.rowcount

    # --- search index ----------------------------------------------------------------------------------------------------
    def _index(self, article_id: int, headline: str, description: str | None, body: str | None) -> None:
        self.db.execute("DELETE FROM search_fts WHERE rowid = ?", (article_id,))
        self.db.execute("INSERT INTO search_fts (rowid, headline_tok, text_tok, ai_tok, entity_tok) VALUES (?, ?, ?, '', '')",
                        (article_id, index_text(headline), index_text(" ".join(x for x in (description, body) if x))))

    # --- ranking ----------------------------------------------------------------------------------------------------------
    def ranking_inputs(self) -> list[dict]:
        """Everything the rules need per live article, including independent-source counts per duplicate group."""
        rows = self.db.query(
            "SELECT a.article_id, a.first_seen_utc, a.lang, a.urgency, a.dup_of, a.reg_domain, a.regex_prefilter_hit, "
            "s.key AS source_key, "
            "s.is_wire, r.headline, r.description_text, r.body_text FROM article a JOIN source s ON s.source_id = a.source_id "
            "JOIN article_revision r ON r.revision_id = a.current_revision_id WHERE a.workspace_id = ? AND a.status <> 'killed'",
            (self.workspace_id,))
        groups: dict[int, set[str]] = {}
        for r in rows:
            groups.setdefault(r["dup_of"] or r["article_id"], set()).add(r["reg_domain"] or r["source_key"])
        out = []
        for r in rows:
            d = dict(r)
            d["independent_sources"] = len(groups[r["dup_of"] or r["article_id"]])
            out.append(d)
        return out

    def save_ranking(self, profile_id: int, results: list[tuple[int, str, str, float, list[tuple[str, str, float]]]],
                     now_s: str) -> None:
        with self.db.tx():
            for article_id, band, final, score, hits in results:
                self.db.execute("UPDATE article SET rule_band = ?, final_band = ?, rule_score = ? WHERE article_id = ? "
                                "AND workspace_id = ?", (band, final, score, article_id, self.workspace_id))
                self.db.execute("DELETE FROM rule_hit WHERE article_id = ? AND profile_id = ?", (article_id, profile_id))
                for rule_id, matched, s in hits:
                    self.db.execute("INSERT OR REPLACE INTO rule_hit (article_id, profile_id, rule_id, matched, score, "
                                    "created_utc) VALUES (?, ?, ?, ?, ?, ?)",
                                    (article_id, profile_id, rule_id, matched, s, now_s))

    def save_profile(self, key: str, yaml_text: str, updated_by: str, now_s: str) -> int:
        with self.db.tx():
            last = self.db.one("SELECT profile_id, yaml, version FROM profile WHERE workspace_id = ? AND key = ? "
                               "ORDER BY version DESC LIMIT 1", (self.workspace_id, key))
            if last is not None and last["yaml"] == yaml_text:
                return last["profile_id"]
            version = (last["version"] + 1) if last else 1
            self.db.execute("UPDATE profile SET active = 0 WHERE workspace_id = ? AND key = ?", (self.workspace_id, key))
            cur = self.db.execute("INSERT INTO profile (workspace_id, key, yaml, version, active, updated_by, updated_utc) "
                                  "VALUES (?, ?, ?, ?, 1, ?, ?)", (self.workspace_id, key, yaml_text, version, updated_by, now_s))
            return cur.lastrowid

    # --- reads -------------------------------------------------------------------------------------------------------------
    _SELECT = ("SELECT a.article_id, a.uid, a.canonical_url, a.lang, a.urgency, a.first_seen_utc, a.published_utc, "
               "a.final_band, a.rule_score, a.status, a.item_type, a.located, a.slugline, a.restrictions, a.licence_snapshot, "
               "a.dup_of, a.synthetic, a.rule_band, a.enrichment_status, a.regex_prefilter_hit, a.current_revision_id, "
               "s.key AS source_key, s.name AS source_name, r.headline, r.description_text, r.body_text, "
               "r.version, (SELECT count(*) FROM article d WHERE d.dup_of = a.article_id) AS dup_count ")

    def queue(self, *, bands: list[str] | None = None, lang: str | None = None, source_key: str | None = None,
              since: str | None = None, include_dups: bool = False, limit: int = 200) -> list[dict]:
        where = ["a.workspace_id = ?", "a.status <> 'killed'"]
        params: list = [self.workspace_id]
        if not include_dups:
            where.append("a.dup_of IS NULL")
        if bands:
            where.append("COALESCE(a.final_band, 'drop') IN (SELECT value FROM json_each(?))")
            params.append(json.dumps(bands))
        if lang:
            where.append("a.lang = ?")
            params.append(lang)
        if source_key:
            where.append("s.key = ?")
            params.append(source_key)
        if since:
            where.append("a.first_seen_utc >= ?")
            params.append(since)
        params.append(min(int(limit), 1000))
        sql = (self._SELECT + "FROM article a JOIN source s ON s.source_id = a.source_id "
               "JOIN article_revision r ON r.revision_id = a.current_revision_id WHERE " + " AND ".join(where) +
               " ORDER BY " + BAND_ORDER + " DESC, COALESCE(a.rule_score, 0) DESC, a.first_seen_utc DESC LIMIT ?")
        return [dict(r) for r in self.db.query(sql, params)]

    def search(self, query: str, *, aliases: dict[str, list[str]] | None = None, lang: str | None = None,
               source_key: str | None = None, band: str | None = None, since: str | None = None,
               video_only: bool = False, newest_first: bool = False, limit: int = 100) -> list[dict]:
        match = build_match(query, aliases)
        if not match:
            return []
        where = ["search_fts MATCH ?", "a.workspace_id = ?", "a.status <> 'killed'"]
        params: list = [match, self.workspace_id]
        if lang:
            where.append("a.lang = ?")
            params.append(lang)
        if source_key:
            where.append("s.key = ?")
            params.append(source_key)
        if band:
            where.append("a.final_band = ?")
            params.append(band)
        if since:
            where.append("a.first_seen_utc >= ?")
            params.append(since)
        if video_only:  # items that carry a wire clip (duty 4: search for footage)
            where.append("EXISTS (SELECT 1 FROM media_asset m WHERE m.article_id = a.article_id AND m.kind IN ('video', 'audio'))")
        params.append(min(int(limit), 500))
        sql = (self._SELECT + ", bm25(search_fts, 3.0, 1.0, 0.5, 1.0) AS rank FROM search_fts "
               "JOIN article a ON a.article_id = search_fts.rowid JOIN source s ON s.source_id = a.source_id "
               "JOIN article_revision r ON r.revision_id = a.current_revision_id WHERE " + " AND ".join(where) +
               (" ORDER BY a.first_seen_utc DESC LIMIT ?" if newest_first else " ORDER BY rank LIMIT ?"))
        return [dict(r) for r in self.db.query(sql, params)]

    def get(self, uid: str) -> dict | None:
        r = self.db.one(self._SELECT + "FROM article a JOIN source s ON s.source_id = a.source_id JOIN article_revision r ON "
                        "r.revision_id = a.current_revision_id WHERE a.uid = ? AND a.workspace_id = ?", (uid, self.workspace_id))
        return dict(r) if r else None

    def related(self, article_id: int) -> list[dict]:
        """Duplicates and revisions linked to an article (both directions), for the detail page."""
        return [dict(r) for r in self.db.query(
            "SELECT DISTINCT a.uid, s.name AS source_name, l.kind, l.jaccard_est, l.method FROM near_dup_link l "
            "JOIN article_revision ra ON ra.revision_id = l.a_revision_id JOIN article_revision rb ON rb.revision_id = "
            "l.b_revision_id JOIN article a ON a.article_id = CASE WHEN ra.article_id = ? THEN rb.article_id ELSE ra.article_id END "
            "JOIN source s ON s.source_id = a.source_id WHERE (ra.article_id = ? OR rb.article_id = ?) AND a.article_id <> ? "
            "AND a.workspace_id = ?", (article_id, article_id, article_id, article_id, self.workspace_id))]

    def rule_hits(self, article_id: int) -> list[dict]:
        return [dict(r) for r in self.db.query(
            "SELECT h.rule_id, h.matched, h.score FROM rule_hit h JOIN profile p ON p.profile_id = h.profile_id "
            "WHERE h.article_id = ? AND p.active = 1 AND p.workspace_id = ? ORDER BY h.score DESC",
            (article_id, self.workspace_id))]

    def public_candidates(self, limit: int = 1000) -> list[dict]:
        """Queue rows (duplicates collapsed) with everything the public publication gate needs, newest first.
        Only fields the gate may consider are selected: no description or body text is read here."""
        rows = [dict(r) for r in self.db.query(
            "SELECT a.article_id, a.uid, a.canonical_url, a.lang, a.first_seen_utc, a.published_utc, a.final_band, "
            "a.rule_score, a.status, a.pubstatus, a.embargoed_utc, a.restrictions, a.licence_snapshot, a.synthetic, "
            "s.key AS source_key, s.name AS source_name, r.headline, "
            "(SELECT count(*) FROM article d WHERE d.dup_of = a.article_id) AS dup_count "
            "FROM article a JOIN source s ON s.source_id = a.source_id "
            "JOIN article_revision r ON r.revision_id = a.current_revision_id "
            "WHERE a.workspace_id = ? AND a.status <> 'killed' AND a.dup_of IS NULL "
            "ORDER BY a.first_seen_utc DESC LIMIT ?", (self.workspace_id, min(int(limit), 5000)))]
        if rows:
            hits: dict[int, list[str]] = {}
            for h in self.db.query(
                    "SELECT h.article_id, h.rule_id FROM rule_hit h JOIN profile p ON p.profile_id = h.profile_id "
                    "WHERE p.active = 1 AND p.workspace_id = ? AND h.article_id IN (SELECT value FROM json_each(?)) "
                    "ORDER BY h.score DESC", (self.workspace_id, json.dumps([r["article_id"] for r in rows]))):
                hits.setdefault(h["article_id"], []).append(h["rule_id"])
            for r in rows:
                r["rule_ids"] = hits.get(r["article_id"], [])
        return rows

    def media(self, article_id: int) -> list[dict]:
        return [dict(r) for r in self.db.query("SELECT kind, href, sha256, size_bytes, content_type FROM media_asset "
                                               "WHERE article_id = ?", (article_id,))]

    def revisions(self, article_id: int) -> list[dict]:
        return [dict(r) for r in self.db.query("SELECT revision_id, version, change_kind, fetched_utc, headline FROM "
                                               "article_revision WHERE article_id = ? ORDER BY revision_id", (article_id,))]

    def counts(self) -> dict[str, int]:
        q = lambda sql: self.db.scalar(sql, (self.workspace_id,))  # noqa: E731
        return {"articles": q("SELECT count(*) FROM article WHERE workspace_id = ?"),
                "live": q("SELECT count(*) FROM article WHERE workspace_id = ? AND status <> 'killed'"),
                "queue_rows": q("SELECT count(*) FROM article WHERE workspace_id = ? AND status <> 'killed' AND dup_of IS NULL"),
                "revisions": q("SELECT count(*) FROM article_revision r JOIN article a ON a.article_id = r.article_id "
                               "WHERE a.workspace_id = ?"),
                "feed_entries": q("SELECT count(*) FROM feed_entry WHERE workspace_id = ?"),
                "dup_links": q("SELECT count(*) FROM near_dup_link l JOIN article_revision r ON r.revision_id = l.b_revision_id "
                               "JOIN article a ON a.article_id = r.article_id WHERE a.workspace_id = ?"),
                "fetch_runs": q("SELECT count(*) FROM fetch_run WHERE workspace_id = ?"),
                "quarantined": q("SELECT count(*) FROM quarantine WHERE workspace_id = ?")}
