"""The migration must be reversible: upgrade -> downgrade -> upgrade (plan sec.7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_downgrade_upgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    url = f"sqlite:///{tmp_path}/m.db"
    monkeypatch.setenv("QUARTERMASTER_DB_URL", url)
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "head")
    assert {"budget", "snipe"} <= _tables(url)

    command.downgrade(cfg, "base")
    assert "snipe" not in _tables(url)

    command.upgrade(cfg, "head")  # reversible roundtrip
    assert {"budget", "snipe"} <= _tables(url)
