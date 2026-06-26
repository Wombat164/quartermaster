"""The autouse egress blocker must stop real network egress and leave loopback to the
OS's own errors (so future respx mocks + local stubs still work)."""

from __future__ import annotations

import socket

import pytest

from conftest import NetworkBlocked


def test_external_egress_is_blocked() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkBlocked):
            s.connect(("example.com", 80))
    finally:
        s.close()


def test_loopback_passes_the_guard() -> None:
    # The guard ALLOWS loopback; the OS then refuses a closed port -- NOT NetworkBlocked.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    try:
        with pytest.raises(OSError) as exc:
            s.connect(("127.0.0.1", 1))
        assert not isinstance(exc.value, NetworkBlocked)
    finally:
        s.close()
