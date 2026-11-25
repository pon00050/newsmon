"""Frozen, advanceable clock implementing the Clock port (T-04)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


class FrozenClock:
    def __init__(self, start: datetime | str = "2026-11-25T00:00:00+00:00") -> None:
        self._now = datetime.fromisoformat(start) if isinstance(start, str) else start
        if self._now.tzinfo is None:
            raise ValueError("FrozenClock needs an aware datetime")
        self._now = self._now.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float = 0, **kw) -> datetime:
        self._now += timedelta(seconds=seconds, **kw)
        return self._now

    def set(self, when: datetime | str) -> None:
        self._now = (datetime.fromisoformat(when) if isinstance(when, str) else when).astimezone(timezone.utc)
