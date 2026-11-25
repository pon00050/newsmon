"""TS-U-settings (T-02): boot from env vars only; O1 defaults; unknown keys rejected."""
from pathlib import Path

import pytest

from newsmon.config.loader import ConfigError, load_config
from newsmon.config.settings import Settings

pytestmark = pytest.mark.unit
EXAMPLE = Path(__file__).resolve().parents[3] / "config.example"


@pytest.mark.req("IR-05", "NFR-20")
def test_boot_from_env_only(tmp_path, monkeypatch):
    # A settings.yaml in the cwd must be ignored: only NEWSMON_CONFIG_DIR is read.
    (tmp_path / "cwd").mkdir()
    (tmp_path / "cwd" / "settings.yaml").write_text("use_context: internal\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "cwd")
    env = {"NEWSMON_CONFIG_DIR": str(EXAMPLE), "NEWSMON_DATA_DIR": str(tmp_path / "data")}
    cfg = load_config(env)
    assert cfg.settings.use_context == "private"  # from config.example, not the cwd file
    assert cfg.paths.data_dir == (tmp_path / "data").resolve()
    assert cfg.paths.db_path == (tmp_path / "data" / "newsmon.sqlite").resolve()
    assert cfg.paths.config_dir == EXAMPLE


@pytest.mark.req("NFR-20")
def test_db_path_override_and_data_dir_required(tmp_path):
    cfg = load_config({"NEWSMON_DATA_DIR": str(tmp_path), "NEWSMON_DB_PATH": str(tmp_path / "x.db")})
    assert cfg.paths.db_path.name == "x.db"
    with pytest.raises(ConfigError, match="NEWSMON_DATA_DIR"):
        load_config({})


@pytest.mark.req("IR-05")
def test_every_ai_capability_defaults_false(tmp_path):
    s = Settings()
    assert s.ai.capabilities.model_dump() == {
        "triage": False, "enrich": False, "embed": False, "digest_draft": False, "query_rewrite": False}
    assert not s.ai.capabilities.any_enabled()
    # The shipped example is O1 as well.
    cfg = load_config({"NEWSMON_CONFIG_DIR": str(EXAMPLE), "NEWSMON_DATA_DIR": str(tmp_path)})
    assert not cfg.settings.ai.capabilities.any_enabled()


@pytest.mark.req("IR-05")
@pytest.mark.parametrize("yaml_text", [
    "no_such_key: 1\n",
    "ai:\n  capabilities:\n    summarize_everything: true\n",
    "fetch:\n  ssrf_allow: [127.0.0.1]\n",
])
def test_unknown_keys_rejected(tmp_path, yaml_text):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "settings.yaml").write_text(yaml_text, encoding="utf-8")
    with pytest.raises(ConfigError, match="settings.yaml"):
        load_config({"NEWSMON_CONFIG_DIR": str(cfg_dir), "NEWSMON_DATA_DIR": str(tmp_path / "d")})


def test_poll_floor_cannot_be_lowered(tmp_path):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "settings.yaml").write_text("fetch:\n  min_poll_seconds: 60\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="min_poll_seconds"):
        load_config({"NEWSMON_CONFIG_DIR": str(cfg_dir), "NEWSMON_DATA_DIR": str(tmp_path / "d")})


@pytest.mark.req("NFR-14")
def test_kst_display_and_unknown_zone_rejected(tmp_path):
    from newsmon.web.service import kst
    assert kst("2026-11-25T00:30:00+00:00") == "11-25 09:30"  # UTC storage, KST display (no DST in Korea)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "settings.yaml").write_text("timezone: Mars/Olympus\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="time zone"):
        load_config({"NEWSMON_CONFIG_DIR": str(cfg_dir), "NEWSMON_DATA_DIR": str(tmp_path / "d")})
