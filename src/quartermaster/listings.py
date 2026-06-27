"""Phase-1 listing record + the LLM-routing boundary (plan sec.4 boundaries B1/B2).

A ``Listing`` is a discovered item before evaluation. Its ``source`` decides whether its text may
reach an LLM: ONLY classifieds alert-email bodies are LLM-eligible; SerpApi / eBay comp data is
deterministic-only (numbers in, never prose to a model). ``assert_llm_allowed`` is the hard gate
that makes the boundary testable BEFORE any LLM path exists, so P1.3 cannot regress it.

This is a Phase-1 concept, deliberately separate from the Phase-2 eBay-bidding ``Source`` enum on
the ``Snipe`` model -- different axis, different lifecycle.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from .valuation import Currency


class ListingSource(StrEnum):
    CLASSIFIEDS_EMAIL = "classifieds_email"  # discovery; the body MAY go to the LLM (B1)
    SERPAPI_SHOPPING = "serpapi_shopping"  # price comps; deterministic-only (B2)
    EBAY = "ebay"  # deterministic-only (the Phase-2 bidding source)


# The ONLY source whose text may reach an LLM (plan boundary B1/B2). Default-deny.
_LLM_ALLOWED: frozenset[ListingSource] = frozenset({ListingSource.CLASSIFIEDS_EMAIL})


class LlmBoundaryViolation(RuntimeError):
    """Raised when deterministic-only content would be routed to an LLM."""


def llm_allowed(source: ListingSource) -> bool:
    return source in _LLM_ALLOWED


def assert_llm_allowed(source: ListingSource) -> None:
    if not llm_allowed(source):
        raise LlmBoundaryViolation(
            f"{source.value} is deterministic-only -- its content must never reach an LLM"
        )


@dataclass(frozen=True, slots=True)
class Listing:
    """A discovered listing (pre-evaluation): the fields the funnel + digest need."""

    source: ListingSource
    title: str
    url: str
    price: Decimal
    currency: Currency = Currency.EUR
    shipping: Decimal = Decimal(0)
    seller_location: str | None = None
    is_eu: bool = False
    listing_type: str | None = None  # auction / buy-now / classified
    close_at: dt.datetime | None = None
    first_seen: dt.datetime | None = None
