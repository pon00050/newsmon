"""Composition root: builds the one database, the repositories, the fetcher and the loaded configuration.

The CLI, the web UI and the tests all construct an `App`; nothing else wires adapters together.
"""
from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

import yaml

from newsmon.adapters.secrets import EnvSecretStore
from newsmon.config.loader import ConfigError, read_yaml
from newsmon.config.settings import AppConfig
from newsmon.domain.ports import Clock, HttpFetcher, SystemClock
from newsmon.fetcher.client import HttpxFetcher
from newsmon.fetcher.robots import RobotsCache
from newsmon.fetcher.ssrf import SsrfPolicy
from newsmon.obs import logging as obslog
from newsmon.pipeline.normalise import fold, iso
from newsmon.registry.loader import load_sources
from newsmon.ai.enrich import Enricher, merge_band
from newsmon.repo.ai import AIRepo
from newsmon.repo.alerts import AlertRepo
from newsmon.repo.articles import ArticleRepo
from newsmon.repo.assessments import AssessmentRepo
from newsmon.repo.media import MediaRepo
from newsmon.repo.searches import SearchRepo
from newsmon.repo.db import Database
from newsmon.repo.migrate import ensure_workspace, migrate
from newsmon.repo.sources import SourceRepo
from newsmon.rules.engine import ItemFacts, evaluate
from newsmon.rules.profile import Profile, ProfileError, validate_profile


def _inapp(cfg) -> bool:
    """A profile `alerts:` entry turns in-app alerts on unless it is false/empty or lists channels without `inapp`."""
    if not cfg:
        return False
    channels = cfg.get("channels") if isinstance(cfg, dict) else None
    return channels is None or "inapp" in channels


