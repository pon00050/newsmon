"""12-factor configuration loader (ADR-009 #1, NFR-20).

- `NEWSMON_CONFIG_DIR`: directory holding settings.yaml, sources.yaml, profiles/, gazetteer.yaml, boilerplate.yaml.
- `NEWSMON_DATA_DIR`: the only directory the application writes to.
- `NEWSMON_DB_PATH`: optional; defaults to `<data_dir>/newsmon.sqlite`.

Nothing is read from the current working directory. YAML is parsed with `safe_load` only, and a YAML value that looks like
a secret is refused (DEP-04): secrets belong in the environment or `.env`, read through `SecretStore`.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from newsmon.config.settings import AppConfig, Paths, Settings

ENV_CONFIG_DIR = "NEWSMON_CONFIG_DIR"
ENV_DATA_DIR = "NEWSMON_DATA_DIR"
ENV_DB_PATH = "NEWSMON_DB_PATH"

# A key that names a secret *value*. Keys that only *refer* to a secret (…_secret_name, …_ref, …_env) are allowed.
_SECRET_KEY = re.compile(r"(api[_-]?key|password|passwd|secret|token|private[_-]?key|credential)s?$", re.I)
_REFERENCE_SUFFIX = re.compile(r"_(name|ref|env|id)$", re.I)
_SECRET_VALUE = re.compile(r"^(sk-|sk_|xox[bp]-|ghp_|AKIA)[A-Za-z0-9_\-]{8,}")


class ConfigError(ValueError):
    """Raised for any invalid configuration; the message is safe to show (it never echoes a secret value)."""


def find_secret_like(data: Any, path: str = "") -> list[str]:
    """Return dotted paths of YAML entries that look like inline secrets."""
    hits: list[str] = []
    if isinstance(data, Mapping):
        for k, v in data.items():
            p = f"{path}.{k}" if path else str(k)
            key = str(k)
            if isinstance(v, str) and v.strip() and _SECRET_KEY.search(key) and not _REFERENCE_SUFFIX.search(key):
                hits.append(p)
            elif isinstance(v, str) and _SECRET_VALUE.match(v.strip()):
                hits.append(p)
            else:
                hits.extend(find_secret_like(v, p))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            if isinstance(v, str) and _SECRET_VALUE.match(v.strip()):
                hits.append(f"{path}[{i}]")
            else:
                hits.extend(find_secret_like(v, f"{path}[{i}]"))
    return hits


def read_yaml(path: Path) -> Any:
    """safe_load a YAML file and refuse inline secrets."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name}: invalid YAML ({exc.__class__.__name__})") from None
    hits = find_secret_like(data)
    if hits:
        raise ConfigError(
            f"{path.name}: secret-looking value(s) at {', '.join(hits)}; secrets belong in the environment or .env "
            "and are referenced by name (e.g. password_secret_name)"
        )
    return data


def load_settings(config_dir: Path | None) -> Settings:
    if config_dir is None:
        return Settings()
    f = config_dir / "settings.yaml"
    if not f.exists():
        return Settings()
    data = read_yaml(f) or {}
    if not isinstance(data, dict):
        raise ConfigError("settings.yaml: top level must be a mapping")
    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise ConfigError(f"settings.yaml: {problems}") from None


def load_config(env: Mapping[str, str] | None = None, *, data_dir: Path | None = None,
                config_dir: Path | None = None) -> AppConfig:
    """Build the app config from environment variables (explicit arguments win, for the CLI's flags)."""
    env = os.environ if env is None else env
    cfg_dir = config_dir or (Path(env[ENV_CONFIG_DIR]) if env.get(ENV_CONFIG_DIR) else None)
    if cfg_dir is not None and not cfg_dir.is_dir():
        raise ConfigError(f"{ENV_CONFIG_DIR} is not a directory: {cfg_dir}")
    d_dir = data_dir or (Path(env[ENV_DATA_DIR]) if env.get(ENV_DATA_DIR) else None)
    if d_dir is None:
        raise ConfigError(f"{ENV_DATA_DIR} is not set; newsmon writes state only under an explicit data directory")
    db = Path(env[ENV_DB_PATH]) if env.get(ENV_DB_PATH) else d_dir / "newsmon.sqlite"
    settings = load_settings(cfg_dir)
    return AppConfig(settings=settings, paths=Paths(config_dir=cfg_dir, data_dir=d_dir.resolve(), db_path=db.resolve()))
