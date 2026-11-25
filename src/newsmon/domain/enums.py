"""Closed vocabularies shared by every layer. Values match the CHECK constraints of the schema (11 §5)."""
from __future__ import annotations

from enum import StrEnum


class Storage(StrEnum):
    NONE = "none"
    METADATA = "metadata"
    TRANSIENT = "transient"
    FULL = "full"


class Display(StrEnum):
    NONE = "none"
    HEADLINE = "headline"
    SNIPPET = "snippet"
    FULL = "full"

    @property
    def rank(self) -> int:
        return _DISPLAY_RANK[self]


_DISPLAY_RANK = {Display.NONE: 0, Display.HEADLINE: 1, Display.SNIPPET: 2, Display.FULL: 3}


class AIProcessing(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class Redistribution(StrEnum):
    NONE = "none"
    INTERNAL = "internal"
    EXTERNAL = "external"


class LicenceOwner(StrEnum):
    PROVIDER = "provider"
    TENANT = "tenant"
    PUBLIC_DOMAIN = "public-domain"
    UNKNOWN = "unknown"


class AIOp(StrEnum):
    CLASSIFY = "classify"
    SUMMARISE = "summarise"
    TRANSLATE = "translate"
    EMBED = "embed"


class AccessMethod(StrEnum):
    FEED = "feed"
    HTTP_API = "http_api"
    DIRECTORY = "directory"
    WIRE_API = "wire_api"
    NRCS_INBOUND = "nrcs_inbound"
    CHANGEDETECTION = "changedetection"
    RSSHUB = "rsshub"


# Designed but not implemented in the MVP (ADR-010 §2): activating one is refused.
UNIMPLEMENTED_ACCESS = frozenset({AccessMethod.WIRE_API, AccessMethod.NRCS_INBOUND,
                                  AccessMethod.CHANGEDETECTION, AccessMethod.RSSHUB})


class PollStatus(StrEnum):
    OK = "ok"
    NOT_MODIFIED = "not_modified"
    EMPTY = "empty"
    ERROR = "error"


class ErrorClass(StrEnum):
    TIMEOUT = "timeout"
    HTTP_4XX = "http_4xx"
    HTTP_5XX = "http_5xx"
    PARSE = "parse"
    RATE_LIMITED = "rate_limited"
    ROBOTS = "robots"
    SSRF_BLOCKED = "ssrf_blocked"
    IO = "io"
    QUARANTINE = "quarantine"


class Band(StrEnum):
    DROP = "drop"
    REVIEW = "review"
    REPORT = "report"
    FLASH = "flash"

    @property
    def rank(self) -> int:
        return _BAND_RANK[self]


_BAND_RANK = {Band.DROP: 0, Band.REVIEW: 1, Band.REPORT: 2, Band.FLASH: 3}


class ItemType(StrEnum):
    TEXT = "text"
    VIDEO = "video"
    AUDIO = "audio"
    PICTURE = "picture"


class PubStatus(StrEnum):
    USABLE = "usable"
    WITHHELD = "withheld"
    CANCELED = "canceled"


class Role(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"
