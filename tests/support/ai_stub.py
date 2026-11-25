"""Deterministic AI stub implementing the AIProvider port (T-04 part built with Release A.1).

Records every call (task, model, fields sent, the full user message and schema), returns scripted outputs, raises
scripted AIUnavailable outages, and reports a scripted cost per call. Never touches the network.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from newsmon.domain.ports import AIResult, AIUnavailable


@dataclass
class StubCall:
    task: str
    model: str
    fields_sent: list[str]
    system: str
    user: str
    schema: dict


def default_output(schema: Mapping[str, Any], user: str) -> dict:
    props = schema.get("properties", {})
    out = {"relevance_band": "review", "importance": "medium", "topics": ["국제"], "relevant_to": [],
           "rationale_ko": "데스크가 확인할 만한 국제 기사입니다.", "source_language": "en", "injection_suspected": False,
           "injection_note": ""}
    if "headline_ko" in props:
        out["headline_ko"] = "합성 기사 제목 번역"
    if "summary_ko" in props:
        out["summary_ko"] = "기사의 핵심 내용을 한국어로 요약했습니다. 원문에 없는 사실은 넣지 않았습니다."
    return out


@dataclass
class AIStub:
    name: str = "stub"
    endpoint_kind: str = "hosted"
    cost_per_call: float = 0.0005
    outputs: list[Any] = field(default_factory=list)  # consumed in order; dicts are merged over the default output
    responder: Callable[[StubCall], Any] | None = None
    down: bool = False
    calls: list[StubCall] = field(default_factory=list)

    def complete_json(self, *, task: str, system: str, user: str, schema: Mapping[str, Any], model: str,
                      fields_sent: Sequence[str]) -> AIResult:
        call = StubCall(task, model, list(fields_sent), system, user, dict(schema))
        if self.down:
            raise AIUnavailable("stub outage (503)")
        self.calls.append(call)
        if self.responder is not None:
            out = self.responder(call)
        elif self.outputs:
            out = self.outputs.pop(0)
        else:
            out = {}
        if isinstance(out, dict):
            out = {**default_output(schema, user), **out}
            out = {k: v for k, v in out.items() if k in schema.get("properties", {}) or k not in ("headline_ko", "summary_ko")}
        return AIResult(output=out, model=model, input_tokens=len(user) // 3, output_tokens=200,
                        cost_usd=self.cost_per_call, latency_ms=1, provider=self.name, endpoint_kind=self.endpoint_kind)

    def embed(self, texts: Sequence[str], *, model: str) -> AIResult:
        raise AIUnavailable("stub: no embeddings")

    def bytes_sent_containing(self, needle: str) -> int:
        return sum(1 for c in self.calls if needle in c.user)
