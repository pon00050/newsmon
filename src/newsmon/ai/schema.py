"""The one structured assessment per article (Release A.1; FR-11/FR-12 subset, R7 schema lessons).

One call returns related assessments together: relevance band, editorial importance, topics, relevance to configured
targets, a short editorial rationale, and, only where the source's licence permits the op, a Korean headline
(translate) and a Korean summary (summarise). Bands, never fine scores (R7: single scores drift 35-62 on repeats).

Three validation layers (FR-13): the API's JSON-schema constraint, Pydantic, and semantic checks (Hangul ratio for
Korean fields, numbers in the summary must occur in the source).
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SCHEMA_VERSION = "assess-1"
AIBand = Literal["drop", "review", "report"]  # the model can never produce `flash` (FR-11)


class Relevance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str = Field(max_length=120)
    reason: str = Field(max_length=300)


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relevance_band: AIBand
    importance: Literal["low", "medium", "high"]
    topics: list[str] = Field(default_factory=list, max_length=5)
    relevant_to: list[Relevance] = Field(default_factory=list, max_length=8)
    rationale_ko: str = Field(max_length=400)
    source_language: str = Field(max_length=10)
    headline_ko: str | None = Field(default=None, max_length=200)
    summary_ko: str | None = Field(default=None, max_length=900)
    injection_suspected: bool = False
    injection_note: str = Field(default="", max_length=300)


def json_schema(*, translate: bool, summarise: bool) -> dict:
    """JSON Schema sent as output_config.format. Korean headline/summary are requested only when the op is permitted,
    so nothing the licence forbids is even asked for."""
    props = {
        "relevance_band": {"type": "string", "enum": ["drop", "review", "report"]},
        "importance": {"type": "string", "enum": ["low", "medium", "high"]},
        "topics": {"type": "array", "items": {"type": "string"}},
        "relevant_to": {"type": "array", "items": {
            "type": "object", "properties": {"target": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["target", "reason"], "additionalProperties": False}},
        "rationale_ko": {"type": "string"},
        "source_language": {"type": "string"},
        "injection_suspected": {"type": "boolean"},
        "injection_note": {"type": "string"},
    }
    if translate:
        props["headline_ko"] = {"type": "string"}
    if summarise:
        props["summary_ko"] = {"type": "string"}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_HANGUL = re.compile(r"[가-힯ᄀ-ᇿ㄰-㆏]")
_LETTER = re.compile(r"[^\W\d_]")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def hangul_ratio(text: str) -> float:
    letters = _LETTER.findall(text or "")
    return (len(_HANGUL.findall(text or "")) / len(letters)) if letters else 0.0


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text or "")}


class SemanticError(ValueError):
    pass


def validate(raw: dict | str, *, source_text: str, translate: bool, summarise: bool) -> Assessment:
    """Pydantic + semantic checks. Raises ValidationError or SemanticError with a short reason."""
    a = Assessment.model_validate_json(raw) if isinstance(raw, str) else Assessment.model_validate(raw)
    if translate and not a.headline_ko:
        raise SemanticError("headline_ko missing")
    if summarise and not a.summary_ko:
        raise SemanticError("summary_ko missing")
    from newsmon.licence.policy import inert  # judge the prose, not markup or URLs the model may have added
    for name in ("rationale_ko", "headline_ko", "summary_ko"):
        v = inert(getattr(a, name))
        if v and hangul_ratio(v) < 0.5:
            raise SemanticError(f"{name} is not Korean (Hangul ratio {hangul_ratio(v):.2f})")
    if a.summary_ko:
        missing = {n for n in _numbers(a.summary_ko) if len(n) > 1} - _numbers(source_text)
        if missing:
            raise SemanticError(f"summary contains numbers not in the source: {sorted(missing)[:5]}")
    return a


__all__ = ["Assessment", "SCHEMA_VERSION", "json_schema", "validate", "SemanticError", "ValidationError", "hangul_ratio"]
