"""Shared fixtures: a fresh in-memory DB with a seeded budget, and an AUTOUSE
network-egress backstop so a stray test does not reach eBay / Gixen / SerpApi / a classifieds
inbox over the standard TCP connect + DNS paths (connect, connect_ex, create_connection,
getaddrinfo). respx is the PRIMARY control for HTTP clients; this is the backstop, not the whole
guard. Only loopback is allowed -- SQLite (memory + file) uses no socket, so DB fixtures are
unaffected.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from quartermaster.db import Base, make_engine, make_session_factory
from quartermaster.models import Budget

CAP_CENTS = 100_000

_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


class NetworkBlocked(RuntimeError):
    """Raised when a test attempts to egress to a non-loopback host."""


def _host(address: object) -> str:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return str(address)


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block outbound sockets in every test across the standard TCP connect + DNS paths;
    loopback is allowed through (respx remains the primary HTTP control)."""
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create = socket.create_connection
    real_getaddrinfo = socket.getaddrinfo

    def _check(host: str) -> None:
        if host not in _ALLOWED_HOSTS:
            raise NetworkBlocked(f"egress to {host!r} blocked in tests")

    def guard_connect(self: socket.socket, address: object) -> None:
        _check(_host(address))
        real_connect(self, address)  # type: ignore[arg-type]

    def guard_connect_ex(self: socket.socket, address: object) -> int:
        _check(_host(address))
        return real_connect_ex(self, address)  # type: ignore[arg-type]

    def guard_create(address: object, *args: object, **kwargs: object) -> socket.socket:
        _check(_host(address))
        return real_create(address, *args, **kwargs)  # type: ignore[arg-type]

    def guard_getaddrinfo(host: object, *args: object, **kwargs: object) -> object:
        _check(str(host))
        return real_getaddrinfo(host, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guard_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guard_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guard_create)
    monkeypatch.setattr(socket, "getaddrinfo", guard_getaddrinfo)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        s.add(Budget(id=1, cap_cents=CAP_CENTS, committed_cents=0))
        s.flush()
        yield s