class App:
    def __init__(self, cfg: AppConfig, *, clock: Clock | None = None, fetcher: HttpFetcher | None = None,
                 ssrf_policy: SsrfPolicy | None = None, sleep: Callable[[float], None] = time.sleep,
                 setup_logging: bool = False) -> None:
        self.cfg = cfg
        self.settings = cfg.settings
        self.clock = clock or SystemClock()
        self.sleep = sleep
        self.secrets = EnvSecretStore(cfg.paths.config_dir / ".env" if cfg.paths.config_dir else None)
        if setup_logging:
            obslog.setup(self.secrets.values())
        cfg.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(cfg.paths.db_path)
        migrate(self.db)
        ensure_workspace(self.db, self.settings.workspace_name, self.settings.use_context, iso(self.clock.now()))
        self.sources = SourceRepo(self.db)
        self.articles = ArticleRepo(self.db)
        self.assessments = AssessmentRepo(self.db)
        self.alerts = AlertRepo(self.db)
        self.media = MediaRepo(self.db)
        self.searches = SearchRepo(self.db)
        from newsmon.adapters.ffmpeg_media import FfmpegMedia
        self.media_tool = FfmpegMedia.available()  # None without ffmpeg/ffprobe on PATH: clips stay unchecked
        self.media_async = False  # True (web UI, collect --loop): checks run on their own thread, outside collect_lock
        self._media_lock = threading.Lock()
        self._media_thread: threading.Thread | None = None
        f = self.settings.fetch
        self.fetcher = fetcher or HttpxFetcher(user_agent=f.user_agent, policy=ssrf_policy or SsrfPolicy(),
                                               max_bytes=f.max_bytes, timeout=f.timeout_seconds)
        self.robots = RobotsCache(self.fetcher, f.user_agent, clock=self.clock, cache_hours=f.robots_cache_hours)
        self.ai_repo = AIRepo(self.db)
        self.enricher = self._build_enricher()
        self.ai_status = self.enricher  # header_label(): 꺼짐 / 중단 / 켜짐
        self.gazetteer: dict[str, list[str]] = {}
        self.profiles: dict[str, tuple[int, Profile]] = {}
        self.profile_errors: dict[str, str] = {}
        self.collect_lock = threading.Lock()
        self.last_report = None
        self.dir_connectors: dict = {}
        self.load_gazetteer()
        self.sync_registry()
        self.load_profiles()
        self.backfill_prefilter()

    def _build_enricher(self, provider=None) -> Enricher:
        """Optional AI (Release A.1). Without the capability switch or the key, the enricher is inert and O1 runs."""
        ai = self.settings.ai
        reason = ""
        if provider is None and ai.capabilities.enrich:
            key = self.secrets.get(ai.anthropic_secret_name)
            if key:
                from newsmon.adapters.anthropic_ai import AnthropicProvider
                provider = AnthropicProvider(key, timeout=ai.request_timeout_seconds, max_retries=ai.max_retries)
            else:
                reason = f"{ai.anthropic_secret_name} not set"
        elif not ai.capabilities.enrich:
            reason = "ai.capabilities.enrich is false"
        return Enricher(provider=provider, repo=self.ai_repo, settings=ai, clock=self.clock, enabled_reason=reason)

    def backfill_prefilter(self) -> int:
        """Screen articles stored before the injection pre-filter existed (migration 0002 defaulted the flag to 0)."""
        from newsmon.ai.enrich import screen
        rows = self.ai_repo.unscreened()
        hits = 0
        for r in rows:
            if screen((r["headline"], r["description_text"], r["body_text"])):
                self.ai_repo.set_prefilter(r["article_id"], True)
                hits += 1
        if rows:
            self.ai_repo.set_state("prefilter_last_id", str(max(r["article_id"] for r in rows)), iso(self.clock.now()))
        return hits

    def use_ai_provider(self, provider) -> None:
        """Inject a provider (tests: the AI stub). The capability switch in settings still decides whether it runs."""
        self.enricher = self._build_enricher(provider)
        self.ai_status = self.enricher

    def stale_ai(self) -> list[int]:
        """Articles whose AI assessment was made for an earlier profile, model, prompt or schema (nothing is sent)."""
        prim = self.primary_profile
        return self.enricher.stale(prim[1]) if prim else []

    def enrich(self, *, uids: list[str] | None = None, limit: int | None = None, stale: bool = False):
        prim = self.primary_profile
        if prim is None:
            return None
        ids = None
        if uids:
            ids = [i for i in (self.ai_repo.article_id_for_uid(u) for u in uids) if i]
        elif stale:  # on request only: a profile edit never triggers paid reassessment by itself
            ids = self.stale_ai()[: limit if limit is not None else self.settings.ai.selection.max_items_per_cycle]
        for i in ids or []:
            self.ai_repo.reset_pending(i)
        rep = self.enricher.run(prim[1], article_ids=ids, limit=limit)
        self.rerank()
        return rep

    # --- configuration -------------------------------------------------------------------------------------------------
    def config_path(self, name: str) -> Path | None:
        d = self.cfg.paths.config_dir
        return d / name if d else None

    def resolve_inbox(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute() and self.cfg.paths.config_dir:
            p = self.cfg.paths.config_dir / p
        return p

    def load_gazetteer(self) -> None:
        p = self.config_path("gazetteer.yaml")
        data = read_yaml(p) if p and p.exists() else {}
        out = {}
        for e in (data or {}).get("entities", []) or []:
            names = [n for lang_names in (e.get("names") or {}).values() for n in (lang_names or [])]
            out[e["id"]] = names
        self.gazetteer = out

    def sync_registry(self) -> int:
        p = self.config_path("sources.yaml")
        specs = load_sources(p) if p else []
        today = self.clock.now().date()
        for s in specs:
            active, reason = s.activation(self.settings.use_context, today)
            endpoint = s.url or s.path or ""
            poll = max(s.poll_seconds or self.settings.fetch.default_poll_seconds, self.settings.fetch.min_poll_seconds)
            self.sources.upsert(s, active=active, reason=reason, endpoint=endpoint, poll_seconds=poll,
                                now=iso(self.clock.now()))
        self.sources.deactivate_missing({s.key for s in specs})
        return len(specs)

    def load_profiles(self) -> dict[str, str]:
        """(Re)load profiles/*.yaml; invalid files are reported and skipped, never half-applied."""
        d = self.config_path("profiles")
        profiles, errors = {}, {}
        if d and d.is_dir():
            keys = self.sources.keys()
            for f in sorted(d.glob("*.yaml")):
                try:
                    text = f.read_text(encoding="utf-8")
                    data = yaml.safe_load(text)
                    read_yaml(f)  # refuses inline secrets
                    p = validate_profile(data or {}, source_keys=keys, entity_ids=set(self.gazetteer))
                except (ProfileError, ConfigError, yaml.YAMLError, AttributeError) as exc:
                    errors[f.name] = str(exc)
                    obslog.event("profile_rejected", 30, file=f.name, stage="rank", detail=str(exc)[:300])
                    continue
                pid = self.articles.save_profile(p.key, text, "config", iso(self.clock.now()))
                profiles[p.key] = (pid, p)
        self.profiles = profiles
        self.profile_errors = errors
        return errors

    @property
    def primary_profile(self) -> tuple[int, Profile] | None:
        return self.profiles[sorted(self.profiles)[0]] if self.profiles else None

    # --- operations ------------------------------------------------------------------------------------------------------
    def collect(self, *, force: bool = False, only: set[str] | None = None):
        from newsmon.runtime.cycle import run_cycle
        with self.collect_lock:
            self.load_profiles()
            self.last_report = run_cycle(self, force=force, only=only)
            return self.last_report

    def rerank(self) -> int:
        """Re-evaluate every live article against the primary profile (bands, scores, explanations)."""
        prim = self.primary_profile
        if prim is None:
            return 0
        pid, profile = prim
        now = self.clock.now()
        from datetime import datetime
        results = []
        ai_latest = self.ai_repo.latest_for_articles()
        for r in self.articles.ranking_inputs():
            text = fold(" ".join(x for x in (r["headline"], r["description_text"], r["body_text"]) if x))
            facts = ItemFacts(text=text, lang=r["lang"], source_key=r["source_key"], is_wire=bool(r["is_wire"]),
                              urgency=r["urgency"], seen=datetime.fromisoformat(r["first_seen_utc"]),
                              independent_sources=r["independent_sources"])
            ev = evaluate(profile, facts, now, self.gazetteer)
            hits = [(h.rule_id, h.matched, h.score) for h in ev.hits]
            final, ai_band = merge_band(ev.band, ai_latest.get(r["article_id"]), bool(r["regex_prefilter_hit"]))
            if r["regex_prefilter_hit"]:
                hits.append(("injection_prefilter", "review, no automatic action", 0.0))
            elif ai_band and final != ev.band:
                hits.append(("ai_band", ai_band, 0.0))
            results.append((r["article_id"], ev.band, final, ev.score, hits))
        self.articles.save_ranking(pid, results, iso(now))
        return len(results)

    INCIDENT_FAILURES = 3  # FR-04 default N
    ALERT_WINDOW_HOURS = 24  # enabling alerts on an existing database does not alert on old items

    def alert_kinds(self) -> set[str]:
        prim = self.primary_profile
        return {k for k, v in prim[1].alerts.items() if _inapp(v)} if prim else {"feed_incident"}

    def raise_alerts(self) -> dict[str, int]:
        """In-app alerts after a cycle (M1 v1). The primary profile's `alerts:` keys switch kinds on: `flash` (band 속보),
        `report` (band 보고, raised as `watch`; opt-in) and `feed_incident` (FR-04 failing feeds). Nothing is sent
        anywhere: email and other channels need the outbox (T-36)."""
        from datetime import timedelta
        enabled = self.alert_kinds()
        now = self.clock.now()
        now_s, since = iso(now), iso(now - timedelta(hours=self.ALERT_WINDOW_HOURS))
        out = {"flash": 0, "watch": 0, "incidents_opened": 0, "incidents_closed": 0}
        if "flash" in enabled:
            out["flash"] = self.alerts.raise_for_band("flash", "flash", "속보 등급 (프로필 규칙)", since=since, now_s=now_s)
        if "report" in enabled:
            out["watch"] = self.alerts.raise_for_band("watch", "report", "보고 등급", since=since, now_s=now_s)
        if "feed_incident" in enabled:
            out["incidents_opened"], out["incidents_closed"] = self.alerts.update_incidents(
                failures=self.INCIDENT_FAILURES, now_s=now_s)
        out["saved_search"] = 0
        for s in self.searches.alerting():  # each saved search with its alert on (duty 4); one failing never stops the rest
            try:
                rows, _ = self.search(s["query"], lang=s["lang"], source=s["source_key"], band=s["band"],
                                      hours=s["hours"], since=max(since, s["created_utc"]),
                                      video_only=bool(s["video_only"]), newest_first=True, limit=500)
                out["saved_search"] += self.alerts.raise_for_articles(
                    "watch", [r["article_id"] for r in rows], f"저장 검색: {s['name']}", since=since,
                    after=s["created_utc"], now_s=now_s)
                self.searches.set_error(s["search_id"], None)
            except Exception as exc:
                self.searches.set_error(s["search_id"], f"{exc.__class__.__name__}: {exc}")
        return out

    MEDIA_PER_CYCLE = 5
    MEDIA_BUDGET_S = 300.0  # a batch stops starting new clips after this much wall time

    def kick_media(self) -> dict:
        """Called at the end of a cycle. Synchronous by default (one-shot CLI, tests); with `media_async` the check runs
        on its own thread so a slow clip never holds up feed collection, and at most one such thread runs at a time."""
        if not self.media_async:
            return self.check_media()
        if self._media_thread is not None and self._media_thread.is_alive():
            return {"tool": self.media_tool is not None, "started": False}

        def run():
            try:
                self.check_media()
            except Exception as exc:  # recorded; the next cycle starts a new thread
                obslog.event("media_check_failed", 40, stage="presentation", detail=f"{exc.__class__.__name__}: {exc}")
        self._media_thread = threading.Thread(target=run, name="newsmon-media", daemon=True)
        self._media_thread.start()
        return {"tool": self.media_tool is not None, "started": True}

    def check_media(self, limit: int | None = None) -> dict:
        """Check wire clips that have arrived and are not yet checked at their current file hash (duty 2, v1): technical
        facts, black/silence faults (freeze as a note), and a thumbnail strip where the licence stores content in full.
        The file is located through the inbox ledger and must resolve inside its feed's inbox root."""
        out = {"tool": self.media_tool is not None, "checked": 0, "ok": 0, "needs_check": 0, "unreadable": 0,
               "missing": 0}
        if self.media_tool is None:
            return out
        with self._media_lock:
            return self._check_media(out, self.MEDIA_PER_CYCLE if limit is None else max(0, limit))

    def _check_media(self, out: dict, limit: int) -> dict:
        from newsmon.adapters.ffmpeg_media import MediaToolError
        from newsmon.domain.enums import Storage
        from newsmon.licence.policy import flags_from_snapshot
        started = time.monotonic()
        for r in self.media.pending(limit):
            if time.monotonic() - started > self.MEDIA_BUDGET_S:
                break
            now_s = iso(self.clock.now())
            root = self.resolve_inbox(r["feed_path"]).resolve()
            path = (root / r["rel_path"]).resolve()
            out["checked"] += 1
            if not path.is_relative_to(root) or not path.is_file():
                why = "file outside the inbox root" if not path.is_relative_to(root) else "file no longer in the inbox"
                self.media.save(r["asset_id"], r["sha256"], now_s, status="missing", error=why)
                out["missing"] += 1
                continue
            try:
                probe = self.media_tool.probe(path)
                found = self.media_tool.detect(path, has_video=bool(probe.get("video")),
                                               has_audio=bool(probe.get("audio")), duration=probe.get("duration_s"))
            except Exception as exc:  # any failure on one clip is recorded on that clip, never raised into the cycle
                self.media.save(r["asset_id"], r["sha256"], now_s, status="unreadable",
                                error=f"{exc.__class__.__name__}: {exc}"[:300])
                out["unreadable"] += 1
                continue
            faults = {"black": found.get("black", []), "silence": found.get("silence", [])}
            status = "needs_check" if faults["black"] or faults["silence"] else "ok"
            thumb = None
            flags = flags_from_snapshot(r["licence_snapshot"])
            if (flags.storage is Storage.FULL and not (r["restrictions"] or "").strip() and probe.get("video")
                    and r["status"] != "killed"):
                rel = f"thumbs/{r['sha256'][:32]}.jpg"
                try:
                    if self.media_tool.thumbnail(path, self.cfg.paths.data_dir / rel, probe.get("duration_s")):
                        thumb = rel
                except (MediaToolError, OSError, subprocess.SubprocessError):
                    thumb = None  # a thumbnail is a convenience; its failure does not fail the check
            self.media.save(r["asset_id"], r["sha256"], now_s, status=status, probe=probe, faults=faults,
                            notes={"freeze": found.get("freeze", [])}, thumb=thumb)
            out[status] += 1
        out["thumbs_removed"] = self.cleanup_thumbs()
        return out

    def cleanup_thumbs(self) -> int:
        """Delete thumbnail files this app generated that no current check of a live, unrestricted item uses (replaced
        by a re-check, withdrawn, or restricted later). Only `data_dir/thumbs/*.jpg` is ever touched."""
        d = self.cfg.paths.data_dir / "thumbs"
        if not d.is_dir():
            return 0
        keep = {Path(p).name for p in self.media.wanted_thumbs()}
        removed = 0
        for f in d.glob("*.jpg"):
            if f.name not in keep:
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed

    def search(self, q: str, *, lang: str | None = None, source: str | None = None, band: str | None = None,
               hours: int | None = None, since: str | None = None, video_only: bool = False,
               newest_first: bool = False, limit: int = 100) -> tuple[list[dict], dict[str, list[str]]]:
        """The one search path (page, saved searches, saved-search alerts): gazetteer expansion, then FTS with filters.
        `hours` limits to items first seen in the last N hours; `since` to items first seen at or after a time."""
        from datetime import timedelta
        aliases = self.search_aliases(q)
        query = f'"{q.strip()}"' if aliases else q
        if hours:
            cutoff = iso(self.clock.now() - timedelta(hours=int(hours)))
            since = max(since, cutoff) if since else cutoff
        rows = self.articles.search(query, aliases=aliases, lang=lang or None, source_key=source or None,
                                    band=band or None, since=since, video_only=video_only, newest_first=newest_first,
                                    limit=limit)
        return rows, aliases

    def search_counts(self, q: str, *, lang=None, source=None, band=None, hours=None, video_only=False,
                      new_after: str | None = None) -> tuple[int, int]:
        from datetime import timedelta
        aliases = self.search_aliases(q)
        query = f'"{q.strip()}"' if aliases else q
        since = iso(self.clock.now() - timedelta(hours=int(hours))) if hours else None
        return self.articles.search_counts(query, aliases=aliases, lang=lang or None, source_key=source or None,
                                           band=band or None, since=since, video_only=video_only, new_after=new_after)

    def search_aliases(self, query: str) -> dict[str, list[str]]:
        """Gazetteer expansion: a query equal to any alias of an entity also searches its other aliases."""
        q = fold(query.strip().strip('"'))
        for names in self.gazetteer.values():
            if q in {fold(n) for n in names}:
                return {query.strip().strip('"'): [n for n in names if fold(n) != q]}
        return {}

    def close(self) -> None:
        close = getattr(self.fetcher, "close", None)
        if close:
            close()
        self.db.close()
