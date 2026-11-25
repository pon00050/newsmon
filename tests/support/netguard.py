"""Network guard: tests may only reach loopback (T-04, test plan §1.2).

Patches `socket.socket.connect`/`connect_ex` and `socket.getaddrinfo`. A connection to any non-loopback address, or a
name lookup for any name other than localhost / loopback literals, is refused with `NetguardViolation` and recorded.
The autouse fixture in conftest fails the test if anything was recorded, so a caller that swallows the exception (as a
connector should, turning it into an error status) still cannot hide the attempt.

Deviation from the backlog wording ("loopback fixture ports"): every loopback port is allowed, because on Windows
`socket.socketpair()` (used by asyncio and test clients) connects to an ephemeral loopback port. The property that
matters — nothing leaves the machine — is unchanged.
"""
from __future__ import annotations

import ipaddress
import socket

_LOCAL_NAMES = {"localhost", "127.0.0.1", "::1", ""}


class NetguardViolation(ConnectionRefusedError):
    pass


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return host in _LOCAL_NAMES


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.split("%")[0])
        return True
    except ValueError:
        return False


class NetGuard:
    def __init__(self) -> None:
        self.violations: list[str] = []
        self._orig = None

    def install(self) -> "NetGuard":
        orig_connect, orig_connect_ex, orig_gai = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo
        self._orig = (orig_connect, orig_connect_ex, orig_gai)
        guard = self

        def check(addr) -> None:
            if isinstance(addr, tuple) and addr and isinstance(addr[0], str) and not _is_loopback(addr[0]):
                guard.violations.append(f"connect {addr[0]}:{addr[1] if len(addr) > 1 else ''}")
                raise NetguardViolation(f"netguard: non-loopback connect to {addr[0]} refused")

        def connect(sock, addr):
            check(addr)
            return orig_connect(sock, addr)

        def connect_ex(sock, addr):
            check(addr)
            return orig_connect_ex(sock, addr)

        def getaddrinfo(host, *args, **kw):
            h = host.decode() if isinstance(host, bytes) else (host or "")
            if not _is_loopback(h) and not _is_ip_literal(h):  # a literal needs no lookup; connect() is checked
                guard.violations.append(f"resolve {h}")
                raise NetguardViolation(f"netguard: name lookup for {h!r} refused")
            return orig_gai(host, *args, **kw)

        socket.socket.connect = connect
        socket.socket.connect_ex = connect_ex
        socket.getaddrinfo = getaddrinfo
        return self

    def uninstall(self) -> None:
        if self._orig:
            socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = self._orig
            self._orig = None

    def take(self) -> list[str]:
        v, self.violations = self.violations, []
        return v
