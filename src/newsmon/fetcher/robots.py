"""RFC 9309 robots.txt matcher with a daily per-host cache (T-12; ported from R5's probe_sources.py).

Not urllib.robotparser: it normalises the path and mishandles rules containing '?' (ACQUISITION_METHODS §3).
- longest match wins; on a tie, Allow wins; '*' wildcard and '$' end anchor;
- 4xx for robots.txt = no rules (allow all); 5xx or unreachable = disallow all;
- rules for our product token win over '*'; the cache is re-checked after `cache_hours`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from newsmon.domain.ports import Clock, HttpFetcher, SystemClock

Rules = list[tuple[bool, str]]


def parse_robots(text: str) -> dict[str, Rules]:
    """Return {agent_token: [(allow, pattern)]}. Groups for the same agent are merged."""
    groups: dict[str, Rules] = {}
    cur: list[str] = []
    in_rules = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if in_rules:
                cur, in_rules = [], False
            cur.append(v.lower())
            groups.setdefault(v.lower(), [])
        elif k in ("allow", "disallow"):
            in_rules = True
            for a in cur:
                groups[a].append((k == "allow", v))
    return groups


def _match_len(pattern: str, path: str) -> int:
    if pattern == "":
        return -1
    rx = re.escape(pattern).replace(r"\*", ".*")
    if rx.endswith(r"\$"):
        rx = rx[:-2] + "$"
    return len(pattern) if re.match(rx, path) else -1


def is_allowed(rules: Rules, path_and_query: str) -> bool:
    best, allow = -1, True
    for a, pat in rules:
        n = _match_len(pat, path_and_query)
        if n > best or (n == best and a):
            best, allow = n, a
    return allow if best >= 0 else True


def rules_for(groups: dict[str, Rules], user_agent: str) -> Rules:
    token = user_agent.split("/", 1)[0].strip().lower()
    return groups.get(token) or groups.get("*") or []


@dataclass
class _Entry:
    groups: dict[str, Rules] | None  # None = disallow all
    fetched: datetime
    status: str


class RobotsCache:
    def __init__(self, fetcher: HttpFetcher, user_agent: str, *, clock: Clock | None = None, cache_hours: int = 24) -> None:
        self.fetcher = fetcher
        self.user_agent = user_agent
        self.clock = clock or SystemClock()
        self.ttl = timedelta(hours=cache_hours)
        self._cache: dict[str, _Entry] = {}

    def allowed(self, url: str) -> tuple[bool, str]:
        """(allowed, robots_status) for a URL; fetches robots.txt at most once per host per TTL."""
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        now = self.clock.now()
        e = self._cache.get(origin)
        if e is None or now - e.fetched >= self.ttl:
            e = self._load(origin, now)
            self._cache[origin] = e
        if e.groups is None:
            return False, e.status
        path = (p.path or "/") + (f"?{p.query}" if p.query else "")
        return is_allowed(rules_for(e.groups, self.user_agent), path), e.status

    def _load(self, origin: str, now: datetime) -> _Entry:
        r = self.fetcher.get(origin + "/robots.txt")
        if r.status == 200 and r.error_class is None:
            return _Entry(parse_robots(r.body.decode("utf-8", "replace")), now, "200")
        if r.error_class == "ssrf_blocked":
            return _Entry(None, now, "ssrf_blocked")
        if r.status is not None and 400 <= r.status < 500:
            return _Entry({}, now, str(r.status))
        return _Entry(None, now, str(r.status) if r.status else (r.error_class or "unreachable"))
