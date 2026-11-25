"""Ports (ADR-009 #2): the interfaces domain and pipeline code depend on. Adapters live elsewhere.

Domain and pipeline modules import only these protocols, never sqlite3 / httpx / anthropic / smtplib (NFR-21).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from newsmon.domain.models import ConnectorHealth, NormalisedItem, PollResult, RawUnit


# --- Clock ------------------------------------------------------------------------------------------------------
@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime:
        """Current time, timezone-aware UTC."""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


# --- Connectors and fetching --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FetchResponse:
    status: int | None
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)
    error_class: str | None = None  # an ErrorClass value when the fetch failed before a usable response
    error_detail: str | None = None
    final_url: str | None = None


@runtime_checkable
class HttpFetcher(Protocol):
    def get(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> FetchResponse: ...


@runtime_checkable
class Connector(Protocol):
    kind: str

    def poll(self, cursor: str | None) -> PollResult: ...

    def parse(self, raw: RawUnit) -> list[NormalisedItem]: ...

    def health(self) -> ConnectorHealth: ...


# --- Storage and search --------------------------------------------------------------------------------------------
@runtime_checkable
class Repository(Protocol):
    """Marker protocol: concrete repositories under repo/ own all SQL and inject workspace_id (NFR-22, NFR-23)."""

    workspace_id: int


# --- AI ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class AIResult:
    output: Any
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    provider: str = ""
    endpoint_kind: str = "hosted"


class AIUnavailable(RuntimeError):
    """No provider configured, provider down, or spend cap reached. Callers take the O1 path."""


class AIRequestError(RuntimeError):
    """A non-transient provider error (bad request, auth, refusal, truncated output). `cost_usd` carries what the
    failed call was billed, so the spend ledger stays complete."""

    def __init__(self, message: str, cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.cost_usd = cost_usd


@runtime_checkable
class AIProvider(Protocol):
    name: str
    endpoint_kind: str  # 'hosted' | 'customer_hosted' | 'none'

    def complete_json(self, *, task: str, system: str, user: str, schema: Mapping[str, Any], model: str,
                      fields_sent: Sequence[str]) -> AIResult:
        """One tool-less, schema-constrained call. Never accepts a tools argument (NFR-08)."""

    def embed(self, texts: Sequence[str], *, model: str) -> AIResult: ...


@runtime_checkable
class AIStatus(Protocol):
    def header_label(self) -> str:
        """'AI: 꺼짐' (not configured), 'AI: 중단' (configured but failing or capped), or 'AI: 켜짐'."""


# --- Secrets -------------------------------------------------------------------------------------------------------
# Delivery (Notifier) and authentication (AuthProvider) ports are deferred with their features; see PROGRESS.md.
@runtime_checkable
class SecretStore(Protocol):
    def get(self, name: str, workspace_id: int = 1) -> str | None: ...

    def owner(self, name: str) -> str:
        """'customer' or 'provider' (ADR-010 §5)."""

    def values(self) -> Iterable[str]:
        """Every configured secret value, for log redaction only."""

