"""TS-DEP04 (T-02): a settings.yaml holding api_key / password / token values is rejected with a message."""
import pytest

from newsmon.config.loader import ConfigError, find_secret_like, load_config

pytestmark = pytest.mark.unit


def _load(tmp_path, text):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "settings.yaml").write_text(text, encoding="utf-8")
    return load_config({"NEWSMON_CONFIG_DIR": str(cfg_dir), "NEWSMON_DATA_DIR": str(tmp_path / "d")})


@pytest.mark.req("DEP-04")
@pytest.mark.parametrize("text,where", [
    ("ai:\n  api_key: abc123secret\n", "ai.api_key"),
    ("smtp:\n  password: hunter2\n", "smtp.password"),
    ("token: deadbeef\n", "token"),
    ("smtp:\n  from_addr: sk-ant-api03-AAAAAAAAAAAAAAAA\n", "smtp.from_addr"),
])
def test_secret_values_rejected(tmp_path, text, where):
    with pytest.raises(ConfigError) as exc:
        _load(tmp_path, text)
    msg = str(exc.value)
    assert where in msg and "secret" in msg
    # The message never echoes the secret value.
    for value in ("abc123secret", "hunter2", "deadbeef", "sk-ant-api03"):
        assert value not in msg


@pytest.mark.req("DEP-04")
def test_secret_references_allowed(tmp_path):
    cfg = _load(tmp_path, "smtp:\n  password_secret_name: SMTP_PASSWORD\nai:\n  anthropic_secret_name: ANTHROPIC_API_KEY\n")
    assert cfg.settings.smtp.password_secret_name == "SMTP_PASSWORD"


def test_detector_controls():
    # known-answer and nonsense controls for the detector itself
    assert find_secret_like({"a": {"api_key": "x"}}) == ["a.api_key"]
    assert find_secret_like({"a": {"api_key_name": "X", "max_tokens": 100, "label": "token budget"}}) == []
