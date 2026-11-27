"""Typed settings (11 §9, IR-05). O1 is the default: every `ai.capabilities` flag is false.

Secrets never live here (DEP-04): the YAML may name a secret (`*_secret_name`), never contain one. Values are read
through `SecretStore` (T-09). There is deliberately no SSRF-allowance key (TS-SEC-10).
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AICapabilities(_Strict):
    triage: bool = False
    enrich: bool = False
    embed: bool = False
    digest_draft: bool = False
    query_rewrite: bool = False

    def any_enabled(self) -> bool:
        return any(self.model_dump().values())


class AISelection(_Strict):
    """Which articles are sent for optional enrichment (Release A.1). Never every article by default."""
    min_band: Literal["drop", "review", "report", "flash"] = "review"  # rule band an item needs to be selected
    max_items_per_cycle: int = Field(20, ge=0)
    sources: tuple[str, ...] = ()  # optional allow-list of source keys (empty = any source whose flags allow it)
    max_input_chars: int = Field(4000, ge=200)  # body text cap per call


class AISettings(_Strict):
    capabilities: AICapabilities = AICapabilities()
    selection: AISelection = AISelection()
    request_timeout_seconds: float = Field(30.0, gt=0)
    max_retries: int = Field(1, ge=0, le=3)  # SDK retries for transient errors; validation retries are separate (one)
    provider: Literal["anthropic_api"] = "anthropic_api"
    embedding_provider: Literal["openai_embeddings_api"] = "openai_embeddings_api"
    triage_model: str = "claude-haiku-5-5"
    enrich_model: str = "claude-haiku-5-5"
    digest_model: str = "claude-sonnet-5-5"
    embedding_model: str = "text-embedding-3-small"
    region: str = "global"
    customer_endpoint: str | None = None  # customer-hosted endpoint: design only (ADR-010 §6)
    daily_cap_usd: float = Field(5.0, ge=0)
    expected_daily_usd: float = Field(2.0, ge=0)  # spend alarm at 2x (NFR-09)
    entity_masking: bool = False  # NFR-15
    anthropic_secret_name: str = "ANTHROPIC_API_KEY"
    openai_secret_name: str = "OPENAI_API_KEY"


class SmtpSettings(_Strict):
    host: str | None = None  # None = email disabled (in-app only)
    port: int = 25
    starttls: bool = False
    username: str | None = None
    password_secret_name: str = "SMTP_PASSWORD"
    from_addr: str = "newsmon@localhost"


class FetchSettings(_Strict):
    user_agent: str = "newsmon/0.1 (foreign-news desk monitor; contact: operator@localhost)"
    min_poll_seconds: int = Field(300, ge=300)  # NFR-03 floor; cannot be configured lower
    default_poll_seconds: int = Field(600, ge=300)
    max_bytes: int = 10 * 1024 * 1024
    timeout_seconds: float = 30.0
    robots_cache_hours: int = 24


class InboxSettings(_Strict):
    scan_seconds: int = Field(10, ge=1)  # V1-06
    max_file_bytes: int = 20 * 1024 * 1024


class BackupSettings(_Strict):
    keep_daily: int = Field(14, ge=1)
    copy_to: str | None = None


class Settings(_Strict):
    workspace_name: str = "default"
    use_context: Literal["private", "internal"] = "private"
    deployment_model: Literal["CH", "MP", "SaaS"] = "CH"
    timezone: str = "Asia/Seoul"  # display only; storage is UTC
    auth_mode: Literal["local", "static_users"] = "local"
    desk_editor: str = Field("local", min_length=1, max_length=40)  # recorded on verdicts while there is no login
    bind_host: str = "127.0.0.1"
    bind_port: int = 8765
    allowed_recipient_domains: tuple[str, ...] = ("internal",)
    ai: AISettings = AISettings()
    smtp: SmtpSettings = SmtpSettings()
    fetch: FetchSettings = FetchSettings()
    inbox: InboxSettings = InboxSettings()
    backup: BackupSettings = BackupSettings()

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"unknown time zone {v!r}") from None
        return v

    @field_validator("allowed_recipient_domains", mode="before")
    @classmethod
    def _lower(cls, v):
        return tuple(str(d).lower().lstrip("@") for d in (v or ()))


class Paths(_Strict):
    """All state paths. Nothing is written outside `data_dir` (NFR-20)."""

    config_dir: Path | None
    data_dir: Path
    db_path: Path

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"


class AppConfig(_Strict):
    settings: Settings
    paths: Paths
