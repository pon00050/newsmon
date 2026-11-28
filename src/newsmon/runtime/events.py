"""The events stage of a cycle: place articles that are in no event yet (pure clustering in `pipeline/events.py`,
storage in `repo/events.py`). Runs after ranking and optional AI, before alerts, isolated like every other stage: an
event defect never stops collection (`runtime/cycle.py`).

Incremental: only articles in no event are placed; placed articles are never moved. Near-duplicate children are not
clustered: they follow their primary into its event. `rebuild=True` removes every `auto` membership and recomputes from
scratch (after a threshold, window or profile change); an event whose first member is unchanged keeps its event_id.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from newsmon.pipeline import events as ev
from newsmon.pipeline.normalise import iso

if TYPE_CHECKING:
    from newsmon.app import App


def params_from(settings) -> ev.Params:
    return ev.Params(threshold=settings.threshold, window=timedelta(hours=settings.window_hours),
                     same_source_threshold=max(settings.threshold, settings.same_source_threshold))


def algo_id(settings) -> str:
    """Stored on each event so rows can be recomputed (ADR-005): algorithm, threshold, window, anchors."""
    return (f"{ev.ALGO}-t{settings.threshold:g}-s{settings.same_source_threshold:g}-w{settings.window_hours:g}h"
            + ("-anchors" if settings.entity_anchors else ""))


def _doc(r: dict, anchors) -> ev.Doc:
    return ev.Doc(article_id=r["article_id"], when=datetime.fromisoformat(r["story_utc"]),
                  bag=Counter(ev.features(r["headline"], r["description_text"], anchors=anchors)),
                  lang=r["lang"], source=r["indep"] or r["source_key"])


def update_events(app: "App", *, rebuild: bool = False, vectorizer: ev.Vectorizer | None = None) -> dict:
    """One pass. Returns counts: placed (primaries), created (new events), joined (into stored events), followers
    (near-duplicates that followed their primary), skipped (near-duplicates whose primary is in no event), aged."""
    s = app.settings.events
    out = {"enabled": s.enabled, "placed": 0, "created": 0, "joined": 0, "followers": 0, "skipped": 0, "aged": 0,
           "rebuilt": rebuild}
    if not s.enabled:
        return out
    repo = app.events
    now = app.clock.now()
    now_s = iso(now)
    params = params_from(s)
    anchors = app.gazetteer if s.entity_anchors else None
    keep_ids = repo.clear_auto() if rebuild else {}
    pending = repo.unassigned()
    if not pending:
        out["aged"] = repo.save(new_events=[], joins=[], algo=algo_id(s), now_s=now_s, window_hours=s.window_hours)["aged"]
        repo.refresh_bands(now_s, s.window_hours)
        return out
    primaries = [r for r in pending if r["dup_of"] is None]
    children = [r for r in pending if r["dup_of"] is not None]
    oldest = min((datetime.fromisoformat(r["story_utc"]) for r in primaries), default=now)
    if not rebuild:
        oldest = max(oldest, now - timedelta(days=s.lookback_days))
    window_rows = repo.window(iso(oldest - params.window))
    new_ids = {r["article_id"] for r in primaries}
    by_event: dict[int, list[dict]] = {}
    context = []
    for r in window_rows:
        if r["event_id"] is not None:
            by_event.setdefault(r["event_id"], []).append(r)
        elif r["article_id"] not in new_ids:
            context.append(r)
    times = repo.event_times(sorted(by_event))
    existing = [ev.Existing(eid, datetime.fromisoformat(times[eid][0]), datetime.fromisoformat(times[eid][1]),
                            tuple(_doc(m, anchors) for m in rows))
                for eid, rows in by_event.items() if eid in times]
    placements = ev.cluster([_doc(r, anchors) for r in primaries], existing,
                            context=[_doc(r, anchors) for r in context], vectorizer=vectorizer, params=params)
    uid_of = {r["article_id"]: r["uid"] for r in primaries}
    new_events: dict[object, tuple[str, list]] = {}
    joins: list[tuple[int, int, float | None]] = []
    event_of: dict[int, object] = {}
    for p in placements:
        event_of[p.article_id] = p.event_key
        if p.new_event:
            new_events[p.event_key] = (uid_of[p.article_id], [(p.article_id, None)])
        elif p.event_key in new_events:
            new_events[p.event_key][1].append((p.article_id, p.similarity))
        else:
            joins.append((p.event_key, p.article_id, p.similarity))
    for c in children:  # a near-duplicate follows its primary; it is never clustered on its own
        key = event_of.get(c["dup_of"])
        if key is None:
            key = repo.event_for_article(c["dup_of"])
        if key is None:
            out["skipped"] += 1
            continue
        if key in new_events:
            new_events[key][1].append((c["article_id"], None))
        else:
            joins.append((key, c["article_id"], None))
        out["followers"] += 1
    res = repo.save(new_events=list(new_events.values()), joins=joins, algo=algo_id(s), now_s=now_s,
                    window_hours=s.window_hours, keep_ids=keep_ids)
    repo.refresh_bands(now_s, s.window_hours)
    out.update(placed=len(placements), created=res["created"], joined=sum(1 for p in placements if not p.new_event),
               aged=res["aged"])
    return out
