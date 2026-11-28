"""`newsmon events`: build or update events on the database, then list multi-item events with their timelines.

Works on an existing database: the first run places every article that is in no event yet (an incremental pass, the
same one each collection cycle runs); `--rebuild` recomputes every automatic event (after changing `events.threshold`
or `events.window_hours`). Headlines and links pass through DisplayPolicy, exactly as in the queue: a source whose
licence does not allow its headline to be displayed shows "(표시 제한)".

Text output is Markdown (one heading per event, one bullet per item), so it can be pasted into a report as it is.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import timedelta

from newsmon.cli import register

KIND_KO = {"first": "최초", "repeat": "반복", "development": "진전", "correction": "정정", "withdrawal": "철회",
           "kill": "취소"}
BAND_KO = {"flash": "속보", "report": "보고", "review": "검토", "drop": "제외"}
HIDDEN = "(표시 제한)"


def _cfg(p) -> None:
    from newsmon.ops.commands import _common
    _common(p)
    p.add_argument("--hours", type=float, default=0,
                   help="only events with an item first seen in the last N hours (default 0 = all)")
    p.add_argument("--min-members", type=int, default=2,
                   help="distinct items per event; near-duplicate copies are not counted (default 2)")
    p.add_argument("--limit", type=int, default=200, help="events to show (default 200)")
    p.add_argument("--rebuild", action="store_true", help="recompute every automatic event before listing")
    p.add_argument("--json", action="store_true", help="JSON instead of Markdown text")


def _item(m: dict, tz: str) -> dict:
    from newsmon.licence.policy import DisplayPolicy
    from newsmon.web.service import kst_full
    shown = DisplayPolicy.render({**m, "description_text": None, "body_text": None, "ai": None})
    return {"kind": m["kind"], "novelty": m["novelty"], "new_source": m["new_source"], "band": m["band"],
            "uid": m["uid"], "source_key": m["source_key"], "source_name": m["source_name"], "lang": m["lang"],
            "status": m["status"], "near_duplicate": m["dup_of"] is not None, "similarity": m["similarity"],
            "first_seen_utc": m["first_seen_utc"], "published_utc": m["published_utc"], "story_utc": m["story_utc"],
            "story_kst": kst_full(m["story_utc"], tz), "headline": shown["headline"], "link": shown["link"],
            "restricted": shown["restricted"], "synthetic": bool(m["synthetic"])}


def build(app, *, hours: float = 0, min_members: int = 2, limit: int = 200, rebuild: bool = False) -> dict:
    """Run one events pass, then collect the listing (the JSON document `--json` prints)."""
    from newsmon.pipeline.normalise import iso
    from newsmon.runtime.events import algo_id, update_events
    t0 = time.perf_counter()
    stats = update_events(app, rebuild=rebuild)
    stats["seconds"] = round(time.perf_counter() - t0, 3)
    seen_since = iso(app.clock.now() - timedelta(hours=hours)) if hours else None
    tz = app.settings.timezone
    events = []
    for e in app.events.list_events(seen_since=seen_since, min_primaries=max(1, min_members), limit=limit):
        events.append({k: e[k] for k in ("event_id", "uid", "status", "first_seen_utc", "last_update_utc", "members",
                                         "primaries", "independent_sources", "langs", "sources", "algo")}
                      | {"band": e["final_band"] or "drop",
                         "timeline": [_item(m, tz) for m in app.events.timeline(e["event_id"])]})
    s = app.settings.events
    return {"generated_utc": iso(app.clock.now()), "algo": algo_id(s), "enabled": s.enabled, "pass": stats,
            "counts": app.events.counts(), "filter": {"hours": hours, "min_members": min_members, "limit": limit},
            "events": events}


def markdown(doc: dict) -> str:
    f = doc["filter"]
    scope = f"최근 {f['hours']:g}시간에 수집된 기사가 있는 사건" if f["hours"] else "전체 기간"
    p, c = doc["pass"], doc["counts"]
    lines = [f"# 사건 목록 ({scope}, 기사 {f['min_members']}건 이상): {len(doc['events'])}건", "",
             f"- 알고리즘 `{doc['algo']}` · 전체 사건 {c['events']} · 다건 사건 {c['multi']} · 소속 기사 {c['members']}",
             f"- 이번 실행: 배치 {p['placed']} · 신규 사건 {p['created']} · 기존 사건 합류 {p['joined']} · 중복 기사 동반 "
             f"{p['followers']} · {p.get('seconds', 0):.2f}초" + (" · 재계산" if p.get("rebuilt") else "")]
    if not doc["enabled"]:
        lines.append("- 사건 추적이 꺼져 있습니다 (settings.yaml `events.enabled: false`).")
    for e in doc["events"]:
        langs = "/".join(e["langs"]) or "-"
        lines += ["", f"## 사건 {e['event_id']} · 기사 {e['members']}건 · 독립 출처 {e['independent_sources']} · {langs} · "
                      f"{BAND_KO.get(e['band'], e['band'])} · {'진행' if e['status'] == 'open' else '휴면'}"]
        for m in e["timeline"]:
            head = (m["headline"] or HIDDEN).replace("\n", " ")
            tags = [t for t, on in (("중복", m["near_duplicate"]), ("제한 표시", m["restricted"]),
                                    ("합성", m["synthetic"])) if on]
            lines.append(f"- {m['story_kst']} · {KIND_KO.get(m['kind'], m['kind'])} · {m['source_name']} · {head}"
                         + (f" ({', '.join(tags)})" if tags else ""))
    return "\n".join(lines) + "\n"


def _run(args) -> int:
    from newsmon.ops.commands import _app
    app = _app(args, setup_logging=False)
    try:
        doc = build(app, hours=args.hours, min_members=args.min_members, limit=args.limit, rebuild=args.rebuild)
    finally:
        app.close()
    if args.json:
        json.dump(doc, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(markdown(doc))
    return 0


register("events", "group articles into events and list multi-item events with their timelines", _cfg, _run)
