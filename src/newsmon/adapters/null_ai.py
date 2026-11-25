"""Null AI adapters: the O1 default. No provider is configured, so every AI call is refused and the header reads
'AI: 꺼짐' (spec 12 §13)."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from newsmon.domain.ports import AIResult, AIUnavailable

AI_OFF = "AI: 꺼짐"
AI_DOWN = "AI: 중단"
AI_ON = "AI: 켜짐"


class NullAIProvider:
    name = "none"
    endpoint_kind = "none"

    def complete_json(self, *, task: str, system: str, user: str, schema: Mapping[str, Any], model: str,
                      fields_sent: Sequence[str]) -> AIResult:
        raise AIUnavailable("no AI provider configured (O1)")

    def embed(self, texts: Sequence[str], *, model: str) -> AIResult:
        raise AIUnavailable("no AI provider configured (O1)")


class NullAIStatus:
    def header_label(self) -> str:
        return AI_OFF
