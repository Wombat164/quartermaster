"""ORM models: the singleton Budget and the Snipe row.

Money is stored as integer CENTS (never float -- plan antipattern). Source is set once
at ingest and is immutable (boundary B1's persistent side). Idempotency is enforced by
UNIQUE(account, ebay_item_id, snapshot_hash) (plan sec.7).
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, validates

from .db import Base, UTCDateTime, utcnow
from .fsm import State


class Source(StrEnum):
    EBAY_API = "ebay_api"
    CLASSIFIEDS_EMAIL = "classifieds_email"


class Budget(Base):
    __tablename__ = "budget"

    id: Mapped[int] = mapped_column(primary_key=True)
    cap_cents: Mapped[int]
    committed_cents: Mapped[int] = mapped_column(default=0)

    __table_args__ = (
        CheckConstraint("cap_cents >= 0", name="ck_budget_cap_nonneg"),
        CheckConstraint("committed_cents >= 0", name="ck_budget_committed_nonneg"),
        CheckConstraint("committed_cents <= cap_cents", name="ck_budget_committed_le_cap"),
    )


class Snipe(Base):
    __tablename__ = "snipe"

    id: Mapped[int] = mapped_column(primary_key=True)
    account: Mapped[str]
    ebay_item_id: Mapped[str]
    snapshot_hash: Mapped[str]
    source: Mapped[Source]
    state: Mapped[State] = mapped_column(default=State.PENDING)
    reserved_cents: Mapped[int]  # EUR-equivalent max-bid held against the budget
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("account", "ebay_item_id", "snapshot_hash", name="uq_snipe_idem"),
        CheckConstraint("reserved_cents >= 0", name="ck_snipe_reserved_nonneg"),
    )

    @validates("source")
    def _immutable_source(self, _key: str, value: Any) -> Any:
        existing = getattr(self, "source", None)
        if existing is not None and existing != value:
            raise ValueError("source is immutable -- set once at ingest (boundary B1)")
        return value
