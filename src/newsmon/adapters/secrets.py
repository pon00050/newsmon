"""SecretStore over the environment and an optional `.env` file (T-09 essential portion; NFR-27, DEP-04).

The only module allowed to read secret values from the environment (TS-ARCH-03). Values are never logged, stored in the
database or returned by any page; `values()` exists only to feed the log redaction filter.
"""
from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path

from dotenv import dotenv_values

KNOWN_OWNERS = {"ANTHROPIC_API_KEY": "provider", "OPENAI_API_KEY": "provider", "SMTP_PASSWORD": "customer"}


class EnvSecretStore:
    def __init__(self, env_file: Path | None = None, env: Mapping[str, str] | None = None,
                 owners: Mapping[str, str] | None = None) -> None:
        self._file = {k: v for k, v in (dotenv_values(env_file) if env_file and env_file.exists() else {}).items() if v}
        self._env = os.environ if env is None else env
        self._owners = {**KNOWN_OWNERS, **(owners or {})}

    def get(self, name: str, workspace_id: int = 1) -> str | None:
        return self._env.get(name) or self._file.get(name) or None

    def owner(self, name: str) -> str:
        return self._owners.get(name, "customer")

    def values(self) -> Iterable[str]:
        names = set(self._owners) | set(self._file)
        return [v for v in (self.get(n) for n in names) if v]

    def __repr__(self) -> str:
        return f"EnvSecretStore(names={sorted(set(self._owners) | set(self._file))})"
