"""TS-NFR27b (T-09): get() by name; repr never shows a value; every credential has an owner tag."""
import pytest

from newsmon.adapters.secrets import EnvSecretStore

pytestmark = pytest.mark.unit


@pytest.mark.req("NFR-27", "DEP-04")
def test_get_owner_and_repr(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SMTP_PASSWORD=from-file-secret\nWIRE_KEY=wire-secret-value\n", encoding="utf-8")
    s = EnvSecretStore(env_file, env={"ANTHROPIC_API_KEY": "env-secret-value"}, owners={"WIRE_KEY": "customer"})
    assert s.get("ANTHROPIC_API_KEY") == "env-secret-value"
    assert s.get("SMTP_PASSWORD") == "from-file-secret"
    assert s.get("MISSING") is None
    assert s.owner("ANTHROPIC_API_KEY") == "provider" and s.owner("WIRE_KEY") == "customer"
    assert s.owner("ANY_OTHER") == "customer"  # unknown credentials default to the customer
    text = repr(s) + str(s)
    for v in ("env-secret-value", "from-file-secret", "wire-secret-value"):
        assert v not in text
    assert set(s.values()) >= {"env-secret-value", "from-file-secret", "wire-secret-value"}


def test_environment_wins_over_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=file\n", encoding="utf-8")
    assert EnvSecretStore(env_file, env={"OPENAI_API_KEY": "env"}).get("OPENAI_API_KEY") == "env"
