"""Events: stories grouped across items and outlets (tables `event`, `event_member`; ROADMAP "items, not events").

Writes come from the events stage of a cycle (`runtime/events.py`); the clustering itself is pure
(`pipeline/events.py`). Membership is incremental: an article placed in an event is never moved by a later cycle;
`clear_auto` + a fresh pass (`newsmon events --rebuild`) recomputes everything the algorithm made (`added_by = 'auto'`)
after a threshold or profile change, and keeps the `event_id` of every event whose first member is unchanged.

Read API (for the UI, the CLI and event-aware alerting / digests built on top):

- `list_events(since=, seen_since=, min_members=, statuses=, limit=)` -> event summaries, newest update first.
- `get(event_id)` -> one event summary, or None.
- `timeline(event_id)` -> members in story-time order, each with a derived `kind` (first | repeat | development |
  correction | withdrawal | kill), `novelty`, `new_source`, `band`, `source_key`, `first_seen_utc`, ... (never stored).
- `event_for_article(article_id)` -> the event_id an article (or its near-duplicate primary) belongs to, or None.

Every row returned carries raw stored fields (headline, licence_snapshot, restrictions, canonical_url): anything shown to
a person must go through `licence.policy.DisplayPolicy.render` first, exactly as the queue does.

Times: `event.first_seen_utc` / `last_update_utc` are member *story times* (publication time capped at first-seen
time, `pipeline.events.story_time`), so a backlog of old items does not look like fresh activity. Each timeline row also
has the member's own `first_seen_utc` (when this system first saw it), which is what "new since" questions should use.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime

from newsmon.pipeline import events as ev
from newsmon.repo.base import BaseRepo

STATUSES = ("open", "dormant", "closed", "merged")
BAND_RANK = {"flash": 3, "report": 2, "review": 1, "drop": 0}
_STORY = "MIN(COALESCE(a.published_utc, a.first_seen_utc), a.first_seen_utc)"
_INDEP = "COALESCE(NULLIF(s.owner_group, ''), a.reg_domain, s.registrable_domain, s.key)"
_ROW = ("SELECT a.article_id, a.uid, a.dup_of, a.status, a.first_seen_utc, a.published_utc, "
        "MIN(COALESCE(a.published_utc, a.first_seen_utc), a.first_seen_utc) AS story_utc, a.lang, a.final_band, "
        "s.key AS source_key, COALESCE(NULLIF(s.owner_group, ''), a.reg_domain, s.registrable_domain, s.key) AS indep, "
        "r.headline, r.description_text, m.event_id "
        "FROM article a JOIN source s ON s.source_id = a.source_id "
        "JOIN article_revision r ON r.revision_id = a.current_revision_id "
        "LEFT JOIN event_member m ON m.article_id = a.article_id ")


def event_uid(first_article_uid: str) -> str:
    return "e_" + hashlib.sha256(f"event\x1f{first_article_uid}".encode("utf-8")).hexdigest()[:20]


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


class EventRepo(BaseRepo):
    # --- inputs of the events stage --------------------------------------------------------------------------------------
    def unassigned(self, limit: int = 20000) -> list[dict]:
        """Live articles (primaries and near-duplicate children) in no event yet, oldest story first."""
        return [dict(r) for r in self.db.query(
            _ROW + "WHERE a.workspace_id = ? AND a.status <> 'killed' AND m.event_id IS NULL "
            "ORDER BY story_utc, a.article_id LIMIT ?", (self.workspace_id, int(limit)))]

    def window(self, since_s: str) -> list[dict]:
        """Live primary articles whose story time is at or after `since_s`, with their event (None when unplaced):
        the documents IDF is fitted on and the members that make up each live event's centroid."""
        return [dict(r) for r in self.db.query(
            _ROW + "WHERE a.workspace_id = ? AND a.status <> 'killed' AND a.dup_of IS NULL AND " + _STORY + " >= ? "
            "ORDER BY story_utc, a.article_id", (self.workspace_id, since_s))]

    def event_times(self, event_ids: list[int]) -> dict[int, tuple[str, str]]:
        if not event_ids:
            return {}
        return {r["event_id"]: (r["first_seen_utc"], r["last_update_utc"]) for r in self.db.query(
            "SELECT event_id, first_seen_utc, last_update_utc FROM event WHERE workspace_id = ? AND status IN "
            "('open', 'dormant') AND event_id IN (SELECT value FROM json_each(?))",
            (self.workspace_id, json.dumps(event_ids)))}

    def event_for_article(self, article_id: int) -> int | None:
        """The event an article belongs to; for a near-duplicate not yet placed, its primary's event."""
        r = self.db.scalar(
            "SELECT m.event_id FROM event_member m JOIN event e ON e.event_id = m.event_id WHERE e.workspace_id = ? "
            "AND m.article_id = ? AND e.status <> 'merged' ORDER BY m.event_id LIMIT 1", (self.workspace_id, article_id))
        if r is not None:
            return r
        return self.db.scalar(
            "SELECT m.event_id FROM article a JOIN event_member m ON m.article_id = a.dup_of JOIN event e ON "
            "e.event_id = m.event_id WHERE a.article_id = ? AND a.workspace_id = ? AND e.workspace_id = ? "
            "AND e.status <> 'merged' ORDER BY m.event_id LIMIT 1", (article_id, self.workspace_id, self.workspace_id))

    # --- writes ---------------------------------------------------------------------------------------------------------
    def save(self, *, new_events: list[tuple[str, list[tuple[int, float | None]]]],
             joins: list[tuple[int, int, float | None]], algo: str, now_s: str, window_hours: float,
             keep_ids: dict[str, int] | None = None) -> dict[str, int]:
        """Write one pass atomically. `new_events`: (first member's article uid, [(article_id, similarity), ...]) in
        story order; `joins`: (event_id, article_id, similarity) for articles added to stored events. `keep_ids` maps an
        event uid to the event_id it had before a rebuild, so references to it survive. Then refreshes the aggregates
        of every touched event and ages events with no update in the window to `dormant`."""
        keep_ids = keep_ids or {}
        touched: set[int] = set()
        with self.db.tx():
            for first_uid, members in new_events:
                uid = event_uid(first_uid)
                want = keep_ids.get(uid)
                if want is not None and self.db.scalar("SELECT 1 FROM event WHERE event_id = ?", (want,)) is None:
                    cur = self.db.execute(
                        "INSERT INTO event (event_id, workspace_id, uid, first_seen_utc, last_update_utc, status, algo) "
                        "VALUES (?, ?, ?, ?, ?, 'open', ?)", (want, self.workspace_id, uid, now_s, now_s, algo))
                else:
                    cur = self.db.execute(
                        "INSERT INTO event (workspace_id, uid, first_seen_utc, last_update_utc, status, algo) "
                        "VALUES (?, ?, ?, ?, 'open', ?)", (self.workspace_id, uid, now_s, now_s, algo))
                eid = cur.lastrowid
                touched.add(eid)
                for article_id, sim in members:
                    self._add_member(eid, article_id, sim, now_s)
            for eid, article_id, sim in joins:
                self._add_member(eid, article_id, sim, now_s)
                touched.add(eid)
            self.refresh(sorted(touched), now_s, window_hours)
            aged = self.age(now_s, window_hours)
        return {"created": len(new_events), "joined": len(joins), "touched": len(touched), "aged": aged}

    def _add_member(self, event_id: int, article_id: int, similarity: float | None, now_s: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO event_member (event_id, article_id, similarity, added_utc, added_by) "
                        "VALUES (?, ?, ?, ?, 'auto')", (event_id, article_id, similarity, now_s))

    def refresh(self, event_ids: list[int], now_s: str, window_hours: float) -> None:
        """Recompute first/last story time, independent sources (distinct owner group / registrable domain across all
        members, near-duplicates included), the highest member band and the open/dormant status."""
        from datetime import timedelta
        if not event_ids:
            return
        cutoff = (parse(now_s) - timedelta(hours=window_hours)).isoformat(timespec="seconds")
        rows = self.db.query(
            "SELECT m.event_id, " + _STORY + " AS story_utc, a.status, a.final_band, " + _INDEP + " AS indep "
            "FROM json_each(?) j CROSS JOIN event_member m ON m.event_id = j.value "  # CROSS JOIN fixes the loop order
            "CROSS JOIN article a ON a.article_id = m.article_id CROSS JOIN source s ON s.source_id = a.source_id "
            "WHERE a.workspace_id = ?", (json.dumps(event_ids), self.workspace_id))
        agg: dict[int, dict] = {}
        for r in rows:
            g = agg.setdefault(r["event_id"], {"first": None, "last": None, "src": set(), "band": None})
            st = parse(r["story_utc"]).isoformat(timespec="seconds")
            g["first"] = st if g["first"] is None or st < g["first"] else g["first"]
            g["last"] = st if g["last"] is None or st > g["last"] else g["last"]
            g["src"].add(r["indep"])
            if r["status"] != "killed" and BAND_RANK.get(r["final_band"] or "drop", 0) >= BAND_RANK.get(g["band"] or "", -1):
                g["band"] = r["final_band"] or "drop"
        for eid, g in agg.items():
            self.db.execute(
                "UPDATE event SET first_seen_utc = ?, last_update_utc = ?, independent_sources = ?, final_band = ?, "
                "status = CASE WHEN status IN ('open', 'dormant') THEN (CASE WHEN ? >= ? THEN 'open' ELSE 'dormant' END) "
                "ELSE status END WHERE event_id = ? AND workspace_id = ?",
                (g["first"], g["last"], len(g["src"]), g["band"], g["last"], cutoff, eid, self.workspace_id))

    def age(self, now_s: str, window_hours: float) -> int:
        """Open events with no member story in the last `window_hours` become dormant."""
        from datetime import timedelta
        cutoff = (parse(now_s) - timedelta(hours=window_hours)).isoformat(timespec="seconds")
        return self.db.execute("UPDATE event SET status = 'dormant' WHERE workspace_id = ? AND status = 'open' AND "
                               "last_update_utc < ?", (self.workspace_id, cutoff)).rowcount

    def refresh_bands(self, now_s: str, window_hours: float) -> None:
        """Bands change on every re-rank: refresh the aggregates of open events."""
        ids = [r[0] for r in self.db.query("SELECT event_id FROM event WHERE workspace_id = ? AND status = 'open'",
                                           (self.workspace_id,))]
        with self.db.tx():
            self.refresh(ids, now_s, window_hours)

    def clear_auto(self) -> dict[str, int]:
        """Remove everything the algorithm made: `auto` memberships, then events left with no member. Events an editor
        added members to keep those members. Returns {event uid: event_id} of the removed events, so a rebuild can
        give an event with the same first member its old id back."""
        with self.db.tx():
            ids = {r["uid"]: r["event_id"] for r in self.db.query(
                "SELECT uid, event_id FROM event WHERE workspace_id = ?", (self.workspace_id,))}
            self.db.execute("DELETE FROM event_member WHERE added_by = 'auto' AND event_id IN (SELECT event_id FROM event "
                            "WHERE workspace_id = ?)", (self.workspace_id,))
            kept = {r[0] for r in self.db.query(
                "SELECT DISTINCT e.uid FROM event e JOIN event_member m ON m.event_id = e.event_id WHERE e.workspace_id = ?",
                (self.workspace_id,))}
            self.db.execute("DELETE FROM event WHERE workspace_id = ? AND NOT EXISTS (SELECT 1 FROM event_member m "
                            "WHERE m.event_id = event.event_id)", (self.workspace_id,))
        return {u: i for u, i in ids.items() if u not in kept}

    # --- reads ----------------------------------------------------------------------------------------------------------
    _EVENT = ("SELECT e.event_id, e.uid, e.first_seen_utc, e.last_update_utc, e.status, e.independent_sources, "
              "e.final_band, e.algo, (SELECT count(*) FROM event_member m WHERE m.event_id = e.event_id) AS members, "
              "(SELECT count(*) FROM event_member m JOIN article a ON a.article_id = m.article_id WHERE "
              "m.event_id = e.event_id AND a.dup_of IS NULL) AS primaries FROM event e ")

    def list_events(self, *, since: str | None = None, seen_since: str | None = None, min_members: int = 1,
                    min_primaries: int = 1, statuses: tuple[str, ...] | list[str] = ("open", "dormant"), limit: int = 200) -> list[dict]:
        """Event summaries, most recently updated first.

        `since`: last story update at or after this UTC ISO time. `seen_since`: at least one member first seen by this
        system at or after this time (what a "what's new" digest wants). `min_members`: members including
        near-duplicates; `min_primaries`: distinct items, near-duplicates not counted (an event of one item and its
        copies has one primary). Each summary has event_id, uid, first_seen_utc, last_update_utc (story times), status,
        independent_sources, final_band, algo, members, primaries, langs (sorted list), sources (distinct source keys)
        and `lead`: the earliest primary member's raw row (uid, headline, source_name, licence_snapshot, restrictions,
        canonical_url, ...) to be rendered through DisplayPolicy."""
        statuses = tuple(s for s in statuses if s in STATUSES) or ("open",)
        where = ["e.workspace_id = ?", "e.status IN (SELECT value FROM json_each(?))",
                 "(SELECT count(*) FROM event_member m WHERE m.event_id = e.event_id) >= ?",
                 "(SELECT count(*) FROM event_member m JOIN article a ON a.article_id = m.article_id WHERE "
                 "m.event_id = e.event_id AND a.dup_of IS NULL) >= ?"]
        params: list = [self.workspace_id, json.dumps(list(statuses)), int(min_members), int(min_primaries)]
        if since:
            where.append("e.last_update_utc >= ?")
            params.append(since)
        if seen_since:
            where.append("EXISTS (SELECT 1 FROM event_member m JOIN article a ON a.article_id = m.article_id WHERE "
                         "m.event_id = e.event_id AND a.first_seen_utc >= ?)")
            params.append(seen_since)
        params.append(min(int(limit), 2000))
        rows = [dict(r) for r in self.db.query(self._EVENT + "WHERE " + " AND ".join(where) +
                                               " ORDER BY e.last_update_utc DESC, e.event_id DESC LIMIT ?", params)]
        self._decorate(rows)
        return rows

    def get(self, event_id: int) -> dict | None:
        r = self.db.one(self._EVENT + "WHERE e.workspace_id = ? AND e.event_id = ?", (self.workspace_id, int(event_id)))
        if r is None:
            return None
        rows = [dict(r)]
        self._decorate(rows)
        return rows[0]

    def get_by_uid(self, uid: str) -> dict | None:
        eid = self.db.scalar("SELECT event_id FROM event WHERE workspace_id = ? AND uid = ?", (self.workspace_id, uid))
        return self.get(eid) if eid is not None else None

    _MEMBER = ("SELECT m.event_id, m.similarity, m.added_utc, m.added_by, a.article_id, a.uid, a.dup_of, a.status, "
               "a.first_seen_utc, a.published_utc, " + _STORY + " AS story_utc, a.lang, a.final_band, a.rule_score, "
               "a.urgency, a.restrictions, a.licence_snapshot, a.canonical_url, a.synthetic, a.item_type, a.located, "
               "a.slugline, s.key AS source_key, s.name AS source_name, " + _INDEP + " AS indep, r.headline, "
               "r.description_text FROM json_each(?) j CROSS JOIN event_member m ON m.event_id = j.value "
               "CROSS JOIN article a ON a.article_id = m.article_id CROSS JOIN source s ON s.source_id = a.source_id "
               "CROSS JOIN article_revision r ON r.revision_id = a.current_revision_id ")

    def _members(self, event_ids: list[int]) -> list[dict]:
        return [dict(r) for r in self.db.query(
            self._MEMBER + "WHERE a.workspace_id = ? ORDER BY story_utc, a.article_id",
            (json.dumps(event_ids), self.workspace_id))]

    def _decorate(self, rows: list[dict]) -> None:
        if not rows:
            return
        by: dict[int, list[dict]] = {}
        for m in self._members([r["event_id"] for r in rows]):
            by.setdefault(m["event_id"], []).append(m)
        for r in rows:
            ms = by.get(r["event_id"], [])
            prim = [m for m in ms if m["dup_of"] is None] or ms
            r["langs"] = sorted({m["lang"] for m in ms if m["lang"]})
            r["sources"] = sorted({m["source_key"] for m in ms})
            r["lead"] = prim[0] if prim else None

    def timeline(self, event_id: int) -> list[dict]:
        """Members in story-time order (ties by article id), each a raw member row plus the derived fields:
        `kind` (see `pipeline.events.timeline`), `novelty` (share of the item's features the event had not seen
        before it, 0..1), `new_source` (its owner group / registrable domain is new to the event) and `band` (the
        article's final band). `first_seen_utc` is when this system first saw the member; `story_utc` is what orders the
        timeline. Display text must go through DisplayPolicy."""
        ms = self._members([int(event_id)])
        if not ms:
            return []
        kinds: dict[int, list[str]] = {}
        for r in self.db.query(
                "SELECT r.article_id, r.change_kind FROM article_revision r JOIN article a ON a.article_id = r.article_id "
                "WHERE a.workspace_id = ? AND r.article_id IN (SELECT value FROM json_each(?))",
                (self.workspace_id, json.dumps([m["article_id"] for m in ms]))):
            if r["change_kind"]:
                kinds.setdefault(r["article_id"], []).append(r["change_kind"])
        steps = ev.timeline([ev.Member(article_id=m["article_id"], when=parse(m["story_utc"]),
                                       bag=Counter(ev.features(m["headline"], m["description_text"])),
                                       source=m["indep"], dup_of=m["dup_of"], status=m["status"],
                                       change_kinds=tuple(kinds.get(m["article_id"], ()))) for m in ms])
        by = {s.article_id: s for s in steps}
        out = []
        for m in sorted(ms, key=lambda x: (parse(x["story_utc"]), x["article_id"])):
            s = by[m["article_id"]]
            out.append({**m, "kind": s.kind, "novelty": s.novelty, "new_source": s.new_source,
                        "band": m["final_band"] or "drop", "revised": len(kinds.get(m["article_id"], ())) > 1})
        return out

    def counts(self) -> dict[str, int]:
        q = lambda sql: self.db.scalar(sql, (self.workspace_id,))  # noqa: E731
        return {"events": q("SELECT count(*) FROM event WHERE workspace_id = ?"),
                "open": q("SELECT count(*) FROM event WHERE workspace_id = ? AND status = 'open'"),
                "multi": q("SELECT count(*) FROM event e WHERE e.workspace_id = ? AND (SELECT count(*) FROM event_member m "
                           "JOIN article a ON a.article_id = m.article_id WHERE m.event_id = e.event_id "
                           "AND a.dup_of IS NULL) > 1"),
                "members": q("SELECT count(*) FROM event_member m JOIN event e ON e.event_id = m.event_id "
                             "WHERE e.workspace_id = ?")}
