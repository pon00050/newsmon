"""Regenerate the screenshots in site/static/screenshots/ (used by README.md and the website).

    uv run python scripts/take_screenshots.py [--browser PATH] [--site https://pon00050.github.io/newsmon]

The local-app screenshots come from a throwaway instance of the real application loaded with the synthetic demo
wire (demo/config + demo/make_demo_inbox.py), served on loopback. No third-party news appears in them. The dashboard
screenshots are taken from the published website. Needs a Chromium-based browser (Edge or Chrome) for headless capture.
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "static" / "screenshots"
PORT = 8791
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/microsoft-edge"]


def run_cli(*args: str, env: dict) -> None:
    subprocess.run([sys.executable, "-c", "import sys; from newsmon.cli import main; sys.exit(main(sys.argv[1:]))",
                    *args], env=env, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def wait_http(url: str, seconds: float = 60) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise SystemExit(f"{url} did not answer")


def shot(browser: str, url: str, out: Path, width: int, height: int, profile: Path) -> None:
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                    f"--user-data-dir={profile}", f"--window-size={width},{height}", "--virtual-time-budget=4000",
                    f"--screenshot={out}", url], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=120)
    if not out.exists() or out.stat().st_size < 5000:
        raise SystemExit(f"screenshot failed: {url}")
    print(f"{out.relative_to(ROOT)}  {out.stat().st_size // 1024} KB  <- {url}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", default=next((b for b in BROWSERS if Path(b).exists()), None))
    ap.add_argument("--site", default="https://pon00050.github.io/newsmon")
    a = ap.parse_args()
    if not a.browser:
        raise SystemExit("no Chromium-based browser found; pass --browser")
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            raise SystemExit(f"port {PORT} is in use")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="newsmon-shots-") as tmp:
        tmp = Path(tmp)
        cfg, data, profile = tmp / "config", tmp / "data", tmp / "profile"
        shutil.copytree(ROOT / "demo" / "config", cfg)
        (cfg / "inbox" / "demo").mkdir(parents=True)
        subprocess.run([sys.executable, "-I", str(ROOT / "demo" / "make_demo_inbox.py"), "--out",
                        str(cfg / "inbox" / "demo")], check=True, stdout=subprocess.DEVNULL)
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")}
        env.update(NEWSMON_CONFIG_DIR=str(cfg), NEWSMON_DATA_DIR=str(data))
        run_cli("init", env=env)
        run_cli("collect", "--force", env=env)
        run_cli("collect", "--force", env=env)  # the inbox watcher ingests files stable across two scans
        sys.path.insert(0, str(ROOT / "src"))
        from newsmon.app import App
        from newsmon.config.loader import load_config
        app = App(load_config(data_dir=data, config_dir=cfg), setup_logging=False)
        try:
            top = app.articles.queue(bands=["flash"], limit=1)[0]["uid"]
        finally:
            app.close()
        server = subprocess.Popen([sys.executable, "-c", "import sys; from newsmon.cli import main; "
                                   "sys.exit(main(sys.argv[1:]))", "serve", "--port", str(PORT)],
                                  env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=open(tmp / "serve.log", "w"))
        try:
            base = f"http://127.0.0.1:{PORT}"
            try:
                wait_http(base + "/healthz")
            except SystemExit:
                print((tmp / "serve.log").read_text(encoding="utf-8", errors="replace")[-3000:], file=sys.stderr)
                raise
            shot(a.browser, base + "/", OUT / "local-queue.png", 1280, 900, profile)
            shot(a.browser, base + f"/article/{top}", OUT / "local-item-detail.png", 1280, 900, profile)
            shot(a.browser, base + "/search?q=%EA%B4%80%EC%84%B8", OUT / "local-search-korean.png", 1280, 760, profile)
            shot(a.browser, base + "/sources", OUT / "local-sources.png", 1280, 620, profile)
        finally:
            server.terminate()
            server.wait(timeout=20)
        shot(a.browser, a.site + "/dashboard.html#live", OUT / "dashboard-live.png", 1280, 1500, profile)
        shot(a.browser, a.site + "/dashboard.html#synthetic", OUT / "dashboard-synthetic.png", 1280, 1500, profile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
