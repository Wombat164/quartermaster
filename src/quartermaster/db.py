"""Persistence foundation: declarative Base, a WAL-tuned SQLite engine, a session
factory, and a UTC-enforcing DateTime type (plan: tz-aware UTC everywhere).

SQLite is single-writer; WAL + busy_timeout let readers proceed while one writer holds
the write lock. Money/safety code runs inside a single transaction per operation.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import DateTime, Engine, TypeDecorator, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator[dt.datetime]):
    """Store tz-aware UTC; return tz-aware UTC. SQLite has no native tz, so we attach
    UTC on the way out instead of leaking a naive datetime into money/time logic."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: dt.datetime | None, dialect: Any) -> dt.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("refusing to store a naive datetime; use UTC-aware")
        return value.astimezone(dt.UTC)

    def process_result_value(self, value: dt.datetime | None, dialect: Any) -> dt.datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value.astimezone(dt.UTC)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _on_connect(dbapi_conn: Any, _record: Any) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def make_engine(url: str = "sqlite:///quartermaster.db") -> Engine:
    engine = create_engine(url)
    event.listen(engine, "connect", _on_connect)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
