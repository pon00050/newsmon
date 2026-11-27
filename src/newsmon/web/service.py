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
CLIP_STATE_KO = {"killed": "철회 · 인제스트 금지", "awaiting": "파일 대기", "queued": "확인 대기", "ok": "인제스트 준비됨", "needs_check": "확인 필요",
                 "unreadable": "읽기 실패", "missing": "파일 없음", "filed": "인제스트 완료"}
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
               hours: int | None = None, video_only: bool = False, limit: int = 100) -> dict:
        """UI-4: results under DisplayPolicy with their clip state and verdict, the aliases used, and the feeds in an
        open incident inside the source filter (a result is never read as "no news" while a feed is failing)."""
        rows, aliases = self.app.search(q, lang=lang, source=source, band=band, hours=hours, video_only=video_only,
                                        limit=limit)
        out = self._render(rows)
        clips: dict[int, list[dict]] = {}
        for c in self.app.media.for_articles([r["article_id"] for r in rows]):
            clips.setdefault(c["article_id"], []).append(self._clip_view(c))
        for v, r in zip(out, rows):
            v["clips"] = clips.get(r["article_id"], [])
        return {"rows": out, "aliases": [a for v in aliases.values() for a in v],
                "failing": self.app.alerts.open_incidents(source or None)}

    # --- saved searches (duty 4) ---------------------------------------------------------------------------------------
    @staticmethod
    def search_url(s: dict) -> str:
        from urllib.parse import urlencode
        params = [("q", s["query"])] + [(k, v) for k, v in (("lang", s["lang"]), ("source", s["source_key"]),
                                                            ("band", s["band"]), ("hours", s["hours"]),
                                                            ("video", 1 if s["video_only"] else None)) if v]
        return "/search?" + urlencode(params)

    def saved_searches(self) -> list[dict]:
        tz = self.app.settings.timezone
        out = []
        for s in self.app.searches.all():
            total = new = 0
            error = s["last_error"]
            try:
                total, new = self.app.search_counts(s["query"], lang=s["lang"], source=s["source_key"], band=s["band"],
                                                    hours=s["hours"], video_only=bool(s["video_only"]),
                                                    new_after=s["last_seen_utc"])
            except Exception as exc:  # a saved query that no longer parses is shown, never a 500
                error = f"{exc.__class__.__name__}: {exc}"
            out.append({**s, "total": total, "new": new, "error": error, "url": self.search_url(s),
                        "seen_kst": kst(s["last_seen_utc"], tz), "created_kst": kst(s["created_utc"], tz)})
        return out

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
        v["clips"] = [self._clip_view(c) for c in self.app.media.for_articles([r["article_id"]])]
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

    # --- wire footage: check, classification, ingest tracking (duty 2, v1) ---------------------------------------------
    @staticmethod
    def _tc(sec: float) -> str:
        sec = max(0.0, float(sec))
        return f"{int(sec // 60):02d}:{sec % 60:04.1f}"

    def _clip_view(self, r: dict) -> dict:
        from newsmon.domain.enums import Storage
        tz = self.app.settings.timezone
        shown = DisplayPolicy.render({**r, "description_text": None, "body_text": None, "ai": None})
        flags = flags_from_snapshot(r["licence_snapshot"])
        topics = []
        for h in self.app.articles.rule_hits(r["article_id"]):
            if h["rule_id"].startswith("topic:") and h["rule_id"][6:] not in topics:
                topics.append(h["rule_id"][6:])
        checked = r["checked_sha"] is not None and r["checked_sha"] == r["sha256"]
        killed = r["status"] == "killed"
        restricted_now = bool((r["restrictions"] or "").strip())
        if killed:
            state = "killed"  # withdrawn by the agency: never offered for filing, whatever its check says
        elif r["sha256"] is None:
            state = "awaiting"
        elif not checked:
            state = "queued"
        elif r["ingest_state"] == "filed":
            state = "filed"
        else:
            state = r["check_status"]
        p = (r["probe"] or {}) if checked else {}
        v, a = p.get("video") or {}, p.get("audio") or {}
        parts = [f"{v['width']}×{v['height']}" if v.get("width") else "",
                 " ".join(str(y) for y in (v.get("codec"), f"{v['fps']:g}fps" if v.get("fps") else "") if y),
                 " ".join(str(y) for y in (a.get("codec"), f"{a['channels']}ch" if a.get("channels") else "",
                                            f"{a['sample_rate'] / 1000:g}kHz" if a.get("sample_rate") else "") if y),
                 f"{p['duration_s']:.1f}s" if p.get("duration_s") else ""]
        tech = " · ".join(x for x in parts if x)
        faults = []
        if checked and r["faults"]:
            for kind, label in (("black", "블랙"), ("silence", "무음")):
                faults += [f"{label} {self._tc(s)}–{self._tc(e)}" for s, e in r["faults"].get(kind, [])]
        freeze = (r["notes"] or {}).get("freeze", []) if checked else []
        notes = [f"정지 화면 {self._tc(s)}–{self._tc(e)}" for s, e in freeze]
        thumb_ok = bool(checked and r["thumb_path"] and flags.storage is Storage.FULL and not restricted_now
                        and not killed)
        return {"asset_id": r["asset_id"], "uid": r["uid"], "headline": shown["headline"] or "(표시 제한)",
                "restricted": shown["restricted"] or restricted_now, "source_name": r["source_name"], "slugline": r["slugline"],
                "located": r["located"], "urgency": r["urgency"], "file": r["href"], "sha256": r["sha256"],
                "topics": topics or ["미분류"], "state": state, "state_ko": CLIP_STATE_KO.get(state, state),
                "tech": tech, "faults": faults, "notes": notes, "error": r["error"] if checked else None,
                "thumb_url": f"/media/thumb/{r['asset_id']}" if thumb_ok else None,
                "killed": killed, "synthetic": bool(r["synthetic"]),
                "filed_by": r["ingest_by"], "filed_kst": kst(r["ingest_utc"], tz) if r["ingest_utc"] else "",
                "checked_kst": kst(r["checked_utc"], tz) if checked else "",
                "seen_kst": kst(r["first_seen_utc"], tz), "can_file": checked and not killed}

    CLIP_PAGE = 200

    def clips(self, limit: int | None = None) -> list[dict]:
        return [self._clip_view(r) for r in self.app.media.list(limit=limit or self.CLIP_PAGE)]

    def clips_page(self) -> tuple[list[dict], bool]:
        rows = self.clips(limit=self.CLIP_PAGE + 1)
        return rows[: self.CLIP_PAGE], len(rows) > self.CLIP_PAGE

    def clips_csv(self) -> str:
        """The ingest sheet: one row per clip, for filing in the broadcaster's own system. Cells that a spreadsheet
        would read as a formula are prefixed with an apostrophe."""
        import csv
        import io

        def cell(x) -> str:
            s = "" if x is None else str(x)
            return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["상태", "철회", "사용 제한", "제목", "슬러그", "위치", "긴급도", "분류", "기술 정보", "결함", "참고", "출처",
                    "파일", "sha256", "수집(KST)", "인제스트 완료"])
        for c in self.clips(limit=100_000):  # the filing sheet is complete, unlike the page
            w.writerow([cell(x) for x in (c["state_ko"], "철회" if c["killed"] else "",
                                          "제한" if c["restricted"] else "", c["headline"], c["slugline"], c["located"], c["urgency"],
                                          " / ".join(c["topics"]), c["tech"], " / ".join(c["faults"]),
                                          " / ".join(c["notes"]), c["source_name"], c["file"], c["sha256"],
                                          c["seen_kst"], f"{c['filed_by'] or ''} {c['filed_kst']}".strip())])
        return "\ufeff" + buf.getvalue()  # BOM: Excel opens Korean UTF-8 correctly

    # --- in-app alerts (M1 v1) ------------------------------------------------------------------------------------------
    def _alert_view(self, r: dict) -> dict:
        """An alert as shown in the list, the poll JSON and a browser notification: the article headline only under
        DisplayPolicy (no summary), or the incident reason."""
        saved = (r["reason"] or "").startswith("저장 검색")
        v = {"id": r["alert_id"], "kind": r["kind"],
             "kind_ko": "저장 검색" if saved else ALERT_KIND_KO.get(r["kind"], r["kind"]), "saved_search": saved,
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
            v.update(title=r["reason"], restricted=False, why=[])
        return v

    def alerts(self, include_done: bool = False) -> list[dict]:
        statuses = ("new", "acknowledged", "dismissed") if include_done else ("new",)
        return [self._alert_view(r) for r in self.app.alerts.list(statuses=statuses)]

    def alert_poll(self, after: int) -> dict:
        return {"new_count": self.app.alerts.new_count(), "last_id": self.app.alerts.last_id(),
                "items": [{k: v[k] for k in ("id", "kind", "kind_ko", "title", "source_name", "url", "at_kst", "reason")}
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
