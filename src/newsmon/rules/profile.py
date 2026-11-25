"""Monitoring profiles (T-30 essential portion; INTERFACE_SPEC §7). A profile is YAML, validated on load.

Release A: schema, validation (unknown source / entity ids rejected, AI-sourced flash rejected), weights and thresholds.
Deferred: versioned saves from the UI, the 24 h preview, alert / digest delivery (fields are accepted and kept).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Band = Literal["drop", "review", "report", "flash"]

SUPPORTED_CONDITIONS = {"source_is_wire", "urgency_lte", "topic_hit", "entity_hit", "keyword_hit",
                        "independent_sources_gte", "within_hours", "lang_in", "source_in"}
AI_FIELDS = {"ai_band", "ai_relevance", "llm_band", "ai_summary", "ai_triage"}


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Topic(_M):
    label: str
    keywords: dict[str, list[str]] = Field(default_factory=dict)  # lang -> terms
    weight: float = 1.0


class SourcePrefs(_M):
    prefer: dict[str, float] = Field(default_factory=dict)
    mute: list[str] = Field(default_factory=list)


class PriorityRule(_M):
    id: str
    when: dict[str, Any]
    band: Band

    @model_validator(mode="after")
    def _check(self):
        unknown = set(self.when) - SUPPORTED_CONDITIONS - AI_FIELDS
        if unknown:
            raise ValueError(f"rule {self.id}: unsupported condition(s) {sorted(unknown)}")
        if self.band == "flash" and set(self.when) & AI_FIELDS:
            raise ValueError(f"rule {self.id}: flash cannot be set from an AI field (FR-16(c))")
        if set(self.when) & AI_FIELDS:
            raise ValueError(f"rule {self.id}: AI fields are not available (AI layer deferred)")
        return self


class Weights(_M):
    topic_hit: float = 2.0  # per matched topic
    entity_hit: float = 2.0  # per matched watch entity
    keyword_extra: float = 0.5  # each further matched term beyond the first per topic
    wire_urgency: float = 2.0  # (9 - urgency) / 8 * weight for wire items
    independent_source: float = 0.5  # per independent source beyond the first
    recency: float = 1.0  # linear decay over recency_hours
    recency_hours: float = 24.0


class Thresholds(_M):
    review_score: float = 1.0
    report_score: float = 3.5
    independent_sources_for_report: int = 2
    spike_z: float = 2.5
    spike_min_count: int = 5
    ai_band_weight: float = 1.0


class AIProfile(_M):
    """Editorial guidance for the optional AI assessment (Release A.1). Plain configuration, no code."""
    instructions: str = ""  # free-text desk guidance, e.g. what counts as important for this desk
    relevance_targets: list[str] = Field(default_factory=list)  # organisations, industries, countries to check against
    topic_labels: list[str] = Field(default_factory=list)  # preferred topic vocabulary (defaults to topic labels)


class Profile(_M):
    key: str
    name: str = ""
    languages: list[str] = Field(default_factory=list)  # empty = all
    countries: list[str] = Field(default_factory=list)  # kept; country matching needs the gazetteer (deferred)
    topics: list[Topic] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    exclude_keywords: dict[str, list[str]] = Field(default_factory=dict)
    sources: SourcePrefs = SourcePrefs()
    priority_rules: list[PriorityRule] = Field(default_factory=list)
    weights: Weights = Weights()
    thresholds: Thresholds = Thresholds()
    alerts: dict[str, Any] = Field(default_factory=dict)  # delivery deferred
    schedules: list[dict[str, Any]] = Field(default_factory=list)  # digests deferred
    review_required: bool = True
    ai: AIProfile = AIProfile()

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not v.replace("_", "").isalnum():
            raise ValueError("profile key must be alphanumeric/underscore")
        return v


class ProfileError(ValueError):
    pass


def validate_profile(data: dict, *, source_keys: set[str], entity_ids: set[str]) -> Profile:
    try:
        p = Profile.model_validate(data)
    except Exception as exc:
        raise ProfileError(str(exc)) from None
    referenced = set(p.sources.prefer) | set(p.sources.mute)
    for r in p.priority_rules:
        referenced |= set(r.when.get("source_in", []) or [])
    bad_sources = referenced - source_keys
    if bad_sources:
        raise ProfileError(f"profile {p.key}: unknown source id(s) {sorted(bad_sources)}")
    bad_entities = set(p.entities) - entity_ids
    if bad_entities:
        raise ProfileError(f"profile {p.key}: unknown entity id(s) {sorted(bad_entities)}")
    return p
