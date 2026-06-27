"""Phase-1 Listing + the B1/B2 LLM-routing boundary. The guard exists BEFORE any LLM path, so
P1.3 cannot route deterministic-only content (SerpApi / eBay) into a model."""

from __future__ import annotations

from decimal import Decimal

import pytest

from quartermaster.listings import (
    Listing,
    ListingSource,
    LlmBoundaryViolation,
    assert_llm_allowed,
    llm_allowed,
)
from quartermaster.valuation import Currency


def test_only_classifieds_email_is_llm_allowed() -> None:
    assert llm_allowed(ListingSource.CLASSIFIEDS_EMAIL)
    assert not llm_allowed(ListingSource.SERPAPI_SHOPPING)
    assert not llm_allowed(ListingSource.EBAY)


def test_assert_passes_for_classifieds() -> None:
    assert_llm_allowed(ListingSource.CLASSIFIEDS_EMAIL)  # must not raise


@pytest.mark.parametrize("src", [ListingSource.SERPAPI_SHOPPING, ListingSource.EBAY])
def test_b1_guard_blocks_deterministic_sources(src: ListingSource) -> None:
    with pytest.raises(LlmBoundaryViolation):
        assert_llm_allowed(src)


def test_every_source_is_decided() -> None:
    # No source may be silently un-routed; every member yields a bool decision.
    for src in ListingSource:
        assert isinstance(llm_allowed(src), bool)


def test_listing_defaults() -> None:
    li = Listing(
        source=ListingSource.CLASSIFIEDS_EMAIL,
        title="DDR4 2x32",
        url="https://example.test/x",
        price=Decimal("120"),
    )
    assert li.currency is Currency.EUR
    assert li.is_eu is False
    assert li.shipping == Decimal(0)
