"""Anthropic API adapter for the AIProvider port (Release A.1; deliverable 10 row 15; anthropic 2.14.0 as in R7).

One tool-less, schema-constrained call (`output_config.format` = JSON Schema) per request (NFR-08). Transient
failures (connection, timeout, 429, 5xx) surface as AIUnavailable so the caller degrades to O1; other API errors
surface as AIRequestError. Cost is computed from the reported token usage and the price table below.
"""
from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from typing import Any

import anthropic

from newsmon.domain.ports import AIRequestError, AIResult, AIUnavailable

# USD per million tokens (input, output), first-party API rates as published 2026-10 (claude-api reference). Unknown
# models are priced at the most expensive row so the spend cap errs on the safe side.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
FALLBACK_PRICE = (10.00, 50.00)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICES.get(model, FALLBACK_PRICE)
    return round((input_tokens * pin + output_tokens * pout) / 1_000_000, 6)


class AnthropicProvider:
    name = "anthropic_api"
    endpoint_kind = "hosted"

    def __init__(self, api_key: str, *, timeout: float = 30.0, max_retries: int = 1, effort: str = "low",
                 client: Any = None) -> None:
        self._client = client or anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)
        self.effort = effort

    def complete_json(self, *, task: str, system: str, user: str, schema: Mapping[str, Any], model: str,
                      fields_sent: Sequence[str]) -> AIResult:
        t0 = time.monotonic()
        try:
            resp = self._client.messages.create(
                model=model, max_tokens=4000, system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": dict(schema)}},
            )
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.RateLimitError,
                anthropic.InternalServerError) as exc:
            raise AIUnavailable(f"{exc.__class__.__name__}") from None
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise AIUnavailable(f"HTTP {exc.status_code}") from None
            raise AIRequestError(f"HTTP {exc.status_code}: {exc.__class__.__name__}") from None
        latency = int((time.monotonic() - t0) * 1000)
        usage = resp.usage
        tin, tout = int(usage.input_tokens or 0), int(usage.output_tokens or 0)
        billed = cost_usd(model, tin, tout)
        if resp.stop_reason == "refusal":
            raise AIRequestError("refusal", billed)
        if resp.stop_reason == "max_tokens":
            raise AIRequestError("output truncated (max_tokens)", billed)
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), None)
        if text is None:
            raise AIRequestError("no text block in response", billed)
        try:
            output = json.loads(text)
        except ValueError:
            output = text  # validation reports it; the call is still billed and recorded
        return AIResult(output=output, model=model, input_tokens=tin, output_tokens=tout,
                        cost_usd=billed, latency_ms=latency, provider=self.name,
                        endpoint_kind=self.endpoint_kind)

    def embed(self, texts: Sequence[str], *, model: str) -> AIResult:
        raise AIUnavailable("embeddings are not part of Release A.1")
