"""CLI smoke test: `python -m quartermaster` runs the funnel and prints a digest. Forced
deterministic (no Anthropic key) and run from an empty cwd so no local `.env` leaks a key in."""

from __future__ import annotations

from pathlib import Path

import pytest

from quartermaster.__main__ import main


def _isolate(monkeypatch: pytest.MonkeyPatch, cwd: Path) -> None:
    monkeypatch.delenv("QM_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(cwd)  # no .env here -> Settings finds no key


def test_main_empty_prints_empty_digest(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate(monkeypatch, tmp_path)
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "QUARTERMASTER digest" in out
    assert "(no listings surfaced)" in out


def test_main_renders_a_fixture_listing(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate(monkeypatch, tmp_path)
    (tmp_path / "corsair.txt").write_text(
        "Corsair 2x32GB DDR4-3200 SO-DIMM EUR 120", encoding="utf-8"
    )
    assert main(["corsair.txt"]) == 0
    out = capsys.readouterr().out
    assert "landed EUR 120.00" in out
