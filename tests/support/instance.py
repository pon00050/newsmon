"""Build an isolated newsmon instance for tests: a config dir, a data dir, fixture feeds served from loopback, and an
inbox copied from the synthetic wire fixtures. The SSRF allowance for the fixture port is constructed here, in tests
only (TS-SEC-10)."""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from newsmon.app import App
from newsmon.config.loader import load_config
from newsmon.fetcher.ssrf import SsrfPolicy
from tests.support.fixture_server import FixtureServer, Resp
from tests.support.wire_recipes import copy_inbox

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config.example"
FEEDS = ROOT / "tests" / "fixtures" / "feeds"
MOCK_SOURCES = ROOT / "tests" / "fixtures" / "wire" / "sources_mock.yaml"

FEED_FLAGS = {"storage": "metadata", "display": "headline", "ai_processing": "unknown", "external_ai_allowed": True}


def feed_source(key: str, url: str, lang: str = "en", **flags) -> dict:
    d = {"key": key, "name": key, "access_method": "feed", "lang": lang, "url": url, "poll_seconds": 600, **FEED_FLAGS}
    d.update(flags)
    return d


def mock_wire_sources(inbox_rel: str = "inbox") -> list[dict]:
    rows = yaml.safe_load(MOCK_SOURCES.read_text(encoding="utf-8"))["sources"]
    out = []
    for r in rows:
        r = dict(r)
        r["lang"] = r.pop("lang_default", "en")
        r["path"] = f"{inbox_rel}/{r['key']}"
        out.append(r)
    return out


def write_config(cfg_dir: Path, sources: list[dict], *, settings: dict | None = None, profile: dict | None = None) -> Path:
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "settings.yaml").write_text(yaml.safe_dump(settings or {"use_context": "private"}), encoding="utf-8")
    (cfg_dir / "sources.yaml").write_text(yaml.safe_dump({"sources": sources}, allow_unicode=True), encoding="utf-8")
    shutil.copy(EXAMPLE / "gazetteer.yaml", cfg_dir / "gazetteer.yaml")
    (cfg_dir / "profiles").mkdir(exist_ok=True)
    if profile is None:
        prof = yaml.safe_load((EXAMPLE / "profiles" / "foreign_desk.yaml").read_text(encoding="utf-8"))
        keys = {s["key"] for s in sources}
        prof["sources"]["prefer"] = {k: v for k, v in prof["sources"]["prefer"].items() if k in keys}
        prof["sources"]["mute"] = [k for k in prof["sources"]["mute"] if k in keys]
        profile = prof
    (cfg_dir / "profiles" / f"{profile['key']}.yaml").write_text(yaml.safe_dump(profile, allow_unicode=True),
                                                                 encoding="utf-8")
    return cfg_dir


def serve_feeds(server: FixtureServer, names: list[str]) -> dict[str, str]:
    """Route each fixture feed file at /feeds/<name>; robots.txt allows everything."""
    server.route("/robots.txt", Resp(body=b"User-agent: *\nAllow: /\n", content_type="text/plain"))
    return {n: server.route(f"/feeds/{n}", Resp.file(FEEDS / n)) for n in names}


def make_app(tmp: Path, server: FixtureServer | None, sources: list[dict], *, clock=None, settings=None, profile=None,
             with_inbox: bool = False) -> App:
    cfg_dir = write_config(tmp / "cfg", sources, settings=settings, profile=profile)
    if with_inbox:
        for key in ("mock_wire_gated", "mock_wire_demo"):
            (cfg_dir / "inbox" / key).mkdir(parents=True, exist_ok=True)
    cfg = load_config({"NEWSMON_CONFIG_DIR": str(cfg_dir), "NEWSMON_DATA_DIR": str(tmp / "data")})
    policy = SsrfPolicy(allow_loopback_ports=frozenset({server.port})) if server else None
    return App(cfg, clock=clock, ssrf_policy=policy, sleep=lambda s: None)


def fill_inbox(app: App, key: str = "mock_wire_demo") -> list[Path]:
    return copy_inbox(app.resolve_inbox(f"inbox/{key}"))
