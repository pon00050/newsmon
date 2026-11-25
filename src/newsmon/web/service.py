"""Service layer for the UI and CLI (T-40 essential portion). Every article leaving it has gone through DisplayPolicy;
nothing here writes SQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from newsmon.ai.enrich import BAND_RANK, kst_day, route
from newsmon.licence.policy import DisplayPolicy

BANDS = ("flash", "report", "review", "drop")
DEFAULT_BANDS = ["flash", "report", "review"]


def kst(ts: str | None, tz: str = "Asia/Seoul") -> str:
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts).astimezone(ZoneInfo(tz)).strftime("%m-%d %H:%M")
    except ValueError:  # a malformed timestamp; an unknown zone is rejected when settings load
        return ts


class Service:
    def __init__(self, app) -> None:
        self.app = app

    def _render(self, rows: list[dict]) -> list[dict]:
        out = []
        tz = self.app.settings.timezone
        enricher = self.app.enricher
        ai_latest = self.app.ai_repo.latest_for_articles([r["article_id"] for r in rows]) if rows else {}
        min_rank = BAND_RANK[self.app.settings.ai.selection.min_band]
        for r in rows:
            r = dict(r)
            r["ai"] = ai_latest.get(r["article_id"])
            v = DisplayPolicy.render(r)
            v["ai_tag"] = None
            v["injection_flag"] = bool(r.get("regex_prefilter_hit")) or bool(v["ai"] and v["ai"]["injection_suspected"])
            if enricher.active:  # spec 12 section 13: tags only when AI is configured
                if not route(r["licence_snapshot"], restrictions=r.get("restrictions"), status=r.get("status")).allowed:
                    v["ai_tag"] = "AI 미적용 (라이선스)"
                elif r.get("enrichment_status") == "review":
                    v["ai_tag"] = "AI 검토 필요"
                elif r.get("enrichment_status") == "pending" and BAND_RANK.get(r.get("rule_band") or "drop", 0) >= min_rank:
                    v["ai_tag"] = "AI 처리 대기"
            v["dup_count"] = r.get("dup_count", 0)
            v["seen_kst"] = kst(r.get("first_seen_utc"), tz)
            v["published_kst"] = kst(r.get("published_utc"), tz)
            v["synthetic"] = bool(r.get("synthetic"))
            out.append(v)
        return out

    def queue(self, *, bands: list[str] | None = None, lang: str | None = None, source: str | None = None,
              hours: int | None = None, include_dups: bool = False, limit: int = 200) -> list[dict]:
        since = None
        if hours:
            since = (self.app.clock.now() - timedelta(hours=hours)).astimezone(timezone.utc).isoformat(timespec="seconds")
        rows = self.app.articles.queue(bands=bands if bands is not None else DEFAULT_BANDS, lang=lang or None,
                                       source_key=source or None, since=since, include_dups=include_dups, limit=limit)
        return self._render(rows)

    def search(self, q: str, *, lang: str | None = None, source: str | None = None, band: str | None = None,
               limit: int = 100) -> dict:
        aliases = self.app.search_aliases(q)
        query = f'"{q.strip()}"' if aliases else q
        rows = self.app.articles.search(query, aliases=aliases, lang=lang or None, source_key=source or None,
                                        band=band or None, limit=limit)
        alias_list = [a for v in aliases.values() for a in v]
        return {"rows": self._render(rows), "aliases": alias_list}

    def article(self, uid: str) -> dict | None:
        r = self.app.articles.get(uid)
        if r is None:
            return None
        v = self._render([r])[0]
        v["rule_hits"] = self.app.articles.rule_hits(r["article_id"])
        v["related"] = self.app.articles.related(r["article_id"])
        v["media"] = self.app.articles.media(r["article_id"])
        v["revisions"] = self.app.articles.revisions(r["article_id"])
        v["version"] = r.get("version")
        return v

    def ai_overview(self) -> dict:
        e = self.app.enricher
        return {"label": e.header_label(), "configured": e.configured, "paused": e.paused, "active": e.active,
                "reason": e.disabled_reason, "last_error": e.last_error,
                "model": self.app.settings.ai.enrich_model, "cap": self.app.settings.ai.daily_cap_usd,
                "spent_today": self.app.ai_repo.spent(kst_day(self.app.clock.now())),
                "totals": self.app.ai_repo.usage_totals(), "status_counts": self.app.ai_repo.status_counts(),
                "stale": len(self.app.stale_ai()),
                "review": [{**DisplayPolicy.render(r), "last_attempt_utc": r["last_attempt_utc"]}
                           for r in self.app.ai_repo.review_queue(30)]}

    def sources(self) -> list[dict]:
        tz = self.app.settings.timezone
        rows = self.app.sources.status_rows()
        for r in rows:
            r["last_success_kst"] = kst(r.get("last_success_utc"), tz)
            if r.get("last_run"):
                r["last_run"]["started_kst"] = kst(r["last_run"].get("started_utc"), tz)
        return rows
