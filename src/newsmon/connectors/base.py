"""Connector contract helpers and the retry policy (T-14; FR-03, FR-27).

- Every attempt yields one PollResult, and the runtime writes one `fetch_run` row per attempt (FR-03(a)(b)).
- timeout, 5xx and 429 are retried with backoff, at most 3 attempts; 4xx, parse, robots, ssrf and io are not.
- A connector never raises on remote failure: `guarded()` turns any exception into `error:io` (FR-27(c)).
"""
from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from datetime import datetime

from newsmon.domain.enums import ErrorClass, PollStatus
from newsmon.domain.models import PollResult, RawUnit

RETRYABLE = {ErrorClass.TIMEOUT, ErrorClass.HTTP_5XX, ErrorClass.RATE_LIMITED}
MAX_ATTEMPTS = 3


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def raw_unit(ref: str, payload: bytes, received: datetime, **kw) -> RawUnit:
    return RawUnit(raw_ref=ref, raw_sha256=sha256(payload), payload=payload, received_utc=received, **kw)


def error(cls: ErrorClass | str, detail: str = "", http_status: int | None = None) -> PollResult:
    return PollResult(status=PollStatus.ERROR, error_class=ErrorClass(cls), error_detail=detail[:500] or None,
                      http_status=http_status)


def guarded(fn: Callable[[], PollResult]) -> PollResult:
    try:
        return fn()
    except Exception as exc:  # the contract: remote failures never escape as exceptions
        return error(ErrorClass.IO, f"{exc.__class__.__name__}: {exc}")


def poll_with_retry(attempt: Callable[[], PollResult], *, sleep: Callable[[float], None] = time.sleep,
                    base_delay: float = 2.0, max_attempts: int = MAX_ATTEMPTS) -> list[PollResult]:
    """Run `attempt` until success, a non-retryable error, or `max_attempts`. Returns every attempt's result."""
    results: list[PollResult] = []
    for n in range(1, max_attempts + 1):
        r = guarded(attempt).model_copy(update={"attempts": n})
        results.append(r)
        if r.status is not PollStatus.ERROR or r.error_class not in RETRYABLE or n == max_attempts:
            break
        sleep(base_delay * (2 ** (n - 1)))
    return results
