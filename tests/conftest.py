"""Shared fixtures: a fresh in-memory DB with a seeded budget, and an AUTOUSE
network-egress blocker so NO test can ever reach eBay / Gixen / SerpApi / a classifieds
inbox or place a real bid (plan: respx + an autouse egress blocker). Only loopback is
allowed -- SQLite (memory + file) uses no socket, so the DB fixtures are unaffected.
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
    """Hard-block outbound sockets in every test; loopback is allowed through."""
    real_connect = socket.socket.connect
    real_create = socket.create_connection

    def guard_connect(self: socket.socket, address: object) -> None:
        if _host(address) not in _ALLOWED_HOSTS:
            raise NetworkBlocked(f"egress to {_host(address)!r} blocked in tests")
        real_connect(self, address)  # type: ignore[arg-type]

    def guard_create(address: object, *args: object, **kwargs: object) -> socket.socket:
        if _host(address) not in _ALLOWED_HOSTS:
            raise NetworkBlocked(f"egress to {_host(address)!r} blocked in tests")
        return real_create(address, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guard_connect)
    monkeypatch.setattr(socket, "create_connection", guard_create)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        s.add(Budget(id=1, cap_cents=CAP_CENTS, committed_cents=0))
        s.flush()
        yield s
