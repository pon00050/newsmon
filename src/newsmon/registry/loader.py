"""Source registry as data (T-13; FR-01, FR-30). Reads `sources.yaml` into validated `SourceSpec`s.

Defaults for missing flags are the safety choice of FR-01(b) (not a claim about any contract). Activation:
- a source whose `allowed_contexts` excludes the workspace's `use_context` is inactive (FR-01(c));
- `wire_api`, `nrcs_inbound`, `changedetection`, `rsshub`: requesting activation is refused (adapter not implemented);
- `http_api` is implemented in MVP-1 but deferred in Release A (P-011): such rows load inactive with that reason;
- a `licence_owner: tenant` source stays inactive until attested with `retention_days` set (FR-30).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from newsmon.config.loader import ConfigError, read_yaml
from newsmon.domain.enums import (
    AIOp, AIProcessing, AccessMethod, Display, LicenceOwner, Redistribution, Storage, UNIMPLEMENTED_ACCESS,
)
from newsmon.domain.models import LicenceFlags

RELEASE_A_DEFERRED = {AccessMethod.HTTP_API: "http_api connector deferred in Release A (T-16)"}
FEED_KINDS = {"feed": "rss", "directory": "directory", "http_api": "api"}


class AdapterNotImplemented(ConfigError):
    pass


class SourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    access_method: AccessMethod
    lang: str | None = None
    country: str | None = None
    is_wire: bool = False
    registrable_domain: str | None = None
    url: str | None = None  # feed / http_api endpoint
    path: str | None = None  # directory root
    poll_seconds: int | None = None
    active: bool = True
    tos_url: str | None = None
    attribution_text: str | None = None
    # licence flags (DR-1 + DR-17); defaults = FR-01(b)
    storage: Storage = Storage.METADATA
    display: Display = Display.HEADLINE
    ai_processing: AIProcessing = AIProcessing.UNKNOWN
    external_ai_allowed: bool = False
    permitted_ops: list[AIOp] = Field(default_factory=list)
    redistribution: Redistribution = Redistribution.NONE
    training: str = "no"
    licence_owner: LicenceOwner = LicenceOwner.UNKNOWN
    allowed_contexts: list[str] = Field(default_factory=lambda: ["private", "internal"])
    third_party_processors_allowed: bool = False
    authorised_users: str | None = None
    territory: str | None = None
    retention_days: int | None = None
    licence_holder: str | None = None
    agreement_ref: str | None = None
    valid_until: date | None = None
    attested_by: str | None = None
    attested_on: date | None = None
    synthetic: bool = False
    # Public redistribution (static website export). Separate from every internal permission above and denied by
    # default: collecting, storing, displaying or sending to AI never implies publishing. `metadata` publishes the link,
    # times and our own labels; `headline` also publishes the headline. Bodies and summaries are never published.
    public_redistribution: Literal["none", "metadata", "headline"] = "none"
    public_redistribution_basis: str | None = None  # the documented permission, in words (required unless none)
    public_redistribution_url: str | None = None  # where that permission is stated
    boilerplate_rules: list[str] = Field(default_factory=list)
    live_patterns: list[str] = Field(default_factory=list)
    story_key_rule: str | None = None

    @field_validator("training")
    @classmethod
    def _no_training(cls, v):
        if v != "no":
            raise ValueError("training is fixed to 'no'")
        return v

    @field_validator("allowed_contexts", mode="before")
    @classmethod
    def _ctx(cls, v):
        if isinstance(v, str):
            v = [x.strip() for x in v.split(",")]
        bad = set(v) - {"private", "internal"}
        if bad:
            raise ValueError(f"unknown context(s) {sorted(bad)}")
        return v

    @model_validator(mode="after")
    def _endpoint(self):
        if self.access_method in (AccessMethod.FEED, AccessMethod.HTTP_API) and not self.url:
            raise ValueError(f"{self.key}: url required for {self.access_method}")
        if self.access_method is AccessMethod.DIRECTORY and not self.path:
            raise ValueError(f"{self.key}: path required for a directory source")
        if self.public_redistribution != "none":
            if not (self.public_redistribution_basis or "").strip():
                raise ValueError(f"{self.key}: public_redistribution needs public_redistribution_basis")
            if self.licence_owner is LicenceOwner.TENANT:
                raise ValueError(f"{self.key}: customer-licensed (tenant) content is never publicly redistributed")
        return self

    def flags(self) -> LicenceFlags:
        return LicenceFlags(storage=self.storage, display=self.display, ai_processing=self.ai_processing,
                            external_ai_allowed=self.external_ai_allowed, permitted_ops=frozenset(self.permitted_ops),
                            redistribution=self.redistribution, licence_owner=self.licence_owner,
                            allowed_contexts=frozenset(self.allowed_contexts),
                            third_party_processors_allowed=self.third_party_processors_allowed,
                            authorised_users=self.authorised_users, retention_days=self.retention_days,
                            synthetic=self.synthetic)

    def activation(self, use_context: str, today: date) -> tuple[bool, str | None]:
        """(active, reason_if_inactive)."""
        if self.access_method in UNIMPLEMENTED_ACCESS:
            if self.active:
                raise AdapterNotImplemented(f"{self.key}: adapter not implemented ({self.access_method})")
            return False, f"adapter not implemented ({self.access_method})"
        if not self.active:
            return False, "disabled in sources.yaml"
        if self.access_method in RELEASE_A_DEFERRED:
            return False, RELEASE_A_DEFERRED[self.access_method]
        if use_context not in self.allowed_contexts:
            return False, f"not allowed in use_context={use_context}"
        if self.licence_owner is LicenceOwner.TENANT:
            if self.retention_days is None or self.attested_on is None:
                return False, "tenant source not attested (FR-30)"
        if self.valid_until is not None and today > self.valid_until:
            return False, f"licence expired on {self.valid_until} (FR-30(b))"
        return True, None


def parse_sources(data: Any) -> list[SourceSpec]:
    if data is None:
        return []
    rows = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ConfigError("sources.yaml: top level must be a mapping with a 'sources' list")
    specs, seen = [], set()
    for i, row in enumerate(rows):
        try:
            spec = SourceSpec.model_validate(row)
        except Exception as exc:
            raise ConfigError(f"sources.yaml entry {i} ({(row or {}).get('key', '?')}): {exc}") from None
        if spec.key in seen:
            raise ConfigError(f"sources.yaml: duplicate key {spec.key}")
        seen.add(spec.key)
        specs.append(spec)
    return specs


def load_sources(path: Path) -> list[SourceSpec]:
    return parse_sources(read_yaml(path)) if path.exists() else []
