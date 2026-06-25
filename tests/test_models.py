"""Model invariants: source immutability, idempotency, WAL on a file DB."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from quartermaster import snipes
from quartermaster.db import make_engine
from quartermaster.models import Snipe, Source


def test_source_is_immutable() -> None:
    s = Snipe(
        account="a", ebay_item_id="i", snapshot_hash="h",
        source=Source.EBAY_API, reserved_cents=1,
    )
    with pytest.raises(ValueError, match="immutable"):
        s.source = Source.CLASSIFIEDS_EMAIL


def test_idempotency_unique(session: Session) -> None:
    kw = dict(account="a", ebay_item_id="i", snapshot_hash="h",
              source=Source.EBAY_API, reserved_cents=100)
    snipes.create_snipe(session, **kw)  # type: ignore[arg-type]
    with pytest.raises(IntegrityError):
        snipes.create_snipe(session, **kw)  # type: ignore[arg-type]


def test_wal_enabled_on_file_db(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path}/q.db")
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
    engine.dispose()
    assert str(mode).lower() == "wal"
