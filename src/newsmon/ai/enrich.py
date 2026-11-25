"""Optional AI enrichment (Release A.1; T-47/T-48/T-49 essential portion). Supplements, never replaces, the
deterministic record: rule bands, search and the queue work the same whether this runs, fails or is switched off.

Per article:
1. Selection: pending, primary (not a duplicate), rule band >= `ai.selection.min_band` (or chosen manually), optionally
   limited to listed sources; at most `max_items_per_cycle` per cycle.
2. Licence routing (FR-15; conservative, configuration only): AI runs only if `ai_processing` is not `no`,
   `external_ai_allowed` is true (no customer-hosted endpoint exists yet) and `permitted_ops` contains `classify`.
   Korean headline / summary are requested only if `translate` / `summarise` are permitted. Otherwise the item is marked
   `not_allowed` and no byte of it is sent. `synthetic` plays no part (FR-27(d)).
3. Fields sent (FR-12(b)): headline + stored feed summary; the stored body only when `ai_processing=yes`. Logged per call.
4. Cache: keyed by model, prompt version, schema version and a hash of exactly what is sent; unchanged input = no call.
5. Spend: today's (KST) spend is checked before every call; at the cap the layer stops until midnight KST (FR-15(c)).
6. Validation: one retry on an invalid result, then `review` (FR-13); a deterministic failure is never retried in bulk.
7. Outage: provider unavailability stops the batch, keeps items `pending`, and backs off before the next attempt.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from newsmon.ai import prompts, schema
from newsmon.ai.prefilter import check as prefilter_check
from newsmon.domain.ports import AIProvider, AIRequestError, AIResult, AIUnavailable
from newsmon.licence.policy import flags_from_snapshot
from newsmon.obs.logging import event

KST = ZoneInfo("Asia/Seoul")
BAND_RANK = {"drop": 0, "review": 1, "report": 2, "flash": 3}
AI_OFF, AI_DOWN, AI_ON = "AI: 꺼짐", "AI: 중단", "AI: 켜짐"


@dataclass
class EnrichReport:
    selected: int = 0
    called: int = 0
    cached: int = 0
    done: int = 0
    review: int = 0
    not_allowed: int = 0
    failed: int = 0
    cost_usd: float = 0.0
    stopped: str | None = None  # why the batch stopped early (capped / provider unavailable / disabled)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Route:
    allowed: bool
    reason: str = ""
    translate: bool = False
    summarise: bool = False
    send_body: bool = False


def route(snapshot: str, *, restrictions: str | None = None, status: str | None = None) -> Route:
    """Whether an article may be sent, from its licence snapshot and its own state. A withdrawn item, or one carrying
    any restriction (embargo, withheld, an unrecognised restriction code), is never sent."""
    if status == "killed":
        return Route(False, "item was withdrawn")
    if restrictions and restrictions.strip():
        return Route(False, "item carries a restriction")
    f = flags_from_snapshot(snapshot)
    ops = {str(o) for o in f.permitted_ops}
    if str(f.ai_processing) == "no":
        return Route(False, "ai_processing=no")
    if not f.external_ai_allowed:
        return Route(False, "external_ai_allowed=false and no customer-hosted endpoint")
    if "classify" not in ops:
        return Route(False, "classify not in permitted_ops")
    return Route(True, "", translate="translate" in ops, summarise="summarise" in ops,
                 send_body=str(f.ai_processing) == "yes")


def kst_day(now: datetime) -> str:
    return now.astimezone(KST).date().isoformat()


class Enricher:
    def __init__(self, *, provider: AIProvider | None, repo, settings, clock, enabled_reason: str = "") -> None:
        self.provider = provider
        self.repo = repo
        self.settings = settings  # AISettings
        self.clock = clock
        self.disabled_reason = enabled_reason
        self.down_until: datetime | None = None
        self.last_error: str | None = None
        self.outages = 0  # consecutive provider outages: drives the back-off
        self._lock = threading.Lock()  # one batch at a time (background collector vs manual button)

    # --- state ----------------------------------------------------------------------------------------------------------
    @property
    def configured(self) -> bool:
        return self.provider is not None and self.settings.capabilities.enrich

    @property
    def paused(self) -> bool:
        return self.repo.get_state("ai_paused", "0") == "1"

    def set_paused(self, paused: bool) -> None:
        self.repo.set_state("ai_paused", "1" if paused else "0", self.clock.now().isoformat(timespec="seconds"))

    @property
    def active(self) -> bool:
        return self.configured and not self.paused

    def capped_today(self) -> bool:
        return self.repo.capped(kst_day(self.clock.now()))

    def header_label(self) -> str:
        if not self.active:
            return AI_OFF
        if self.capped_today() or (self.down_until and self.clock.now() < self.down_until):
            return AI_DOWN
        return AI_ON

    # --- the batch ---------------------------------------------------------------------------------------------------------
    def run(self, profile, *, article_ids: list[int] | None = None, limit: int | None = None) -> EnrichReport:
        with self._lock:
            return self._run(profile, article_ids=article_ids, limit=limit)

    def _over_cap(self) -> bool:
        day = kst_day(self.clock.now())
        if self.repo.capped(day) or self.repo.spent(day) >= self.settings.daily_cap_usd:
            self.repo.mark_capped(day, self.settings.daily_cap_usd)
            return True
        return False

    def _run(self, profile, *, article_ids: list[int] | None = None, limit: int | None = None) -> EnrichReport:
        rep = EnrichReport()
        if not self.active:
            rep.stopped = "disabled" if self.configured else (self.disabled_reason or "not configured")
            return rep
        now = self.clock.now()
        if self.down_until and now < self.down_until and article_ids is None:
            rep.stopped = f"provider unavailable; retry after {self.down_until.isoformat(timespec='seconds')}"
            return rep
        sel = self.settings.selection
        if article_ids is None:
            n = sel.max_items_per_cycle if limit is None else limit
            article_ids = [r["article_id"] for r in self.repo.candidates(min_rank=BAND_RANK[sel.min_band], limit=n,
                                                                        sources=tuple(sel.sources))]
        rep.selected = len(article_ids)
        for aid in article_ids:
            day = kst_day(self.clock.now())
            if self._over_cap():
                rep.stopped = f"daily cap ${self.settings.daily_cap_usd:.2f} reached ({day} KST)"
                event("ai_capped", logging.WARNING, stage="ai", day=day, cap=self.settings.daily_cap_usd)
                break
            try:
                self._one(profile, aid, rep)
            except AIUnavailable as exc:
                self.outages += 1
                backoff = min(600, 30 * 2 ** min(5, self.outages - 1))
                self.down_until = self.clock.now() + timedelta(seconds=backoff)
                self.last_error = str(exc)
                rep.stopped = f"provider unavailable ({exc}); items stay pending"
                event("ai_unavailable", logging.WARNING, stage="ai", error_class="provider_unavailable", detail=str(exc),
                      backoff_s=backoff)
                break
        if rep.stopped is None:
            self.down_until = None
            self.outages = 0
        event("ai_batch", stage="ai", selected=rep.selected, called=rep.called, cached=rep.cached, done=rep.done,
              review=rep.review, not_allowed=rep.not_allowed, failed=rep.failed, cost_usd=round(rep.cost_usd, 6),
              stopped=rep.stopped)
        return rep

    def _one(self, profile, article_id: int, rep: EnrichReport) -> None:
        a = self.repo.article_input(article_id)
        if a is None:
            return
        r = route(a["licence_snapshot"], restrictions=a["restrictions"], status=a["status"])
        if not r.allowed:
            self.repo.set_status(article_id, "not_allowed")
            rep.not_allowed += 1
            return
        fields, user, js, input_sha = self._request(profile, a, r)
        fields_sent = sorted(k for k in fields if k in ("headline", "summary", "body"))
        model = self.settings.enrich_model
        hit =self.repo.cached(a["current_revision_id"], model, prompts.PROMPT_VERSION, schema.SCHEMA_VERSION, input_sha)
        if hit is not None:
            rep.cached += 1
            self.repo.set_status(article_id, "done" if hit["validation_status"] in ("valid", "retried_valid") else "review")
            return
        source_text = " ".join(fields.get(k, "") for k in ("headline", "summary", "body"))
        prefilter = bool(a["regex_prefilter_hit"])
        last_error = ""
        for attempt in (1, 2):
            if attempt == 2 and self._over_cap():  # the retry is a paid call too
                last_error = "daily cap reached before retry"
                break
            try:
                res = self.provider.complete_json(task="enrich", system=prompts.SYSTEM, user=user, schema=js, model=model,
                                                  fields_sent=fields_sent)
            except AIRequestError as exc:
                rep.called += 1
                rep.cost_usd += exc.cost_usd
                self.repo.add_spend(kst_day(self.clock.now()), exc.cost_usd, self.settings.daily_cap_usd)
                last_error = str(exc)
                failed = AIResult(output={"error": str(exc)[:200]}, model=model, cost_usd=exc.cost_usd,
                                  provider=getattr(self.provider, "name", ""),
                                  endpoint_kind=getattr(self.provider, "endpoint_kind", ""))
                self._save(a, failed, failed.output, input_sha, fields_sent, "invalid", False, prefilter,
                           suffix=f"#e{attempt}")
                continue
            rep.called += 1
            rep.cost_usd += res.cost_usd
            self.repo.add_spend(kst_day(self.clock.now()), res.cost_usd, self.settings.daily_cap_usd)
            try:
                assessment = schema.validate(res.output, source_text=source_text, translate=r.translate,
                                             summarise=r.summarise)
            except (schema.ValidationError, schema.SemanticError, ValueError) as exc:
                last_error = _safe_error(exc)  # field names and error types only: never model or source text
                status = "invalid" if attempt == 1 else "review"
                self._save(a, res, res.output, input_sha, fields_sent, status, False, prefilter, suffix=f"#a{attempt}")
                event("ai_invalid", logging.WARNING, stage="ai", article=a["uid"], attempt=attempt, detail=last_error)
                continue
            status = "valid" if attempt == 1 else "retried_valid"
            self._save(a, res, assessment.model_dump(), input_sha, fields_sent, status, assessment.injection_suspected,
                       prefilter)
            self.repo.set_status(article_id, "done")
            rep.done += 1
            return
        self.repo.set_status(article_id, "review")
        rep.review += 1
        rep.errors.append(f"{a['uid']}: {last_error}")

    def _request(self, profile, a: dict, r: Route) -> tuple[dict, str, dict, str]:
        """The exact request for one article and its hash. The hash covers the system prompt, the desk block built from
        the profile, the article fields and the schema, so a change to any of them makes a different request."""
        fields = {"source": a["source_name"], "published": a["published_utc"] or "", "language": a["lang"] or "",
                  "headline": a["headline"] or ""}
        if a["description_text"]:
            fields["summary"] = a["description_text"]
        if r.send_body and a["body_text"]:
            fields["body"] = a["body_text"][: self.settings.selection.max_input_chars]
        user = prompts.user_message(profile, fields, translate=r.translate, summarise=r.summarise)
        js = schema.json_schema(translate=r.translate, summarise=r.summarise)
        sha = hashlib.sha256(json.dumps([prompts.SYSTEM, user, js], ensure_ascii=False).encode()).hexdigest()
        return fields, user, js, sha

    def stale(self, profile) -> list[int]:
        """Articles whose stored assessment no longer matches what would be sent today: the profile, the model, the
        prompt or the schema changed after they were assessed. Computed locally; nothing is sent."""
        out = []
        for aid, seen in self.repo.assessed().items():
            a = self.repo.article_input(aid)
            r = route(a["licence_snapshot"], restrictions=a["restrictions"], status=a["status"])
            if not r.allowed:
                continue  # it can no longer be sent, so it cannot be refreshed either
            sha = self._request(profile, a, r)[3]
            if seen != (self.settings.enrich_model, prompts.PROMPT_VERSION, schema.SCHEMA_VERSION, sha):
                out.append(aid)
        return out

    def _save(self, a, res, output, input_sha, fields_sent, status, injection, prefilter, suffix: str = "") -> None:
        # failed attempts get a unique key (never overwriting an earlier attempt's record) so that every billed call
        # keeps its fields_sent / tokens / cost row, and the next valid attempt is stored under the real cache key
        if suffix:
            suffix += "#" + uuid.uuid4().hex[:8]
        self.repo.save_interpretation(
            revision_id=a["current_revision_id"], output=output, provider=res.provider, endpoint_kind=res.endpoint_kind,
            model=res.model, prompt_version=prompts.PROMPT_VERSION, schema_version=schema.SCHEMA_VERSION,
            input_sha=input_sha + suffix, fields_sent=fields_sent, validation_status=status, injection=injection,
            prefilter=prefilter, input_tokens=res.input_tokens, output_tokens=res.output_tokens, cost=res.cost_usd,
            latency_ms=res.latency_ms, now=self.clock.now().astimezone(timezone.utc).isoformat(timespec="seconds"))


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, schema.ValidationError):
        fields = sorted({".".join(str(x) for x in e["loc"]) or "?" for e in exc.errors()})
        return f"ValidationError in {', '.join(fields)[:150]}"
    if isinstance(exc, schema.SemanticError):
        return f"SemanticError: {str(exc).split(':')[0][:120]}"
    return exc.__class__.__name__


def merge_band(rule_band: str | None, ai: dict | None, prefilter_hit: bool) -> tuple[str, str | None]:
    """Final band = max(rule band, AI band capped at report); flash only from rules (FR-11). An injection flag (regex or
    model) discards the AI band and sets the item to `review` (FR-14). Returns (band, ai_band_used)."""
    rule = rule_band or "drop"
    if prefilter_hit or (ai and ai.get("injection_suspected")):
        return "review", None
    if not ai:
        return rule, None
    ai_band = ai["output"].get("relevance_band", "drop")
    if ai_band not in ("drop", "review", "report"):
        ai_band = "drop"
    return (ai_band if BAND_RANK[ai_band] > BAND_RANK[rule] else rule), ai_band


def screen(texts: tuple[str | None, ...]) -> list[str]:
    return prefilter_check(*texts)
