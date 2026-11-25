"""JSON-lines logging with correlation ids and secret redaction (T-09 essential portion; NFR-07, NFR-13).

Each record is one JSON object: ts, level, event, correlation_id, plus structured fields such as source, stage and
error_class, so a failure can be located without reading other components. Policy: ids, hashes and counts are logged;
source text never is. Every configured secret value is replaced by [REDACTED] in messages and fields.
"""
from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")
LOGGER_NAME = "newsmon"


def new_correlation_id(prefix: str = "c") -> str:
    cid = f"{prefix}-{uuid.uuid4().hex[:12]}"
    correlation_id.set(cid)
    return cid


class RedactionFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self.secrets = [s for s in secrets if s and len(s) >= 6]

    def _scrub(self, v):
        if isinstance(v, str):
            for s in self.secrets:
                v = v.replace(s, "[REDACTED]")
            return v
        if isinstance(v, dict):
            return {k: self._scrub(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [self._scrub(x) for x in v]
        return v

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._scrub(record.getMessage())
        record.args = ()
        if hasattr(record, "fields"):
            record.fields = self._scrub(record.fields)
        if record.exc_info:
            record.exc_text = self._scrub(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        d = {"ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
             "level": record.levelname.lower(), "event": record.getMessage(),
             "correlation_id": getattr(record, "correlation_id", None) or correlation_id.get()}
        d.update(getattr(record, "fields", {}) or {})
        if record.exc_text:
            d["exception"] = record.exc_text
        return json.dumps(d, ensure_ascii=False, default=str)


def setup(secrets: Iterable[str] = (), *, stream=None, level: int = logging.INFO) -> logging.Logger:
    log = logging.getLogger(LOGGER_NAME)
    log.handlers.clear()
    h = logging.StreamHandler(stream or sys.stderr)
    h.setFormatter(JsonFormatter())
    h.addFilter(RedactionFilter(secrets))
    log.addHandler(h)
    log.setLevel(level)
    log.propagate = False
    return log


def event(name: str, level: int = logging.INFO, **fields) -> None:
    logging.getLogger(LOGGER_NAME).log(level, name, extra={"fields": fields})
