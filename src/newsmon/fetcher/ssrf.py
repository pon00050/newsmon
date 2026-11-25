"""Connect-time SSRF policy (T-11, FR-02(d), NFR-06).

A destination is allowed only if every address the name resolves to is a global unicast address. Loopback, private,
link-local (incl. 169.254.169.254 metadata), CGNAT, multicast, reserved, unspecified, ULA and IPv4-mapped forms of any of
these are refused. The fetcher connects to the vetted address itself, so a second DNS answer cannot swap it
(DNS rebinding).

`SsrfPolicy.allow_loopback_ports` exists only so tests can reach the loopback fixture server. Production builds the
policy with no arguments; the settings schema has no key for it (TS-SEC-10).
"""
from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass, field

Resolver = Callable[[str, int], list[str]]


class SsrfBlocked(Exception):
    pass


def system_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def _legacy_ipv4(host: str) -> str | None:
    """Decimal / hex / octal / short IPv4 forms ('2130706433', '0x7f.1') that resolvers accept as addresses.
    Parsed locally so they are vetted without a DNS lookup."""
    if not host or not all(c in "0123456789abcdefxABCDEFX." for c in host) or not host[0].isdigit():
        return None
    try:
        return socket.inet_ntoa(socket.inet_aton(host))
    except OSError:
        return None


_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_NAT64_LOCAL = ipaddress.ip_network("64:ff9b:1::/48")


def _embedded_ipv4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """IPv4-mapped, IPv4-compatible (::a.b.c.d), NAT64, 6to4 and Teredo addresses reach an IPv4 host: vet that host."""
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in _NAT64 or ip in _NAT64_LOCAL:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip.teredo is not None:
        return ip.teredo[1]
    if int(ip) >> 32 == 0 and int(ip) > 1:  # ::a.b.c.d (deprecated IPv4-compatible); ::1 / :: handled as themselves
        return ipaddress.IPv4Address(int(ip))
    return None


@dataclass(frozen=True)
class SsrfPolicy:
    allow_loopback_ports: frozenset[int] = field(default_factory=frozenset)

    def check_ip(self, ip_text: str, port: int) -> None:
        ip = ipaddress.ip_address(ip_text.split("%")[0])
        if isinstance(ip, ipaddress.IPv6Address):
            embedded = _embedded_ipv4(ip)
            if embedded is not None:
                ip = embedded
        if ip.is_loopback and port in self.allow_loopback_ports:
            return
        if not ip.is_global or ip.is_multicast:
            raise SsrfBlocked(f"refused non-global address {ip}")

    def vet(self, host: str, port: int, resolver: Resolver = system_resolver) -> str:
        """Resolve once, refuse if any answer is not allowed, return the address to connect to."""
        try:
            literal = ipaddress.ip_address(host.strip("[]"))
            addrs = [str(literal)]
        except ValueError:
            legacy = _legacy_ipv4(host)
            addrs = [legacy] if legacy else resolver(host, port)
        if not addrs:
            raise SsrfBlocked(f"no address for {host}")
        for a in addrs:
            self.check_ip(a, port)
        return addrs[0]
