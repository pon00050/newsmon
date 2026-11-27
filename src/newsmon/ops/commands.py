"""Operational CLI commands (IR-06; Release A subset: init, migrate, collect/run-once, status, search, rerank, serve).

Every command reads NEWSMON_CONFIG_DIR / NEWSMON_DATA_DIR (or --config / --data) and nothing else.
Deferred to later tasks: backup, restore, export, import, config export/import, source takedown, doctor, sbom.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from newsmon.cli import register
from newsmon.config.loader import ConfigError, load_config


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", type=Path, help="config directory (default: $NEWSMON_CONFIG_DIR)")
    p.add_argument("--data", type=Path, help="data directory (default: $NEWSMON_DATA_DIR)")


def _app(args, *, setup_logging: bool = True):
    from newsmon.app import App
    try:
        cfg = load_config(data_dir=args.data, config_dir=args.config)
    except ConfigError as exc:
        print(f"newsmon: configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2)
    return App(cfg, setup_logging=setup_logging)


def _print_report(rep) -> None:
    print(f"cycle {rep.correlation_id}: {len(rep.feeds)} feed(s), {rep.new_articles} new article(s), "
          f"{len(rep.failed)} failed, {rep.ranked} ranked")
    for f in rep.feeds:
        extra = f" error={f.error_class} stage={f.stage} detail={f.detail}" if f.status == "error" else ""
        print(f"  {f.source_key:<22} {f.status:<12} attempts={f.attempts} entries={f.entries} new={f.new} "
              f"quarantined={f.quarantined}{extra}")
    if rep.rank_error:
        print(f"  ranking failed: {rep.rank_error}")


# --- init / migrate ------------------------------------------------------------------------------------------------------
def _init(args) -> int:
    app = _app(args)
    try:
        c = app.articles.counts()
        print(f"initialised {app.cfg.paths.db_path} (schema ok, {len(app.sources.status_rows())} source(s), "
              f"{len(app.profiles)} profile(s), {c['articles']} article(s))")
        for f, err in app.profile_errors.items():
            print(f"  profile {f} rejected: {err}")
    finally:
        app.close()
    return 0


register("init", "create or upgrade the database and load the configuration", _common, _init)
register("migrate", "apply pending schema migrations", _common, _init)


# --- collect -------------------------------------------------------------------------------------------------------------
def _collect_cfg(p):
    _common(p)
    p.add_argument("--force", action="store_true", help="poll every active source now, ignoring intervals")
    p.add_argument("--source", action="append", help="only this source key (repeatable)")
    p.add_argument("--loop", action="store_true", help="keep collecting; each source runs at its own interval")
    p.add_argument("--max-cycles", type=int, default=0, help="with --loop: stop after N cycles (0 = forever)")
    p.add_argument("--tick", type=float, default=10.0, help="with --loop: seconds between due-checks")


def _collect(args) -> int:
    app = _app(args)
    app.media_async = bool(args.loop)  # a long-running loop must not wait on footage checks between feed polls
    try:
        n = 0
        while True:
            rep = app.collect(force=args.force and n == 0, only=set(args.source) if args.source else None)
            _print_report(rep)
            n += 1
            if not args.loop or (args.max_cycles and n >= args.max_cycles):
                break
            time.sleep(args.tick)
    except KeyboardInterrupt:
        print("stopped")
    finally:
        app.close()
    return 0


register("collect", "run one collection cycle (or --loop)", _collect_cfg, _collect)
register("run-once", "alias of collect", _collect_cfg, _collect)


# --- status / search / rerank ----------------------------------------------------------------------------------------------
def _status(args) -> int:
    app = _app(args, setup_logging=False)
    try:
        print(f"database: {app.cfg.paths.db_path}  integrity={'ok' if app.db.integrity_ok() else 'FAILED'}")
        print(f"{app.ai_status.header_label()}  profiles: {', '.join(app.profiles) or '-'}")
        for f, err in app.profile_errors.items():
            print(f"  profile {f} REJECTED: {err}")
        print("counts: " + ", ".join(f"{k}={v}" for k, v in app.articles.counts().items()))
        print(f"{'source':<22} {'active':<6} {'last':<13} {'err':<5} {'articles':>8}  detail")
        for r in app.sources.status_rows():
            last = r["last_run"]
            detail = r["inactive_reason"] or ""
            if last and last["status"] == "error":
                detail = f"{last['error_class']}: {last['error_detail'] or ''}"
            print(f"{r['key']:<22} {'yes' if r['active'] else 'no':<6} {(last or {}).get('status', '-'):<13} "
                  f"{r['error_streak']:<5} {r['articles']:>8}  {detail[:80]}")
    finally:
        app.close()
    return 0


register("status", "show sources, last fetch results and counts", _common, _status)


def _search_cfg(p):
    _common(p)
    p.add_argument("query")
    p.add_argument("--lang")
    p.add_argument("--limit", type=int, default=20)


def _search(args) -> int:
    from newsmon.web.service import Service
    app = _app(args, setup_logging=False)
    try:
        res = Service(app).search(args.query, lang=args.lang, limit=args.limit)
        if res["aliases"]:
            print(f"aliases: {', '.join(res['aliases'])}")
        for r in res["rows"]:
            print(f"{r['final_band'] or '-':<7} {r['lang'] or '-':<3} {r['source_name'][:20]:<20} {r['headline']}")
        print(f"{len(res['rows'])} result(s)")
    finally:
        app.close()
    return 0


register("search", "search collected articles", _search_cfg, _search)


def _rerank(args) -> int:
    app = _app(args)
    try:
        errs = app.load_profiles()
        for f, e in errs.items():
            print(f"profile {f} rejected: {e}")
        print(f"ranked {app.rerank()} article(s) with profile {app.primary_profile[1].key if app.primary_profile else '-'}")
    finally:
        app.close()
    return 0


register("rerank", "reload profiles and re-rank stored articles", _common, _rerank)


# --- serve ----------------------------------------------------------------------------------------------------------------
def _serve_cfg(p):
    _common(p)
    p.add_argument("--port", type=int)
    p.add_argument("--auto-collect", action="store_true", help="also collect in the background at each source's interval")


def _serve(args) -> int:
    import uvicorn

    from newsmon.web.app import create_app
    app = _app(args)
    host = app.settings.bind_host
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"newsmon: refusing to bind {host}: Release A serves loopback only (no authentication yet)", file=sys.stderr)
        return 2
    app.media_async = True  # in the web server, footage checks run on their own thread, never inside a collection
    web = create_app(app, auto_collect=args.auto_collect)
    print(f"newsmon UI on http://{host}:{args.port or app.settings.bind_port}/  ({app.ai_status.header_label()})")
    try:
        uvicorn.run(web, host=host, port=args.port or app.settings.bind_port, log_level="warning")
    finally:  # uvicorn re-raises KeyboardInterrupt after a Ctrl+C shutdown; close the database either way
        app.close()
    return 0


register("serve", "run the local web UI (loopback only)", _serve_cfg, _serve)


# --- media-check (duty 2) ------------------------------------------------------------------------------------------------
def _media_cfg(p):
    _common(p)
    p.add_argument("--limit", type=int, default=20, help="clips to check in this run (default 20)")


def _media(args) -> int:
    app = _app(args)
    try:
        if app.media_tool is None:
            print("ffmpeg/ffprobe not found on PATH: clips are not checked")
            return 1
        rep = app.check_media(limit=args.limit)
        print(f"checked={rep['checked']} ok={rep['ok']} needs_check={rep['needs_check']} unreadable={rep['unreadable']} "
              f"missing={rep['missing']}")
    finally:
        app.close()
    return 0


register("media-check", "check wire video clips now: technical facts, black/silence, thumbnails (duty 2)", _media_cfg,
         _media)


# --- enrich (Release A.1) ----------------------------------------------------------------------------------------------
def _enrich_cfg(p):
    _common(p)
    p.add_argument("--uid", action="append", help="enrich this article (manual selection; repeatable)")
    p.add_argument("--limit", type=int, help="override ai.selection.max_items_per_cycle for this run")
    p.add_argument("--stale", action="store_true",
                   help="reassess articles whose assessment predates the current profile, model or prompt")


def _enrich(args) -> int:
    app = _app(args)
    try:
        if args.stale:
            print(f"stale assessments: {len(app.stale_ai())}")
        if not app.enricher.active:
            print(f"AI is off: {app.enricher.disabled_reason or ('paused' if app.enricher.paused else 'not configured')}")
            return 0
        rep = app.enrich(uids=args.uid, limit=args.limit, stale=args.stale)
        print(f"selected={rep.selected} called={rep.called} cached={rep.cached} done={rep.done} review={rep.review} "
              f"not_allowed={rep.not_allowed} cost_usd={rep.cost_usd:.6f}" + (f" stopped: {rep.stopped}" if rep.stopped else ""))
        for e in rep.errors:
            print(f"  review: {e}")
    finally:
        app.close()
    return 0


register("enrich", "run optional AI enrichment now (Release A.1)", _enrich_cfg, _enrich)


# --- export-public (static website) ------------------------------------------------------------------------------------
def _export_public_cfg(p):
    _common(p)
    p.add_argument("--out", type=Path, required=True, help="JSON file to write (schema newsmon-public/1)")
    p.add_argument("--dataset", choices=["synthetic", "live"], required=True,
                   help="synthetic: only synthetic sources' items; live: only real sources' items")
    p.add_argument("--previous", type=Path, help="earlier published file to roll forward (bounded by the two options below)")
    p.add_argument("--max-items", type=int, default=500)
    p.add_argument("--max-age-days", type=int, default=14)


def _export_public(args) -> int:
    import json

    from newsmon.publish import export
    app = _app(args)
    try:
        doc = export.build(app, args.dataset, limit=args.max_items)
        refused = doc.pop("_refused", {})
        refused_uids = set(doc.pop("_refused_uids", []))
        wrong = [i["uid"] for i in doc["items"] if bool(i["synthetic"]) != (args.dataset == "synthetic")]
        if wrong:  # a synthetic source in a live export or the reverse: never mix them
            doc["items"] = [i for i in doc["items"] if i["uid"] not in wrong]
            doc["stats"] = export.stats(doc["items"])
        if args.previous and args.previous.exists():
            try:
                prev = json.loads(args.previous.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                prev = None
                print("previous snapshot unreadable; starting a new one", file=sys.stderr)
            doc = export.merge_previous(doc, prev, max_items=args.max_items, max_age_days=args.max_age_days,
                                        exclude_uids=refused_uids)
        export.write(doc, args.out)
    except export.PublicExportError as exc:
        print(f"newsmon: public export refused: {exc}", file=sys.stderr)
        return 1
    finally:
        app.close()
    print(f"wrote {args.out}: {doc['stats']['items']} item(s) from {len(doc['sources'])} permitted source(s); "
          f"withheld by the publication gate: {sum(refused.values())} " + (str(refused) if refused else "")
          + (f"; dropped {len(wrong)} item(s) of the other dataset" if wrong else ""))
    return 0


register("export-public", "write the public website dataset (only publicly redistributable fields)",
         _export_public_cfg, _export_public)
