"""HttpFetcher: the one HTTP client for every outbound fetch (T-11; deliverable 10 row 2).

- descriptive User-Agent on every request (FR-02(c));
- conditional GET with stored validators (FR-02(a));
- connect-time SSRF refusal: the host is resolved once, vetted, and the connection goes to the vetted IP, with the
  original Host header and TLS SNI kept; every redirect hop is re-vetted (FR-02(d));
- http/https only; at most 5 redirects;
- a size cap (default 10 MB) and a total time cap (default 30 s) (NFR-06);
- one in-flight request per host (FR-02(e)).

It never raises for remote failures: problems come back as `FetchResponse.error_class`.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from urllib.parse import urljoin

import httpx

from newsmon.domain.ports import FetchResponse
from newsmon.fetcher.ssrf import Resolver, SsrfBlocked, SsrfPolicy, system_resolver

MAX_REDIRECTS = 5


class HostLocks:
    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._guard = threading.Lock()

    def for_host(self, host: str) -> threading.Lock:
        with self._guard:
            return self._locks[host.lower()]


class HttpxFetcher:
    def __init__(self, *, user_agent: str, policy: SsrfPolicy | None = None, max_bytes: int = 10 * 1024 * 1024,
                 timeout: float = 30.0, resolver: Resolver = system_resolver, host_locks: HostLocks | None = None) -> None:
        self.user_agent = user_agent
        self.policy = policy or SsrfPolicy()
        self.max_bytes = max_bytes
        self.timeout = timeout
        self.resolver = resolver
        self.host_locks = host_locks or HostLocks()
        self._client = httpx.Client(follow_redirects=False, trust_env=False,
                                    timeout=httpx.Timeout(timeout), headers={"User-Agent": user_agent})

    def close(self) -> None:
        self._client.close()

    def get(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> FetchResponse:
        deadline = time.monotonic() + self.timeout
        current = url
        for _hop in range(MAX_REDIRECTS + 1):
            try:
                resp = self._one(current, etag, last_modified, deadline)
            except SsrfBlocked as exc:
                return FetchResponse(None, error_class="ssrf_blocked", error_detail=str(exc), final_url=current)
            if resp.status in (301, 302, 303, 307, 308) and resp.error_class is None:
                loc = resp.headers.get("location")
                if not loc:
                    return FetchResponse(resp.status, error_class="http_4xx", error_detail="redirect without Location")
                current = urljoin(current, loc)
                etag = last_modified = None  # validators belong to the original URL
                continue
            return resp
        return FetchResponse(None, error_class="http_4xx", error_detail="too many redirects", final_url=current)

    # -- one hop -------------------------------------------------------------------------------------------------------
    def _one(self, url: str, etag: str | None, last_modified: str | None, deadline: float) -> FetchResponse:
        u = httpx.URL(url)
        if u.scheme not in ("http", "https"):
            raise SsrfBlocked(f"scheme {u.scheme!r} refused")
        if not u.host:
            raise SsrfBlocked("no host")
        port = u.port or (443 if u.scheme == "https" else 80)
        try:
            ip = self.policy.vet(u.host, port, self.resolver)
        except SsrfBlocked:
            raise
        except (OSError, ValueError) as exc:
            return FetchResponse(None, error_class="io", error_detail=f"resolve failed: {exc.__class__.__name__}",
                                 final_url=url)
        headers = {"Host": u.netloc.decode("ascii")}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        target = u.copy_with(host=ip)
        extensions = {"sni_hostname": u.host} if u.scheme == "https" else {}
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return FetchResponse(None, error_class="timeout", error_detail="total time cap", final_url=url)
        with self.host_locks.for_host(u.host):
            try:
                req = self._client.build_request("GET", target, headers=headers, extensions=extensions,
                                                 timeout=httpx.Timeout(min(self.timeout, remaining)))
                resp = self._client.send(req, stream=True)
            except httpx.TimeoutException as exc:
                return FetchResponse(None, error_class="timeout", error_detail=exc.__class__.__name__, final_url=url)
            except (httpx.HTTPError, OSError) as exc:
                return FetchResponse(None, error_class="io", error_detail=exc.__class__.__name__, final_url=url)
            try:
                body = bytearray()
                declared = resp.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > self.max_bytes:
                    return FetchResponse(resp.status_code, error_class="io", error_detail="oversize", final_url=url)
                try:
                    for chunk in resp.iter_bytes():  # decoded: the cap also bounds decompression
                        body += chunk
                        if len(body) > self.max_bytes:
                            return FetchResponse(resp.status_code, error_class="io", error_detail="oversize",
                                                 final_url=url)
                        if time.monotonic() > deadline:
                            return FetchResponse(resp.status_code, error_class="timeout", error_detail="total time cap",
                                                 final_url=url)
                except httpx.TimeoutException as exc:
                    return FetchResponse(resp.status_code, error_class="timeout", error_detail=exc.__class__.__name__,
                                         final_url=url)
                except httpx.HTTPError as exc:
                    return FetchResponse(resp.status_code, error_class="io", error_detail=exc.__class__.__name__,
                                         final_url=url)
            finally:
                resp.close()
        status = resp.status_code
        hdrs = {k.lower(): v for k, v in resp.headers.items()}
        err = None
        if status == 429:
            err = "rate_limited"
        elif 500 <= status:
            err = "http_5xx"
        elif 400 <= status < 500:
            err = "http_4xx"
        return FetchResponse(status, bytes(body), hdrs, error_class=err, final_url=url)
