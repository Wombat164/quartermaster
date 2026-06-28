"""Config separation + secret hygiene: fail-safe defaults, no .env-example drift, and
SecretStr never leaks. These guard the public-repo security posture."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from quartermaster.config import Settings, render_env_example


def test_dry_run_defaults_true() -> None:
    # Fail-safe (plan sec.2): unconfigured runs must never arm a real action.
    assert Settings.model_fields["dry_run"].default is True


def test_env_example_in_sync_with_model() -> None:
    committed = Path(".env.example").read_text(encoding="utf-8")
    assert committed == render_env_example(), (
        ".env.example drifted from the Settings model -- regenerate it from "
        "quartermaster.config.render_env_example()"
    )


def test_secret_is_masked_and_never_leaks() -> None:
    s = Settings(serpapi_api_key=SecretStr("super-secret-value"))
    assert "super-secret-value" not in repr(s)
    assert "super-secret-value" not in str(s)
    # but the real value is still retrievable for use
    assert s.serpapi_api_key is not None
    assert s.serpapi_api_key.get_secret_value() == "super-secret-value"


def test_blank_secret_env_becomes_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # an empty / whitespace env value means 'unset' -> None, so a missing key degrades to
    # deterministic extraction instead of reaching an API as a blank credential (live-run bug).
    monkeypatch.setenv("QM_ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("QM_SERPAPI_API_KEY", "   ")
    s = Settings()
    assert s.anthropic_api_key is None
    assert s.serpapi_api_key is None
