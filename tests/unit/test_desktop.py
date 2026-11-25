"""Desktop launcher: directory resolution, first-run seeding, port detection (loopback only)."""
from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from newsmon import desktop

pytestmark = pytest.mark.unit


# --- directory resolution ------------------------------------------------------------------------------------------------
def test_windows_default_dirs_under_localappdata():
    cfg, data = desktop.default_dirs({"LOCALAPPDATA": r"C:\Users\x\AppData\Local"}, platform="win32")
    assert cfg == Path(r"C:\Users\x\AppData\Local") / "Newsmon" / "config"
    assert data == Path(r"C:\Users\x\AppData\Local") / "Newsmon" / "data"


def test_posix_default_dirs_honour_xdg_then_home(tmp_path):
    cfg, data = desktop.default_dirs({"XDG_DATA_HOME": str(tmp_path)}, platform="linux")
    assert (cfg, data) == (tmp_path / "newsmon" / "config", tmp_path / "newsmon" / "data")
    cfg, data = desktop.default_dirs({}, platform="linux")
    assert cfg == Path.home() / ".local" / "share" / "newsmon" / "config"


def test_env_beats_default_and_argument_beats_env(tmp_path):
    env = {"NEWSMON_CONFIG_DIR": str(tmp_path / "ec"), "NEWSMON_DATA_DIR": str(tmp_path / "ed"), "LOCALAPPDATA": str(tmp_path)}
    assert desktop.resolve_dirs(env=env, platform="win32") == (tmp_path / "ec", tmp_path / "ed")
    assert desktop.resolve_dirs(tmp_path / "ac", None, env=env, platform="win32") == (tmp_path / "ac", tmp_path / "ed")
    assert desktop.resolve_dirs(None, tmp_path / "ad", env={"LOCALAPPDATA": str(tmp_path)}, platform="win32") == (
        tmp_path / "Newsmon" / "config", tmp_path / "ad")


# --- first-run seeding ---------------------------------------------------------------------------------------------------
def _example(tmp_path: Path) -> Path:
    ex = tmp_path / "ex"
    (ex / "profiles").mkdir(parents=True)
    (ex / "inbox" / "empty").mkdir(parents=True)
    (ex / "settings.yaml").write_text("workspace_name: example\n", encoding="utf-8")
    (ex / "sources.yaml").write_text("sources: []\n", encoding="utf-8")
    (ex / "profiles" / "p.yaml").write_text("key: p\n", encoding="utf-8")
    return ex


def test_seed_copies_tree_on_first_run(tmp_path):
    cfg = tmp_path / "cfg"
    copied = desktop.seed_config(cfg, _example(tmp_path))
    assert len(copied) == 3
    assert (cfg / "settings.yaml").read_text(encoding="utf-8") == "workspace_name: example\n"
    assert (cfg / "profiles" / "p.yaml").is_file() and (cfg / "inbox" / "empty").is_dir()


def test_seed_is_skipped_when_settings_exist(tmp_path):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "settings.yaml").write_text("mine: true\n", encoding="utf-8")
    assert desktop.seed_config(cfg, _example(tmp_path)) == []
    assert sorted(p.name for p in cfg.iterdir()) == ["settings.yaml"]


def test_seed_never_overwrites_files_in_a_partial_config(tmp_path):
    cfg = tmp_path / "cfg"
    (cfg / "profiles").mkdir(parents=True)
    (cfg / "sources.yaml").write_text("sources: [mine]\n", encoding="utf-8")
    (cfg / "extra.txt").write_text("keep\n", encoding="utf-8")
    copied = desktop.seed_config(cfg, _example(tmp_path))
    assert (cfg / "sources.yaml").read_text(encoding="utf-8") == "sources: [mine]\n"
    assert (cfg / "extra.txt").read_text(encoding="utf-8") == "keep\n"
    assert cfg / "sources.yaml" not in copied and (cfg / "settings.yaml").is_file()


