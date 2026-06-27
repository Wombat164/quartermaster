"""Structured logging with default-deny secret redaction (plan sec.4 / sec.6 / sec.8).

structlog is configured once at startup. A redaction processor masks any field whose KEY looks like
a secret (api_key, token, password, secret, ...) so a secret can never reach a sink, even if a
caller accidentally puts it in an event. Born redacted, not retrofitted -- wired before the first
secret-bearing client logs anything.
"""

from __future__ import annotations

import logging
from typing import cast

import structlog
from structlog.typing import EventDict, FilteringBoundLogger, WrappedLogger

from .config import Settings

# Substrings that mark a field's KEY as secret-bearing -> its value is masked, whatever it holds.
_SECRET_KEY_MARKERS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "passwd",
    "authorization",
    "ping_url",
    "cookie",
)
_MASK = "***REDACTED***"


def _redact_secrets(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    for key in list(event_dict):
        if any(marker in key.lower() for marker in _SECRET_KEY_MARKERS):
            event_dict[key] = _MASK
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure structlog process-wide: redaction, then level filter, timestamp, JSON render."""
    level = logging.getLevelNamesMapping().get(settings.log_level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _redact_secrets,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    """A bound logger. Call ``configure_logging`` once at startup first."""
    return cast(FilteringBoundLogger, structlog.get_logger(name))
