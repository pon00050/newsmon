"""One-click desktop launcher: `newsmon-desktop` (and the frozen Windows executable).

Does what the README asks of a non-technical user in one step:

1. resolves a per-user config and data directory (nothing is written anywhere else),
2. on first run seeds the config directory from the bundled `config.example` (never overwrites, never deletes),
3. runs the same initialisation as `newsmon init`,
4. starts the same server as `newsmon serve --auto-collect` (loopback only),
5. opens the default browser once /healthz answers.

If the port is already serving Newsmon it only opens the browser; if something else holds the port it says so and fails.
All process logic is reused from `newsmon.ops.commands`; this module adds only directory defaults, seeding and the
browser hand-off.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Mapping
from pathlib import Path

from newsmon.config.loader import ENV_CONFIG_DIR, ENV_DATA_DIR, ConfigError, load_config

HOST = "127.0.0.1"
READY_TIMEOUT_SECONDS = 60.0
EXAMPLE_DIRNAME = "config.example"

# probe_port() results
FREE, NEWSMON, OTHER = "free", "newsmon", "other"


# --- directories ------------------------------------------------------------------------------------------------------
def default_dirs(env: Mapping[str, str] | None = None, platform: str | None = None) -> tuple[Path, Path]:
    """Per-user (config_dir, data_dir): %LOCALAPPDATA%\\Newsmon on Windows, ~/.local/share/newsmon elsewhere."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if platform.startswith("win"):
        base = Path(env["LOCALAPPDATA"]) if env.get("LOCALAPPDATA") else Path.home() / "AppData" / "Local"
        root = base / "Newsmon"
    else:
        base = Path(env["XDG_DATA_HOME"]) if env.get("XDG_DATA_HOME") else Path.home() / ".local" / "share"
        root = base / "newsmon"
    return root / "config", root / "data"


def resolve_dirs(config: Path | None = None, data: Path | None = None, env: Mapping[str, str] | None = None,
                 platform: str | None = None) -> tuple[Path, Path]:
    """Precedence per directory: explicit argument, then NEWSMON_CONFIG_DIR / NEWSMON_DATA_DIR, then the default."""
    env = os.environ if env is None else env
    d_cfg, d_data = default_dirs(env, platform)
    cfg = config or (Path(env[ENV_CONFIG_DIR]) if env.get(ENV_CONFIG_DIR) else d_cfg)
    dat = data or (Path(env[ENV_DATA_DIR]) if env.get(ENV_DATA_DIR) else d_data)
    return Path(cfg), Path(dat)


