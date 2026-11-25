"""Static public export (schema `newsmon-public/1`) for the project website's dashboard.

It reads what the normal pipeline stored and ranked; it does not collect, deduplicate or rank on its own. Every item
passes `gate.decide` and is reduced to `gate.public_record`. `validate` is the last check before a file is written and
is also run by CI over the built site: it rejects any unexpected field, any non-http(s) link, a headline from a
metadata-only source, and a mix of synthetic and real items.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newsmon import __version__
from newsmon.publish.gate import decide, public_record
from newsmon.registry.loader import load_sources

SCHEMA = "newsmon-public/1"
BANDS = ("flash", "report", "review", "drop")
TOP_KEYS = {"schema", "dataset", "generated_utc", "newsmon_version", "profile", "notice", "sources", "stats", "items"}
ITEM_KEYS = {"uid", "source_key", "source_name", "lang", "published_utc", "first_seen_utc", "headline", "link", "band",
             "score", "topics", "entities", "duplicates", "synthetic"}
SOURCE_KEYS = {"key", "name", "public_level", "basis", "basis_url", "attribution", "items", "last_success_utc",
               "last_status"}
NOTICES = {
    "synthetic": "Synthetic demonstration data: every item was written for the Newsmon project and is fictional.",
    "live": "Headlines and links from sources whose public redistribution is documented. Each item links to its "
            "original publisher; article text is not reproduced. Topics and priority are Newsmon's own rule-based "
            "labels, not the publisher's.",
}


class PublicExportError(ValueError):
    pass


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")


def build(app, dataset: str, *, limit: int = 500) -> dict:
    if dataset not in NOTICES:
        raise PublicExportError(f"unknown dataset {dataset!r}")
    now = app.clock.now()
    p = app.config_path("sources.yaml")
    specs = {s.key: s for s in (load_sources(p) if p else [])}
    items, refused, refused_uids = [], Counter(), []
    for row in app.articles.public_candidates(limit=5000):
        d = decide(row, specs.get(row["source_key"]), now)
        if d.level == "none":
            refused[d.reason] += 1
            refused_uids.append(row["uid"])
            continue
        items.append(public_record(row, d.level))
        if len(items) >= limit:
            break
    prof = app.primary_profile
    status = {r["key"]: r for r in app.sources.status_rows()}
    per_source = Counter(i["source_key"] for i in items)
    sources = []
    for key, s in sorted(specs.items()):
        if s.public_redistribution == "none":
            continue
        st = status.get(key, {})
        last = st.get("last_run") or {}
        sources.append({"key": key, "name": s.name, "public_level": s.public_redistribution,
                        "basis": s.public_redistribution_basis, "basis_url": s.public_redistribution_url,
                        "attribution": s.attribution_text, "items": per_source.get(key, 0),
                        "last_success_utc": st.get("last_success_utc"),
                        "last_status": last.get("status") or ("inactive" if not st.get("active") else "never")})
    doc = {
        "schema": SCHEMA, "dataset": dataset, "generated_utc": _iso(now), "newsmon_version": __version__,
        "profile": {"key": prof[1].key if prof else "", "name": (prof[1].name or prof[1].key) if prof else ""},
        "notice": NOTICES[dataset], "sources": sources, "stats": stats(items), "items": items,
    }
    doc["_refused"] = dict(refused)  # reported by the CLI, removed before writing
    doc["_refused_uids"] = refused_uids  # items seen now and refused: never rolled forward from an earlier snapshot
    return doc


def stats(items: list[dict]) -> dict:
    topics = Counter(t for i in items for t in i["topics"])
    return {"items": len(items), "duplicates_collapsed": sum(i["duplicates"] for i in items),
            "by_band": {b: sum(1 for i in items if i["band"] == b) for b in BANDS},
            "by_lang": dict(Counter(i["lang"] or "unknown" for i in items).most_common()),
            "by_source": dict(Counter(i["source_key"] for i in items).most_common()),
            "by_topic": dict(topics.most_common(30))}


def merge_previous(doc: dict, previous: dict | None, *, max_items: int, max_age_days: int,
                   exclude_uids: set[str] | frozenset[str] = frozenset()) -> dict:
    """Bounded rolling snapshot for scheduled publication: keep earlier published items that are still within the
    window and whose source is still publicly permitted (at the same or a lower level), newest first, capped.
    Items seen in this run and refused by the gate (`exclude_uids`: restricted, withdrawn, ...) are dropped. An item
    withdrawn at its source after publication that no longer appears in the feed cannot be detected; it ages out."""
    if not previous or previous.get("schema") != SCHEMA or previous.get("dataset") != doc["dataset"]:
        return doc
    allowed = {s["key"]: s["public_level"] for s in doc["sources"]}
    cutoff = datetime.fromisoformat(doc["generated_utc"]) - timedelta(days=max_age_days)
    seen = {i["uid"] for i in doc["items"]}
    merged = list(doc["items"])
    for it in previous.get("items", []):
        if not isinstance(it, dict) or set(it) != ITEM_KEYS or it["uid"] in seen or it["uid"] in exclude_uids:
            continue
        level = allowed.get(it["source_key"])
        if level is None:
            continue
        try:
            first = datetime.fromisoformat(it["first_seen_utc"])
        except (TypeError, ValueError):
            continue
        if first < cutoff:
            continue
        it = dict(it)
        if level != "headline":
            it["headline"] = None
        merged.append(it)
        seen.add(it["uid"])
    merged.sort(key=lambda i: i["first_seen_utc"], reverse=True)
    merged = merged[:max_items]
    out = dict(doc, items=merged, stats=stats(merged))
    counts = Counter(i["source_key"] for i in merged)
    out["sources"] = [dict(s, items=counts.get(s["key"], 0)) for s in doc["sources"]]
    return out


def validate(doc: dict) -> None:
    """Raise PublicExportError unless `doc` is exactly the public contract."""
    def fail(msg):
        raise PublicExportError(msg)

    if set(doc) != TOP_KEYS:
        fail(f"top-level keys {sorted(set(doc) ^ TOP_KEYS)} differ from the contract")
    if doc["schema"] != SCHEMA or doc["dataset"] not in NOTICES:
        fail("bad schema or dataset")
    levels = {}
    for s in doc["sources"]:
        if set(s) != SOURCE_KEYS:
            fail(f"source {s.get('key')}: keys differ from the contract")
        if s["public_level"] not in ("metadata", "headline") or not (s["basis"] or "").strip():
            fail(f"source {s['key']}: no public permission or basis")
        levels[s["key"]] = s["public_level"]
    for it in doc["items"]:
        if set(it) != ITEM_KEYS:
            fail(f"item {it.get('uid')}: keys differ from the contract")
        if it["source_key"] not in levels:
            fail(f"item {it['uid']}: source {it['source_key']} is not publicly permitted")
        if it["headline"] is not None and levels[it["source_key"]] != "headline":
            fail(f"item {it['uid']}: headline from a metadata-only source")
        if it["link"] is not None and not str(it["link"]).lower().startswith(("http://", "https://")):
            fail(f"item {it['uid']}: non-http(s) link")
        if it["band"] not in BANDS:
            fail(f"item {it['uid']}: bad band")
        if bool(it["synthetic"]) != (doc["dataset"] == "synthetic"):
            fail(f"item {it['uid']}: synthetic flag does not match dataset {doc['dataset']}")
        for k in ("headline", "source_name"):
            if isinstance(it[k], str) and len(it[k]) > 400:
                fail(f"item {it['uid']}: {k} longer than a headline")


def write(doc: dict, out: Path) -> Path:
    doc = {k: v for k, v in doc.items() if not k.startswith("_")}
    validate(doc)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out)
    return out