def test_seed_from_the_real_example_and_it_loads(tmp_path):
    src = desktop.find_example_dir()
    assert src is not None and (src / "settings.yaml").is_file()
    cfg = tmp_path / "cfg"
    assert desktop.seed_config(cfg)
    from newsmon.config.loader import load_config
    assert load_config(env={}, data_dir=tmp_path / "d", config_dir=cfg).settings.bind_port == 8765


def test_ensure_inbox_dirs_creates_only_directory_sources_inside_config(tmp_path):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    lines = ["sources:",
             "- {key: a, access_method: directory, path: inbox/a}",
             "- {key: b, access_method: rss, path: inbox/not_a_dir_source}",
             "- {key: c, access_method: directory, path: ../escape}"]
    (cfg / "sources.yaml").write_text(chr(10).join(lines), encoding="utf-8")
    made = desktop.ensure_inbox_dirs(cfg)
    assert made == [(cfg / "inbox" / "a").resolve()] and (cfg / "inbox" / "a").is_dir()
    assert not (cfg / "inbox" / "not_a_dir_source").exists() and not (tmp_path / "escape").exists()


def test_seed_without_example_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        desktop.seed_config(tmp_path / "cfg", tmp_path / "missing")


# --- port detection ------------------------------------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    body: bytes = b"{}"
    status = 200

    def do_GET(self):   # noqa: N802
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *a):
        pass


@pytest.fixture
def serve():
    servers = []

    def start(body: bytes, status: int = 200) -> int:
        handler = type("H", (_Handler,), {"body": body, "status": status})
        srv = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return srv.server_address[1]

    yield start
    for s in servers:
        s.shutdown()
        s.server_close()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_probe_free_port():
    assert desktop.probe_port(_free_port()) == desktop.FREE


def test_probe_detects_newsmon(serve):
    port = serve(json.dumps({"ok": True, "db": "ok", "counts": {"articles": 0}}).encode())
    assert desktop.probe_port(port) == desktop.NEWSMON
    assert desktop.wait_ready(port, timeout=3)


def test_probe_detects_newsmon_with_failed_integrity(serve):
    port = serve(json.dumps({"ok": False, "db": "failed", "counts": {}}).encode(), status=503)
    assert desktop.probe_port(port) == desktop.NEWSMON
    assert not desktop.wait_ready(port, timeout=0.6)   # present but not healthy: not "ready"


@pytest.mark.parametrize("body", [b"<html>hi</html>", b'{"status": "up"}', b"[1, 2]"])
def test_probe_other_program_on_port(serve, body):
    assert desktop.probe_port(serve(body)) == desktop.OTHER


# --- main() paths that need no server ------------------------------------------------------------------------------------
def test_main_opens_browser_when_newsmon_already_running(serve, tmp_path, monkeypatch, capsys):
    port = serve(json.dumps({"ok": True, "db": "ok", "counts": {}}).encode())
    opened = []
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url: opened.append(url) or True)
    rc = desktop.main(["--config", str(tmp_path / "c"), "--data", str(tmp_path / "d"), "--port", str(port)])
    assert rc == 0 and opened == [f"http://127.0.0.1:{port}/"]
    assert "already running" in capsys.readouterr().out


def test_main_reports_port_taken_by_other_program(serve, tmp_path, monkeypatch, capsys):
    port = serve(b"<html></html>")
    opened = []
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url: opened.append(url) or True)
    rc = desktop.main(["--config", str(tmp_path / "c"), "--data", str(tmp_path / "d"), "--port", str(port)])
    out = capsys.readouterr().out
    assert rc == 3 and not opened
    assert f"Port {port} is in use" in out and "포트" in out


def test_main_no_browser_flag(serve, tmp_path, monkeypatch):
    port = serve(json.dumps({"ok": True, "db": "ok", "counts": {}}).encode())
    opened = []
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url: opened.append(url) or True)
    assert desktop.main(["--config", str(tmp_path / "c"), "--data", str(tmp_path / "d"), "--port", str(port),
                         "--no-browser"]) == 0
    assert opened == []
