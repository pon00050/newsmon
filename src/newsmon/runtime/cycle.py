"""One collection cycle: collect -> parse -> normalise -> licence gate + persist -> dedup -> rank -> index (T-08).

Every source is isolated: a failure in one feed (network, parse, a bad item, even an unexpected exception) is recorded
against that feed with its stage and error class, and the cycle moves on (Release A item 11). Each attempt writes one
`fetch_run` row; each rejected record writes one `quarantine` row with `<stage>: <reason>`.

(The backlog put the orchestrator at pipeline/cycle.py; it lives in runtime/ because it drives I/O adapters, and
pipeline/ must stay free of I/O imports, NFR-21.)
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from newsmon.ai.enrich import screen
from newsmon.connectors.base import poll_with_retry
from newsmon.connectors.directory import DirectoryConnector
from newsmon.connectors.feed import FeedConnector, FeedParseError
from newsmon.connectors.wire import WireParseError
from newsmon.domain.enums import PollStatus
from newsmon.obs.logging import event, new_correlation_id
from newsmon.pipeline.normalise import Quarantined, RegexRejected, SourceRules, iso, normalise

if TYPE_CHECKING:
    from newsmon.app import App

STAGES = ("collect", "parse", "normalise", "permission", "persist", "dedup", "rank", "search", "presentation")


@dataclass
class FeedOutcome:
    source_key: str
    feed_id: int
    status: str  # ok | not_modified | empty | error | skipped
    error_class: str | None = None
    stage: str | None = None
    detail: str | None = None
    attempts: int = 0
    entries: int = 0
    new: int = 0
    quarantined: int = 0


@dataclass
class CycleReport:
    correlation_id: str
    started_utc: str
    finished_utc: str = ""
    feeds: list[FeedOutcome] = field(default_factory=list)
    ranked: int = 0
    rank_error: str | None = None
    ai: object | None = None  # EnrichReport when the AI stage ran
    ai_error: str | None = None
    alerts: dict | None = None
    alert_error: str | None = None
    media: dict | None = None
    media_error: str | None = None

    @property
    def new_articles(self) -> int:
        return sum(f.new for f in self.feeds)

    @property
    def failed(self) -> list[FeedOutcome]:
        return [f for f in self.feeds if f.status == "error"]


def run_cycle(app: "App", *, force: bool = False, only: set[str] | None = None) -> CycleReport:
    cid = new_correlation_id("cycle")
    now = app.clock.now()
    report = CycleReport(cid, iso(now))
    for feed in app.sources.active_feeds():
        if only and feed.source_key not in only:
            continue
        if not force and feed.next_due_utc and feed.next_due_utc > iso(now):
            continue
        try:
            outcome = _collect_feed(app, feed)
        except Exception as exc:  # last-resort isolation: never let one source stop the cycle
            outcome = FeedOutcome(feed.source_key, feed.feed_id, "error", "io", "collect", f"{exc.__class__.__name__}: {exc}")
            event("feed_failed", logging.ERROR, source=feed.source_key, stage="collect", error_class="io",
                  detail=outcome.detail)
        report.feeds.append(outcome)
    try:
        report.ranked = app.rerank()
    except Exception as exc:
        report.rank_error = f"{exc.__class__.__name__}: {exc}"
        event("rank_failed", logging.ERROR, stage="rank", error_class="io", detail=report.rank_error)
    # optional AI (Release A.1): after the deterministic stages are committed, isolated from them
    if app.enricher.active and app.primary_profile and report.rank_error is None:
        try:
            report.ai = app.enricher.run(app.primary_profile[1])
            if report.ai.called or report.ai.cached:
                app.rerank()
        except Exception as exc:  # an AI defect must never stop collection, ranking or search
            report.ai_error = f"{exc.__class__.__name__}: {exc}"
            event("ai_failed", logging.ERROR, stage="ai", error_class="io", detail=report.ai_error)
    try:  # an alert defect must never stop collection (M1)
        report.alerts = app.raise_alerts()
    except Exception as exc:
        report.alert_error = f"{exc.__class__.__name__}: {exc}"
        event("alerts_failed", logging.ERROR, stage="presentation", error_class="io", detail=report.alert_error)
    try:  # a footage-check defect must never stop collection either (duty 2)
        report.media = app.kick_media()
    except Exception as exc:
        report.media_error = f"{exc.__class__.__name__}: {exc}"
        event("media_check_failed", logging.ERROR, stage="presentation", error_class="io", detail=report.media_error)
    report.finished_utc = iso(app.clock.now())
    event("cycle_done", feeds=len(report.feeds), new=report.new_articles, failed=len(report.failed), ranked=report.ranked)
    return report


def _connector(app: "App", feed, src):
    snapshot = src.flags.snapshot_json()
    if feed.kind == "directory":
        # one connector per feed for the life of the app: it holds the previous scan for the stability check
        cached = app.dir_connectors.get(feed.feed_id)
        if cached is not None and cached.licence_snapshot == snapshot:
            return cached
        root = app.resolve_inbox(feed.url_or_path)
        conn = app.dir_connectors[feed.feed_id] = DirectoryConnector(
            source_key=src.key, root=root, licence_snapshot=snapshot, clock=app.clock,
            seen=lambda rel, sha: app.sources.ledger_has(feed.feed_id, rel, sha),
            present=lambda: app.sources.ledger_present(feed.feed_id), max_bytes=app.settings.inbox.max_file_bytes,
            synthetic=src.flags.synthetic, lang_default=src.lang_default, cursor=app.sources.feed_cursor(feed.feed_id))
        return conn
    return FeedConnector(source_key=src.key, url=feed.url_or_path, licence_snapshot=snapshot, fetcher=app.fetcher,
                         robots=app.robots, clock=app.clock, lang_default=src.lang_default, synthetic=src.flags.synthetic,
                         etag=feed.etag, last_modified=feed.last_modified)


def _collect_feed(app: "App", feed) -> FeedOutcome:
    src = app.sources.source_ref(feed.source_id)
    out = FeedOutcome(src.key, feed.feed_id, "ok")
    now = app.clock.now()
    valid_until = app.sources.valid_until(src.source_id)
    if valid_until is not None and now.date() > valid_until:  # FR-30(b): ingestion stops after valid_until
        app.sources.set_inactive(src.source_id, f"licence expired on {valid_until} (FR-30(b))")
        event("source_skipped", logging.WARNING, source=src.key, stage="permission", reason="valid_until passed")
        return FeedOutcome(src.key, feed.feed_id, "skipped", None, "permission", "licence expired")
    try:
        bp, live, sk = app.sources.source_rules(src.source_id)
        rules = SourceRules.build(bp, live, sk)
    except RegexRejected as exc:
        rules = SourceRules()
        event("source_rules_rejected", logging.WARNING, source=src.key, stage="normalise", detail=str(exc))
    conn = _connector(app, feed, src)
    started = iso(now)
    attempts = poll_with_retry(conn.poll, sleep=app.sleep)
    for a in attempts[:-1]:
        app.sources.record_run(feed.feed_id, started, iso(app.clock.now()), a, None, None)
        event("fetch_attempt", logging.WARNING, source=src.key, stage="collect", status=a.label, attempt=a.attempts)
    final = attempts[-1]
    run_id = app.sources.record_run(feed.feed_id, started, iso(app.clock.now()), final, None, None)
    out.attempts = len(attempts)
    out.status = str(final.status)
    interval = app.settings.inbox.scan_seconds if feed.kind == "directory" else max(feed.poll_seconds,
                                                                                    app.settings.fetch.min_poll_seconds)
    app.sources.set_next_due(feed.feed_id, iso(now + timedelta(seconds=interval)))
    if final.status is PollStatus.ERROR:
        out.error_class, out.stage, out.detail = str(final.error_class), "collect", final.error_detail
        event("fetch_failed", logging.WARNING, source=src.key, stage="collect", error_class=out.error_class,
              detail=final.error_detail, attempts=len(attempts))
        return out
    if final.status is PollStatus.OK and feed.kind != "directory":
        app.sources.save_validators(feed.feed_id, final.etag, final.last_modified)
    if final.next_cursor is not None:
        app.sources.save_cursor(feed.feed_id, final.next_cursor)

    for unit in final.raw_units:
        if isinstance(conn, DirectoryConnector):
            _ingest_file(app, conn, feed, src, unit, rules, run_id, out)
        else:
            try:
                items = conn.parse(unit)
            except Exception as exc:  # a FeedParseError message is ours; anything else may quote the feed
                why = str(exc) if isinstance(exc, FeedParseError) else exc.__class__.__name__
                out.status, out.error_class, out.stage, out.detail = "error", "parse", "parse", why
                app.sources.quarantine(run_id, unit.raw_ref, f"parse: {why}", iso(app.clock.now()))
                app.sources.update_run_counts(run_id, entries=0, new_articles=0, status="error", error_class="parse",
                                              error_detail=why[:500])
                event("parse_failed", logging.WARNING, source=src.key, stage="parse", error_class="parse", detail=why)
                return out
            _ingest_items(app, src, feed, items, rules, run_id, out)
    if isinstance(conn, DirectoryConnector):
        scan = conn.last_scan
        for r in scan.refused:
            app.sources.ledger_record(feed.feed_id, r.rel_path, r.size, r.mtime_ns, r.sha256 or "-", None, "quarantined",
                                      f"io: {r.reason}", iso(app.clock.now()))
            app.sources.quarantine(run_id, r.rel_path, f"collect: io: {r.reason}", iso(app.clock.now()))
            out.quarantined += 1
            event("file_refused", logging.WARNING, source=src.key, stage="collect", error_class="io",
                  file=r.rel_path, reason=r.reason)
        for rel, sha in scan.gone:
            app.sources.ledger_mark_gone(feed.feed_id, rel, sha)
    if out.entries == 0 and final.status is PollStatus.OK and feed.kind != "directory" and out.status == "ok":
        out.status = "empty"
        app.sources.update_run_counts(run_id, entries=0, new_articles=0, status="empty")
    else:
        app.sources.update_run_counts(run_id, entries=out.entries, new_articles=out.new)
    event("fetch_done", source=src.key, stage="collect", status=out.status, entries=out.entries, new=out.new,
          quarantined=out.quarantined)
    return out


def _ingest_items(app, src, feed, items, rules, run_id, out: FeedOutcome) -> None:
    for item in items:
        out.entries += 1
        try:
            n = normalise(item, rules, lang_hint=src.lang_default)
        except Quarantined as exc:
            out.quarantined += 1
            app.sources.quarantine(run_id, item.uri or item.url or item.raw_ref, f"normalise: {exc}", iso(app.clock.now()))
            event("item_quarantined", logging.INFO, source=src.key, stage="normalise", reason=str(exc),
                  ref=item.uri or item.url)
            continue
        try:
            res = app.articles.store(src, n, feed_id=feed.feed_id, now=app.clock.now())
        except Exception as exc:
            out.quarantined += 1
            app.sources.quarantine(run_id, item.uri or item.url or item.raw_ref, f"persist: {exc.__class__.__name__}",
                                   iso(app.clock.now()))
            event("item_failed", logging.ERROR, source=src.key, stage="persist", error_class="io",
                  detail=exc.__class__.__name__)
            continue
        if res.action in ("new", "killed"):
            out.new += 1
        if res.action in ("new", "revision") and res.article_id:
            hits = screen((n.item.headline, n.item.description_text, n.item.body_text))  # FR-14: every mode
            app.ai_repo.set_prefilter(res.article_id, bool(hits))
            if hits:
                event("injection_prefilter_hit", logging.WARNING, source=src.key, stage="normalise",
                      article_id=res.article_id, patterns=len(hits))  # a count: the matches are source text


def _ingest_file(app, conn: DirectoryConnector, feed, src, unit, rules, run_id, out: FeedOutcome) -> None:
    meta = unit.meta
    now_s = iso(app.clock.now())
    media = conn.media_info(unit)
    if media:
        app.sources.ledger_record(feed.feed_id, meta["rel_path"], meta["size"], meta["mtime_ns"], unit.raw_sha256, "media",
                                  "media", None, now_s)
        app.articles.update_media(Path(meta["rel_path"]).name, unit.raw_sha256, meta["size"], media[1])
        return
    fmt = "unknown"
    try:
        fmt = conn.classify(unit)
        items = conn.parse(unit)
    except Exception as exc:  # one bad file is quarantined; it never stops the rest of the inbox
        # a WireParseError message is written by the parser; anything else may quote the file, so only its type is kept
        why = str(exc) if isinstance(exc, WireParseError) else exc.__class__.__name__
        out.quarantined += 1
        app.sources.ledger_record(feed.feed_id, meta["rel_path"], meta["size"], meta["mtime_ns"], unit.raw_sha256, fmt,
                                  "quarantined", f"parse: {why}", now_s)
        app.sources.quarantine(run_id, meta["rel_path"], f"parse: {why}", now_s)
        event("file_quarantined", logging.WARNING, source=src.key, stage="parse", error_class="parse",
              file=meta["rel_path"], detail=why)
        return
    _ingest_items(app, src, feed, items, rules, run_id, out)
    app.sources.ledger_record(feed.feed_id, meta["rel_path"], meta["size"], meta["mtime_ns"], unit.raw_sha256, fmt,
                              "ingested", None, now_s)
    # media named by a sidecar: record path, sha256 and size only; the file is never copied (FR-29(e))
    base = Path(meta["abs_path"]).parent
    for item in items:
        for href in item.media_refs:
            p = (base / href)
            try:
                if p.resolve().is_relative_to(conn.root.resolve()) and p.is_file():
                    with p.open("rb") as fh:  # hashed in chunks: a video is never read into memory whole
                        head = fh.read(16)
                        fh.seek(0)
                        sha = hashlib.file_digest(fh, "sha256").hexdigest()
                    kind = conn.media_info(type(unit)(raw_ref=href, raw_sha256="", payload=head,
                                                      received_utc=unit.received_utc))
                    app.articles.update_media(href, sha, p.stat().st_size,
                                              kind[1] if kind else "application/octet-stream")
            except OSError:
                pass
