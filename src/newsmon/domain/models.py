"""Domain value objects (ADR-010 §1). Pure: no I/O imports (NFR-21).

`NormalisedItem` uses ninjs-style field names and carries provenance. Downstream code never branches on connector kind
(FR-27); `synthetic` is provenance only and never changes a licence decision (FR-27(d)).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from newsmon.domain.enums import (
    AIOp, AIProcessing, Display, ErrorClass, ItemType, LicenceOwner, PollStatus, PubStatus, Redistribution, Storage,
)


class LicenceFlags(BaseModel):
    """A source's licence flags (DR-1 + DR-17 + S1 additions). Defaults are the safety choice of FR-01(b), not a claim
    about any contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    storage: Storage = Storage.METADATA
    display: Display = Display.HEADLINE
    ai_processing: AIProcessing = AIProcessing.UNKNOWN
    external_ai_allowed: bool = False
    permitted_ops: frozenset[AIOp] = frozenset()
    redistribution: Redistribution = Redistribution.NONE
    training: str = "no"
    licence_owner: LicenceOwner = LicenceOwner.UNKNOWN
    allowed_contexts: frozenset[str] = frozenset({"private", "internal"})
    third_party_processors_allowed: bool = False
    authorised_users: str | None = None
    retention_days: int | None = None
    synthetic: bool = False

    @field_validator("training")
    @classmethod
    def _training_is_no(cls, v: str) -> str:
        if v != "no":
            raise ValueError("training is fixed to 'no' (NFR-19)")
        return v

    def snapshot_json(self) -> str:
        """Stable JSON snapshot stored on every article (licence_snapshot)."""
        d = self.model_dump(mode="json")
        d["permitted_ops"] = sorted(d["permitted_ops"])
        d["allowed_contexts"] = sorted(d["allowed_contexts"])
        return json.dumps(d, sort_keys=True, ensure_ascii=False)


class RawUnit(BaseModel):
    """One unit of raw input as received (a feed document, an API response, an inbox file)."""

    model_config = ConfigDict(frozen=True)

    raw_ref: str  # URL or inbox-relative path
    raw_sha256: str
    payload: bytes
    content_type: str | None = None
    received_utc: datetime
    http_status: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict)  # e.g. AP-style filename parts


class NormalisedItem(BaseModel):
    """ninjs-style item plus provenance. Produced by every connector's parse()."""

    model_config = ConfigDict(extra="forbid")

    # ninjs-style fields
    uri: str | None = None
    type: ItemType = ItemType.TEXT
    version: int = 1
    firstcreated: datetime | None = None
    versioncreated: datetime | None = None
    published_raw: str | None = None
    pubstatus: PubStatus = PubStatus.USABLE
    headline: str = ""
    slugline: str | None = None
    byline: str | None = None
    located: str | None = None
    language: str | None = None
    urgency: int | None = None
    url: str | None = None
    description_text: str | None = None
    body_text: str | None = None
    subjects: list[str] = Field(default_factory=list)
    renditions: list[dict[str, Any]] = Field(default_factory=list)
    associations: dict[str, Any] = Field(default_factory=dict)
    usageterms: str | None = None
    restrictions: str | None = None
    embargoed: datetime | None = None
    media_refs: list[str] = Field(default_factory=list)
    # provenance
    source_key: str
    connector_kind: str
    raw_ref: str
    raw_sha256: str
    parser: str
    received_utc: datetime
    synthetic: bool = False
    licence_snapshot: str


class PollResult(BaseModel):
    """Every poll has an explicit status: 'empty' is a status, never a silent null (ADR-010 §1)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: PollStatus
    error_class: ErrorClass | None = None
    error_detail: str | None = None
    http_status: int | None = None
    raw_units: list[RawUnit] = Field(default_factory=list)
    next_cursor: str | None = None
    attempts: int = 1
    bytes: int = 0
    etag: str | None = None
    last_modified: str | None = None

    @property
    def label(self) -> str:
        return f"error:{self.error_class}" if self.status is PollStatus.ERROR else str(self.status)


class ConnectorHealth(BaseModel):
    last_success_utc: datetime | None = None
    error_streak: int = 0
    last_error_class: ErrorClass | None = None


class SourceRef(BaseModel):
    """What the pipeline needs to know about a source (no SQL, no I/O)."""

    model_config = ConfigDict(frozen=True)

    source_id: int
    key: str
    name: str
    access_method: str
    is_wire: bool = False
    lang_default: str | None = None
    registrable_domain: str | None = None
    flags: LicenceFlags = LicenceFlags()
    active: bool = True
