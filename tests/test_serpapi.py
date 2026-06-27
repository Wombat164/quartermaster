"""SerpApi client: parse Google-Shopping results into Comps. All HTTP is respx-mocked, so
no live call escapes (the autouse egress backstop is the second line of defence)."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
import respx

from quartermaster.serpapi import (
    SERPAPI_URL,
    SOURCE,
    SerpApiError,
    fetch_shopping_comps,
)
from quartermaster.valuation import Comp, Currency, FxRates, live_baseline


def _shopping(*items: dict[str, object]) -> dict[str, object]:
    return {"shopping_results": list(items)}


@respx.mock
def test_fetch_parses_comps() -> None:
    respx.get(SERPAPI_URL).mock(
        return_value=httpx.Response(
            200,
            json=_shopping(
                {"title": "a", "price": "€120,00", "extracted_price": 120.0},
                {"title": "b", "price": "€110,00", "extracted_price": 110.0},
            ),
        )
    )
    comps = fetch_shopping_comps("DDR4 32GB", api_key="test")
    assert comps == [
        Comp(Decimal("120.0"), Currency.EUR, SOURCE),
        Comp(Decimal("110.0"), Currency.EUR, SOURCE),
    ]


@respx.mock
def test_fetch_reads_currency_from_symbol() -> None:
    respx.get(SERPAPI_URL).mock(
        return_value=httpx.Response(
            200,
            json=_shopping(
                {"price": "$130.00", "extracted_price": 130.0},
                {"price": "£100.00", "extracted_price": 100.0},
                {"price": "no symbol", "extracted_price": 90.0},  # -> default (EUR)
            ),
        )
    )
    comps = fetch_shopping_comps("x", api_key="test")
    assert [c.currency for c in comps] == [Currency.USD, Currency.GBP, Currency.EUR]


@respx.mock
def test_fetch_skips_unusable_prices() -> None:
    respx.get(SERPAPI_URL).mock(
        return_value=httpx.Response(
            200,
            json=_shopping(
                {"price": "€120,00", "extracted_price": 120.0},
                {"title": "no price"},  # no extracted_price
                {"price": "€0", "extracted_price": 0},  # non-positive
            ),
        )
    )
    comps = fetch_shopping_comps("x", api_key="test")
    assert len(comps) == 1


@respx.mock
def test_fetch_raises_on_serpapi_error() -> None:
    respx.get(SERPAPI_URL).mock(return_value=httpx.Response(200, json={"error": "Invalid API key"}))
    with pytest.raises(SerpApiError, match="Invalid API key"):
        fetch_shopping_comps("x", api_key="bad")


@respx.mock
def test_fetch_raises_on_http_error() -> None:
    respx.get(SERPAPI_URL).mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_shopping_comps("x", api_key="bad")


@respx.mock
def test_fetched_comps_feed_live_baseline() -> None:
    fx = FxRates(
        {Currency.EUR: Decimal(1), Currency.USD: Decimal("0.92"), Currency.GBP: Decimal("1.17")}
    )
    respx.get(SERPAPI_URL).mock(
        return_value=httpx.Response(
            200,
            json=_shopping(*({"price": "€120,00", "extracted_price": 120.0} for _ in range(6))),
        )
    )
    comps = fetch_shopping_comps("DDR4 64GB", api_key="test")
    baseline = live_baseline(comps, fx)
    assert baseline is not None
    assert baseline.n_comps == 6
    assert baseline.market_ref_cents == 12000
