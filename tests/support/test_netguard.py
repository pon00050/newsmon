"""TS-HAR-04 (T-04): known-answer controls for the instrument itself."""
import socket

import httpx
import pytest

from tests.support.fixture_server import Resp
from tests.support.netguard import NetGuard, NetguardViolation

pytestmark = pytest.mark.support


@pytest.mark.netguard_expected
def test_non_loopback_ip_refused(netguard):
    s = socket.socket()
    try:
        with pytest.raises(NetguardViolation):
            s.connect(("192.0.2.1", 80))  # TEST-NET-1: must never be attempted
    finally:
        s.close()
    assert netguard.take() == ["connect 192.0.2.1:80"]


@pytest.mark.netguard_expected
def test_ai_host_name_refused(netguard):
    with pytest.raises(NetguardViolation):
        socket.getaddrinfo("api.anthropic.com", 443)
    with pytest.raises(httpx.ConnectError):
        httpx.get("https://api.openai.com/v1/models", timeout=2)
    taken = netguard.take()
    assert "resolve api.anthropic.com" in taken and "resolve api.openai.com" in taken


def test_loopback_fixture_port_allowed(fixture_server, netguard):
    url = fixture_server.route("/ok", Resp(body=b"fine"))
    assert httpx.get(url).content == b"fine"
    assert netguard.violations == []


def test_swallowed_attempt_still_recorded():
    g = NetGuard().install()
    try:
        try:
            socket.create_connection(("198.51.100.7", 443), timeout=1)
        except OSError:
            pass  # a connector turning the failure into a status must not hide the attempt
    finally:
        g.uninstall()
    assert g.take() == ["connect 198.51.100.7:443"]


def test_ai_keys_unset(monkeypatch):
    import os
    assert "ANTHROPIC_API_KEY" not in os.environ and "OPENAI_API_KEY" not in os.environ
