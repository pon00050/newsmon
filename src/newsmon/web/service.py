"""Service layer for the UI and CLI (T-40 essential portion). Every article leaving it has gone through DisplayPolicy;
nothing here writes SQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from newsmon.ai.enrich import BAND_RANK, kst_day, route
from newsmon.domain.enums import Redistribution
from newsmon.licence.policy import DisplayPolicy, flags_from_snapshot
from newsmon.pipeline.normalise import iso

BANDS = ("flash", "report", "review", "drop")
DEFAULT_BANDS = ["flash", "report", "review"]
VERDICT_KO = {"report_to_desk": "보고", "verify": "확인", "ignore": "무시"}
ALERT_KIND_KO = {"flash": "속보", "watch": "보고 등급", "feed_incident": "피드"}


def kst(ts: str | None, tz: str = "Asia/Seoul") -> str:
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts).astimezone(ZoneInfo(tz)).strftime("%m-%d %H:%M")
    except ValueError:  # a malformed timestamp; an unknown zone is rejected when settings load
        return ts


def kst_full(ts: str | None, tz: str = "Asia/Seoul") -> str:
    return datetime.fromisoformat(ts).astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M") if ts else ""


class Service:
    def __init__(self, app) -> None:
        self.app = app

    def _render(self, rows: list[dict]) -> list[dict]:
        out = []
        tz = self.app.settings.timezone
        enricher = self.app.enricher
        ai_latest = self.app.ai_repo.latest_for_articles([r["article_id"] for r in rows]) if rows else {}
        verdicts = self.app.assessments.latest_for_articles([r["article_id"] for r in rows])
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
            vd = verdicts.get(r["article_id"])
            v["verdict"] = {"verdict": vd["verdict"], "editor": vd["editor"],
                            "at_kst": kst(vd["created_utc"], tz)} if vd else None
            v["killed"] = r.get("status") == "killed"
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
        v["history"] = [{**h, "at_kst": kst(h["created_utc"], self.app.settings.timezone)}
                        for h in self.app.assessments.history(r["article_id"])]
        return v

    # --- editorial verdicts and the shift report (FR-18; "PC등록", INTERFACE_SPEC §2) ------------------------------------
    def add_verdict(self, uid: str, verdict: str, note: str | None) -> str:
        """Record a verdict. Returns "ok", "unknown" (no such article), "killed" (withdrawn items take no verdict) or
        "invalid" (verdict not in the vocabulary)."""
        from newsmon.repo.assessments import VERDICTS
        if verdict not in VERDICTS:
            return "invalid"
        r = self.app.articles.get(uid)
        if r is None:
            return "unknown"
        if r.get("status") == "killed":
            return "killed"
        self.app.assessments.add(r["article_id"], verdict, note, self.app.settings.desk_editor, iso(self.app.clock.now()))
        return "ok"

    def shift_report(self, hours: int = 8) -> dict:
        """Items whose current verdict (보고 or 확인) was made in the last `hours`. The report leaves the app (print,
        download), and recipient gating is not built, so each row carries a fixed set of fields only: headline under
        DisplayPolicy, source, link, times, rule reasons, the editor's note and licence marks. Never a feed summary,
        a body or AI text."""
        tz = self.app.settings.timezone
        now = self.app.clock.now()
        hours = max(1, min(int(hours), 48))
        since, until = iso(now - timedelta(hours=hours)), iso(now + timedelta(seconds=1))
        sections: dict[str, list[dict]] = {"report_to_desk": [], "verify": []}
        for r in self.app.assessments.report_rows(since, until):
            shown = DisplayPolicy.render({**r, "ai": None})
            flags = flags_from_snapshot(r["licence_snapshot"])
            killed = r["status"] == "killed"
            sections[r["verdict"]].append({
                "uid": r["uid"], "headline": shown["headline"], "link": shown["link"], "restricted": shown["restricted"],
                "source_name": r["source_name"], "lang": r["lang"], "band": r["final_band"], "urgency": r["urgency"],
                "seen_kst": kst(r["first_seen_utc"], tz), "published_kst": kst(r["published_utc"], tz),
                "verdict_kst": kst(r["verdict_utc"], tz), "editor": r["editor"], "note": r["note"],
                # recency is an age frozen at ranking time, misleading in a report read later
                "reasons": [h for h in self.app.articles.rule_hits(r["article_id"])
                            if h["rule_id"] not in ("injection_prefilter", "recency")][:3],
                "killed": killed,
                "revised_after": (not killed and (r["revision_utc"] or "") > r["verdict_utc"]) and r["version"],
                "merged": r["dup_of"] is not None, "dup_count": r["dup_count"],
                "synthetic": bool(r["synthetic"]),
                "no_redistribution": flags.redistribution is Redistribution.NONE,
            })
        return {"hours": hours, "since_kst": kst_full(since, tz), "until_kst": kst_full(iso(now), tz),
                "editor": self.app.settings.desk_editor, "sections": sections,
                "count": sum(len(v) for v in sections.values())}

    # --- in-app alerts (M1 v1) ------------------------------------------------------------------------------------------
    def _alert_view(self, r: dict) -> dict:
        """An alert as shown in the list, the poll JSON and a browser notification: the article headline only under
        DisplayPolicy (no summary), or the incident reason."""
        v = {"id": r["alert_id"], "kind": r["kind"], "kind_ko": ALERT_KIND_KO.get(r["kind"], r["kind"]),
             "severity": r["severity"], "status": r["status"], "reason": r["reason"],
             "at_kst": kst(r["created_utc"], self.app.settings.timezone), "uid": r["uid"], "source_name": r["source_name"],
             "killed": r["article_status"] == "killed", "synthetic": bool(r["synthetic"]),
             "closed": bool(r["closed_utc"]), "url": "/sources"}
        if r["article_id"] is not None and r["licence_snapshot"]:
            shown = DisplayPolicy.render({**r, "description_text": None, "body_text": None, "ai": None})
            v.update(title=shown["headline"] or "(표시 제한)", restricted=shown["restricted"], url=f"/article/{r['uid']}",
                     why=[h for h in self.app.articles.rule_hits(r["article_id"])
                          if h["rule_id"] not in ("injection_prefilter", "recency")][:3])
        else:
            v.update(title=r["reason"], restricted=False)
        return v

    def alerts(self, include_done: bool = False) -> list[dict]:
        statuses = ("new", "acknowledged", "dismissed") if include_done else ("new",)
        return [self._alert_view(r) for r in self.app.alerts.list(statuses=statuses)]

    def alert_poll(self, after: int) -> dict:
        return {"new_count": self.app.alerts.new_count(), "last_id": self.app.alerts.last_id(),
                "items": [{k: v[k] for k in ("id", "kind", "kind_ko", "title", "source_name", "url", "at_kst")}
                          for v in map(self._alert_view, self.app.alerts.after(max(0, int(after))))]}

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
