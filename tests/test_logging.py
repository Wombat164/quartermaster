"""Structured logging: the redaction processor masks secret-keyed fields, and a configured
logger never emits a secret value."""

from __future__ import annotations

import pytest

from quartermaster.config import Settings
from quartermaster.logging import _redact_secrets, configure_logging, get_logger


def test_redacts_secret_keyed_fields() -> None:
    out = _redact_secrets(None, "info", {"serpapi_api_key": "sk-LIVE", "query": "DDR4"})
    assert out["serpapi_api_key"] == "***REDACTED***"
    assert out["query"] == "DDR4"


def test_redacts_every_marker() -> None:
    ev = {
        "api_key": "a",
        "auth_token": "b",
        "password": "c",
        "healthchecks_ping_url": "d",
        "Authorization": "e",  # case-insensitive
        "count": 3,
    }
    out = _redact_secrets(None, "info", dict(ev))
    assert out["api_key"] == "***REDACTED***"
    assert out["auth_token"] == "***REDACTED***"
    assert out["password"] == "***REDACTED***"
    assert out["healthchecks_ping_url"] == "***REDACTED***"
    assert out["Authorization"] == "***REDACTED***"
    assert out["count"] == 3


def test_configured_logger_never_emits_a_secret(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(Settings(log_level="INFO"))
    get_logger("test").info("fetching comps", serpapi_api_key="sk-SUPERSECRET", query="DDR4")
    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert "sk-SUPERSECRET" not in blob
    assert "***REDACTED***" in blob
