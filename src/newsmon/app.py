"""Composition root: builds the one database, the repositories, the fetcher and the loaded configuration.

The CLI, the web UI and the tests all construct an `App`; nothing else wires adapters together.
"""
from __future__ import annotations

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
from newsmon.repo.db import Database
from newsmon.repo.migrate import ensure_workspace, migrate
from newsmon.repo.sources import SourceRepo
from newsmon.rules.engine import ItemFacts, evaluate
from newsmon.rules.profile import Profile, ProfileError, validate_profile


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

    def raise_alerts(self) -> dict[str, int]:
        """In-app alerts after a cycle (M1 v1). The primary profile's `alerts:` keys switch kinds on: `flash` (band 속보),
        `report` (band 보고, raised as `watch`; opt-in) and `feed_incident` (FR-04 failing feeds). Nothing is sent
        anywhere: email and other channels need the outbox (T-36)."""
        from datetime import timedelta
        prim = self.primary_profile
        enabled = set(prim[1].alerts) if prim else {"feed_incident"}
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
        return out

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