# --- first-run seeding --------------------------------------------------------------------------------------------------
def find_example_dir() -> Path | None:
    """The bundled config.example: sys._MEIPASS when frozen, else the repository root (src layout), else beside the package."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / EXAMPLE_DIRNAME)
    here = Path(__file__).resolve()
    candidates.append(here.parents[2] / EXAMPLE_DIRNAME)   # <repo>/src/newsmon/desktop.py -> <repo>/config.example
    candidates.append(here.parent / EXAMPLE_DIRNAME)
    return next((c for c in candidates if c.is_dir()), None)


def seed_config(config_dir: Path, example_dir: Path | None = None) -> list[Path]:
    """If config_dir has no settings.yaml, copy the example tree into it. Returns the files copied (empty if not seeded).

    Never overwrites an existing file and never deletes anything; existing files in a half-populated directory are kept.
    """
    if (config_dir / "settings.yaml").exists():
        return []
    src = example_dir if example_dir is not None else find_example_dir()
    if src is None or not src.is_dir():
        raise FileNotFoundError(f"bundled {EXAMPLE_DIRNAME} not found")
    copied: list[Path] = []
    config_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if "__pycache__" in rel.parts:
            continue
        dest = config_dir / rel
        if path.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        elif not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(path.read_bytes())
            copied.append(dest)
    return copied


def ensure_inbox_dirs(config_dir: Path) -> list[Path]:
    """Create the (empty) folders that directory-type sources in sources.yaml point at, inside config_dir only.

    The example ships these as empty directories, which neither git archives nor PyInstaller bundles preserve; without them
    the demo wire sources report "inbox root missing" on every cycle.
    """
    import yaml
    made: list[Path] = []
    try:
        data = yaml.safe_load((config_dir / "sources.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return made
    items = data.get("sources", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    base = config_dir.resolve()
    for item in items:
        if not (isinstance(item, dict) and item.get("access_method") == "directory" and isinstance(item.get("path"), str)):
            continue
        target = (base / item["path"]).resolve()
        if target != base and base in target.parents and not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            made.append(target)
    return made


# --- port / health ------------------------------------------------------------------------------------------------------
def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))   # loopback must never go through a proxy


def healthz(port: int, timeout: float = 2.0) -> dict | None:
    """The parsed /healthz body of a Newsmon on this port, or None (not listening, not HTTP, or not Newsmon)."""
    try:
        with _opener().open(f"http://{HOST}:{port}/healthz", timeout=timeout) as resp:
            body = json.loads(resp.read(65536).decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:   # 503 from a Newsmon with a failed integrity check still carries the body
        try:
            body = json.loads(exc.read(65536).decode("utf-8", "replace"))
        except (ValueError, OSError):
            return None
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) and "db" in body and "counts" in body else None


def _listening(port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((HOST, port)) == 0


def probe_port(port: int) -> str:
    """FREE (nothing listening), NEWSMON (a Newsmon answers /healthz) or OTHER (something else holds the port)."""
    if not _listening(port):
        return FREE
    return NEWSMON if healthz(port) is not None else OTHER


def wait_ready(port: int, timeout: float = READY_TIMEOUT_SECONDS, stop: threading.Event | None = None) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not (stop and stop.is_set()):
        body = healthz(port, timeout=1.0)
        if body is not None and body.get("ok"):
            return True
        time.sleep(0.25)
    return False


# --- main ---------------------------------------------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="newsmon-desktop", description="Start Newsmon and open it in your browser / "
                                "Newsmon을 시작하고 브라우저에서 엽니다")
    p.add_argument("--config", type=Path, help=f"config directory (default: ${ENV_CONFIG_DIR} or the per-user default)")
    p.add_argument("--data", type=Path, help=f"data directory (default: ${ENV_DATA_DIR} or the per-user default)")
    p.add_argument("--port", type=int, help="port (default: bind_port in settings.yaml, 8765)")
    p.add_argument("--no-browser", action="store_true", help="do not open the browser")
    return p


def _say(*lines: str) -> None:
    for line in lines:
        print(line, flush=True)


def _open_browser(url: str, enabled: bool) -> None:
    if enabled:
        try:
            webbrowser.open(url)
        except Exception as exc:   # a missing default browser must not stop the server
            _say(f"Could not open the browser ({exc}); open {url} yourself. / 브라우저를 열지 못했습니다. {url} 을 직접 여세요.")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and not stream.isatty():
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    config_dir, data_dir = resolve_dirs(args.config, args.data)

    try:
        seeded = seed_config(config_dir)
        if seeded:
            ensure_inbox_dirs(config_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, FileNotFoundError) as exc:
        _say(f"Newsmon cannot prepare its folders: {exc}", f"Newsmon이 폴더를 준비하지 못했습니다: {exc}")
        return 2
    if seeded:
        _say(f"First run: copied {len(seeded)} starter configuration file(s) into {config_dir}",
             f"처음 실행: 기본 설정 파일 {len(seeded)}개를 {config_dir} 에 복사했습니다")

    try:
        cfg = load_config(data_dir=data_dir, config_dir=config_dir)
    except ConfigError as exc:
        _say(f"Newsmon configuration error: {exc}", f"설정 오류: {exc}",
             f"Fix the files in {config_dir} and start again. / {config_dir} 의 파일을 고친 뒤 다시 시작하세요.")
        return 2
    port = args.port or cfg.settings.bind_port
    url = f"http://{HOST}:{port}/"

    state = probe_port(port)
    if state == NEWSMON:
        _say(f"Newsmon is already running at {url} - opening it. / Newsmon이 이미 {url} 에서 실행 중입니다. 브라우저를 엽니다.")
        _open_browser(url, not args.no_browser)
        return 0
    if state == OTHER:
        _say(f"Port {port} is in use by another program, not Newsmon. Close that program or start with --port <number>.",
             f"포트 {port} 를 다른 프로그램이 사용 중입니다. 그 프로그램을 닫거나 --port <번호> 로 다시 시작하세요.")
        return 3

    # Reuse the CLI's own code paths (same flags `newsmon init` / `newsmon serve --auto-collect` would parse).
    from newsmon.ops import commands
    ns = argparse.Namespace(config=config_dir, data=data_dir, port=port, auto_collect=True)
    rc = commands._init(ns)
    if rc:
        return rc

    _say("", "Newsmon / 뉴스몬",
         f"  config / 설정: {config_dir}", f"  data   / 데이터: {data_dir}",
         f"  address / 주소: {url}",
         "Starting... the page opens in your browser when ready. / 시작하는 중입니다. 준비되면 브라우저가 열립니다.",
         "Press Ctrl+C or close this window to stop. / 중지하려면 Ctrl+C 를 누르거나 이 창을 닫으세요.", "")

    stop = threading.Event()

    def _watch() -> None:
        if wait_ready(port, stop=stop):
            _say(f"Ready: {url} / 준비되었습니다: {url}")
            _open_browser(url, not args.no_browser)
        elif not stop.is_set():
            _say(f"Newsmon did not answer within {int(READY_TIMEOUT_SECONDS)} s; check the messages above. / "
                 f"{int(READY_TIMEOUT_SECONDS)}초 안에 응답하지 않았습니다. 위의 메시지를 확인하세요.")

    watcher = threading.Thread(target=_watch, name="newsmon-ready", daemon=True)
    watcher.start()
    try:
        return int(commands._serve(ns) or 0)
    except KeyboardInterrupt:
        _say("", "Stopped. / 중지했습니다.")
        return 0
    finally:
        stop.set()


if __name__ == "__main__":
    sys.exit(main())
