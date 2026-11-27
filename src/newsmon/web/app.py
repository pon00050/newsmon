"""Local web UI (Release A subset of UI-1 queue, UI-3 item detail, UI-4 search, UI-8 sources; Korean, KST display).

Loopback only, no login (auth_mode=local). POST routes require a same-origin request, so a page on another site cannot
trigger them from the user's browser. Templates autoescape everything; links are rendered only for http(s) URLs.
"""
from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import timezone
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from newsmon.obs.logging import event
from newsmon.pipeline.normalise import iso
from newsmon.web.service import BANDS, DEFAULT_BANDS, VERDICT_KO, Service

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
BAND_KO = {"flash": "속보", "report": "보고", "review": "검토", "drop": "제외"}
LANG_KO = {"ko": "한", "en": "영", "zh": "중", "ja": "일"}


class Collector:
    """Runs collection in one background thread so the UI stays responsive; never two at once."""

    def __init__(self, app) -> None:
        self.app = app
        self.running = False
        self.last_error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def trigger(self, force: bool = True) -> bool:
        if self.running:
            return False
        self.running = True

        def run():
            try:
                self.app.collect(force=force)
                self.last_error = None
            except Exception as exc:  # recorded, shown on the page; the UI keeps working
                self.last_error = f"{exc.__class__.__name__}: {exc}"
                event("collect_failed", 40, stage="collect", detail=self.last_error)
            finally:
                self.running = False

        threading.Thread(target=run, name="newsmon-collect", daemon=True).start()
        return True

    def start_loop(self, tick: float) -> None:
        def loop():
            while not self._stop.wait(tick):
                if not self.running:
                    self.trigger(force=False)
        self._thread = threading.Thread(target=loop, name="newsmon-auto", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


LOCAL_HOSTS = ["127.0.0.1", "localhost", "::1", "[::1]"]


def _same_origin(request: Request) -> bool:
    """POSTs must come from a page served by this app on a loopback name (CSRF; the Host header itself is checked by
    TrustedHostMiddleware, so a DNS-rebinding page cannot pose as this origin)."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return False
    o = urlsplit(origin)
    return o.hostname in LOCAL_HOSTS and o.netloc == request.headers.get("host", "")


def _local_path(next_: str | None, default: str) -> str:
    """A redirect target from a form: a path on this app only (one leading slash, no scheme, no backslash)."""
    if next_ and next_.startswith("/") and not next_.startswith("//") and "\\" not in next_ and "://" not in next_:
        return next_
    return default


FORM_MAX_BYTES = 16_384
SEARCH_HOURS = (6, 24, 72, 168)


def create_app(app, *, auto_collect: bool = False) -> FastAPI:
    svc = Service(app)
    collector = Collector(app)
    @asynccontextmanager
    async def lifespan(_web):
        if auto_collect:
            collector.start_loop(max(1.0, float(app.settings.inbox.scan_seconds)))
        yield
        collector.stop()

    web = FastAPI(title="newsmon", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    web.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS)  # refuses rebinding Host names
    web.state.collector = collector

    def ctx(request: Request, **kw) -> dict:
        qs = urlencode([(k, v) for k, v in request.query_params.multi_items() if k != "msg"])
        here = request.url.path + ("?" + qs if qs else "")  # where a form on this page returns to
        return {"request": request, "ai_label": app.ai_status.header_label(), "band_ko": BAND_KO, "lang_ko": LANG_KO,
                "collecting": collector.running, "collect_error": collector.last_error, "report": app.last_report,
                "verdict_ko": VERDICT_KO, "editor": app.settings.desk_editor, "here": here,
                "alert_count": app.alerts.new_count(), "alert_last_id": app.alerts.last_id(),
                "media_attention": app.media.attention_count(),
                "profile": app.primary_profile[1] if app.primary_profile else None,
                "profile_errors": app.profile_errors, **kw}

    @web.get("/", response_class=HTMLResponse)
    def queue(request: Request, band: list[str] | None = Query(None), lang: str = "", source: str = "", hours: int = 0,
              dups: int = 0, msg: str = ""):
        bands = [b for b in (band or DEFAULT_BANDS) if b in BANDS]
        rows = svc.queue(bands=bands, lang=lang, source=source, hours=hours or None, include_dups=bool(dups))
        return TEMPLATES.TemplateResponse(request, "queue.html", ctx(
            request, rows=rows, bands=bands, all_bands=BANDS, lang=lang, source=source, hours=hours, dups=dups, msg=msg,
            source_keys=sorted(app.sources.keys()), counts=app.articles.counts()))

    @web.get("/search", response_class=HTMLResponse)
    def search(request: Request, q: str = "", lang: str = "", source: str = "", band: str = "", hours: int = 0,
               video: int = 0, msg: str = ""):
        band = band if band in BANDS else ""
        hours = hours if hours in SEARCH_HOURS else 0
        res = (svc.search(q, lang=lang, source=source, band=band, hours=hours, video_only=bool(video)) if q.strip()
               else {"rows": [], "aliases": [], "failing": app.alerts.open_incidents(source or None)})
        return TEMPLATES.TemplateResponse(request, "search.html", ctx(
            request, q=q, lang=lang, source=source, band=band, hours=hours, video=bool(video), msg=msg,
            rows=res["rows"], aliases=res["aliases"], failing=res["failing"], all_bands=BANDS,
            search_hours=SEARCH_HOURS, source_keys=sorted(app.sources.keys())))

    async def _form(request: Request) -> dict:
        body = await request.body()
        if len(body) > FORM_MAX_BYTES:
            raise HTTPException(413, "form too large")
        return {k: v[0] for k, v in parse_qs(body.decode("utf-8", "replace")).items()}

    @web.post("/searches")
    async def save_search(request: Request):
        if not _same_origin(request):
            raise HTTPException(403, "cross-origin request refused")
        f = await _form(request)
        q = (f.get("q") or "").strip()
        if not q or len(q) > 200:
            raise HTTPException(400, "query must be 1-200 characters")
        hours = int(f["hours"]) if f.get("hours") in {str(h) for h in SEARCH_HOURS} else None
        band = f.get("band") if f.get("band") in BANDS else None
        source = f.get("source") if f.get("source") in app.sources.keys() else None
        lang = f.get("lang") if f.get("lang") in LANG_KO else None
        app.searches.add(name=(f.get("name") or q), query=q, lang=lang, source_key=source, band=band, hours=hours,
                         video_only=f.get("video") == "1", alert=f.get("alert") == "1", editor=app.settings.desk_editor,
                         now_s=iso(app.clock.now()))
        return RedirectResponse("/searches?msg=" + quote("검색을 저장했습니다"), status_code=303)

    @web.get("/searches", response_class=HTMLResponse)
    def searches_page(request: Request, msg: str = ""):
        return TEMPLATES.TemplateResponse(request, "searches.html", ctx(request, searches=svc.saved_searches(), msg=msg))

    @web.post("/searches/{search_id}/open")
    def open_search(request: Request, search_id: int):
        if not _same_origin(request):
            raise HTTPException(403, "cross-origin request refused")
        s = app.searches.get(search_id)
        if s is None:
            raise HTTPException(404, "저장 검색을 찾을 수 없습니다")
        app.searches.mark_seen(search_id, iso(app.clock.now()))
        return RedirectResponse(svc.search_url(s), status_code=303)

    @web.post("/searches/{search_id}/{action}")
    def search_action(request: Request, search_id: int, action: str):
        if not _same_origin(request):
            raise HTTPException(403, "cross-origin request refused")
        s = app.searches.get(search_id)
        if s is None or action not in ("alert", "delete"):  # "open" is its own route above
            raise HTTPException(404, "저장 검색을 찾을 수 없습니다")
        if action == "delete":
            app.searches.delete(search_id)
            msg = "삭제했습니다"
        else:
            app.searches.set_alert(search_id, not s["alert"])
            msg = "알림을 껐습니다" if s["alert"] else "새 결과가 들어오면 알림을 띄웁니다"
        return RedirectResponse("/searches?msg=" + quote(msg), status_code=303)

    @web.get("/article/{uid}", response_class=HTMLResponse)
    def article(request: Request, uid: str, msg: str = ""):
        a = svc.article(uid)
        if a is None:
            raise HTTPException(404, "기사를 찾을 수 없습니다")
        return TEMPLATES.TemplateResponse(request, "article.html", ctx(request, a=a, msg=msg,
                                                                       ai_active=app.enricher.active))

    @web.get("/sources", response_class=HTMLResponse)
    def sources(request: Request):
        return TEMPLATES.TemplateResponse(request, "sources.html", ctx(
            request, rows=svc.sources(), runs=app.sources.recent_runs(40), quarantine=app.sources.recent_quarantine(30)))

    @web.post("/refresh")
    def refresh(request: Request):
        if not _same_origin(request):
            raise HTTPException(403, "cross-origin request refused")
        started = collector.trigger(force=True)
        return RedirectResponse("/?msg=" + ("수집을 시작했습니다" if started else "이미 수집 중입니다"), status_code=303)

    @web.get("/ai", response_class=HTMLResponse)
    def ai_page(request: Request, msg: str = ""):
        return TEMPLATES.TemplateResponse(request, "ai.html", ctx(request, ai=svc.ai_overview(), msg=msg))

    @web.post("/ai/toggle")
    def ai_toggle(request: Request):
        if not _same_origin(request):
            raise HTTPException(403, "cross-origin request refused")
        app.enricher.set_paused(not app.enricher.paused)
        return RedirectResponse("/ai?msg=" + ("AI를 일시 중지했습니다" if app.enricher.paused else "AI를 다시 켰습니다"),
                                status_code=303)

    @web.post("/article/{uid}/enrich")
    def enrich_one(request: Request, uid: str):
        if not _same_origin(request):
            raise HTTPException(403, "cross-origin request refused")
        if not app.enricher.active:
            return RedirectResponse(f"/article/{uid}?msg=AI가 꺼져 있습니다", status_code=303)
        rep = app.enrich(uids=[uid])
        msg = "AI 분석 완료" if rep and rep.done else ("라이선스상 AI 미적용" if rep and rep.not_allowed else
                                                  ("AI 분석 실패: " + (rep.stopped or "검증 실패, 검토 대기열 확인") if rep else "AI 분석 실패"))
        return RedirectResponse(f"/article/{uid}?msg={msg}", status_code=303)

    @web.post("/article/{uid}/verdict")
    async def verdict(request: Request, uid: str):
        if not _same_origin(request):
            raise HTTPException(403, "cross-origin request refused")
        body = await request.body()
        if len(body) > FORM_MAX_BYTES:
            raise HTTPException(413, "form too large")
        form = {k: v[0] for k, v in parse_qs(body.decode("utf-8", "replace")).items()}
        back = _local_path(form.get("next"), f"/article/{uid}")
        result = svc.add_verdict(uid, form.get("verdict", ""), form.get("note"))
        if result == "invalid":
            raise HTTPException(400, "unknown verdict")
        if result == "unknown":
            raise HTTPException(404, "기사를 찾을 수 없습니다")
        if result == "killed":
            raise HTTPException(409, "철회된 기사에는 판정을 남길 수 없습니다")
        msg = f"{VERDICT_KO[form['verdict']]} 등록됨"
        return RedirectResponse(back + ("&" if "?" in back else "?") + "msg=" + quote(msg), status_code=303)

    @web.get("/shift-report", response_class=HTMLResponse)
    def shift_report(request: Request, hours: int = 8, download: int = 0):
        shift = svc.shift_report(hours)
        resp = TEMPLATES.TemplateResponse(request, "shift_report.html", ctx(request, shift=shift, standalone=bool(download)))
        if download:
            stamp = app.clock.now().astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")
            resp.headers["Content-Disposition"] = f'attachment; filename="shift_report_{stamp}.html"'
        return resp

    @web.get("/alerts", response_class=HTMLResponse)
    def alerts_page(request: Request, all: int = 0, msg: str = ""):
        return TEMPLATES.TemplateResponse(request, "alerts.html", ctx(
            request, alerts=svc.alerts(include_done=bool(all)), show_all=bool(all), msg=msg,
            enabled=sorted(app.alert_kinds())))

    @web.get("/alerts/poll")
    def alerts_poll(after: int = 0):
        return JSONResponse(svc.alert_poll(after))

    @web.post("/alerts/ack-all")
    def alerts_ack_all(request: Request):
        if not _same_origin(request):
            raise HTTPException(403, "cross-origin request refused")
        n = app.alerts.acknowledge_all()
        return RedirectResponse("/alerts?msg=" + quote(f"{n}건 확인 처리"), status_code=303)

    @web.post("/alerts/{alert_id}/{action}")
    def alert_action(request: Request, alert_id: int, action: str):
        if not _same_origin(request):
            raise HTTPException(403, "cross-origin request refused")
        status = {"ack": "acknowledged", "dismiss": "dismissed"}.get(action)
        if status is None:
            raise HTTPException(404, "unknown action")
        if not app.alerts.set_status(alert_id, status):
            raise HTTPException(404, "알림을 찾을 수 없습니다")
        return RedirectResponse("/alerts?msg=" + quote("확인 처리" if action == "ack" else "무시 처리"), status_code=303)

    @web.get("/media", response_class=HTMLResponse)
    def media_page(request: Request, msg: str = ""):
        clips, capped = svc.clips_page()
        return TEMPLATES.TemplateResponse(request, "media.html", ctx(
            request, clips=clips, capped=capped, msg=msg, tool=app.media_tool is not None, clip_page=svc.CLIP_PAGE))

    @web.get("/media.csv")
    def media_csv():
        stamp = app.clock.now().astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")
        return Response(svc.clips_csv(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="ingest_sheet_{stamp}.csv"'})

    @web.get("/media/thumb/{asset_id}")
    def media_thumb(asset_id: int):
        from newsmon.domain.enums import Storage
        from newsmon.licence.policy import flags_from_snapshot
        r = app.media.thumb(asset_id)
        if not r or not r["thumb_path"]:
            raise HTTPException(404, "no thumbnail")
        flags = flags_from_snapshot(r["licence_snapshot"])
        if flags.storage is not Storage.FULL or (r["restrictions"] or "").strip() or r["status"] == "killed":
            raise HTTPException(404, "no thumbnail")  # the licence, a later restriction or a withdrawal forbids it
        thumbs = (app.cfg.paths.data_dir / "thumbs").resolve()
        p = (app.cfg.paths.data_dir / r["thumb_path"]).resolve()
        if not p.is_relative_to(thumbs) or not p.is_file():
            raise HTTPException(404, "no thumbnail")
        return FileResponse(p, media_type="image/jpeg")

    @web.post("/media/{asset_id}/{action}")
    def media_action(request: Request, asset_id: int, action: str):
        if not _same_origin(request):
            raise HTTPException(403, "cross-origin request refused")
        if action == "recheck":
            if not app.media.recheck(asset_id):
                raise HTTPException(404, "확인되지 않은 영상입니다")
            return RedirectResponse("/media?msg=" + quote("다음 수집 주기에 다시 확인합니다"), status_code=303)
        if action not in ("filed", "pending"):
            raise HTTPException(404, "unknown action")
        if not app.media.set_ingest(asset_id, action == "filed", app.settings.desk_editor, iso(app.clock.now())):
            raise HTTPException(404, "확인되지 않은 영상입니다")
        return RedirectResponse("/media?msg=" + quote("인제스트 완료로 표시" if action == "filed" else "표시 취소"),
                                status_code=303)

    @web.get("/healthz")
    def healthz():
        ok = app.db.integrity_ok()
        rep = app.last_report
        return JSONResponse({"ok": ok, "db": "ok" if ok else "failed", "ai": app.ai_status.header_label(),
                             "collecting": collector.running,
                             "last_cycle": rep.finished_utc if rep else None,
                             "counts": app.articles.counts()}, status_code=200 if ok else 503)

    return web


def wait_idle(web: FastAPI, timeout: float = 30.0) -> None:
    """Test helper: block until a triggered collection finishes."""
    t0 = time.monotonic()
    while web.state.collector.running and time.monotonic() - t0 < timeout:
        time.sleep(0.05)
