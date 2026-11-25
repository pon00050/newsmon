"""Local web UI (Release A subset of UI-1 queue, UI-3 item detail, UI-4 search, UI-8 sources; Korean, KST display).

Loopback only, no login (auth_mode=local). POST routes require a same-origin request, so a page on another site cannot
trigger them from the user's browser. Templates autoescape everything; links are rendered only for http(s) URLs.
"""
from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from newsmon.obs.logging import event
from newsmon.web.service import BANDS, DEFAULT_BANDS, Service

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
        return {"request": request, "ai_label": app.ai_status.header_label(), "band_ko": BAND_KO, "lang_ko": LANG_KO,
                "collecting": collector.running, "collect_error": collector.last_error, "report": app.last_report,
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
    def search(request: Request, q: str = "", lang: str = "", source: str = ""):
        res = svc.search(q, lang=lang, source=source) if q.strip() else {"rows": [], "aliases": []}
        return TEMPLATES.TemplateResponse(request, "search.html", ctx(
            request, q=q, lang=lang, source=source, rows=res["rows"], aliases=res["aliases"],
            source_keys=sorted(app.sources.keys())))

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
