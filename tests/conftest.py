"""Shared fixtures: a fresh in-memory DB with a seeded budget per test."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from quartermaster.db import Base, make_engine, make_session_factory
from quartermaster.models import Budget

CAP_CENTS = 100_000


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        s.add(Budget(id=1, cap_cents=CAP_CENTS, committed_cents=0))
        s.flush()
        yield s
