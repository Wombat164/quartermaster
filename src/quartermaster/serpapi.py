"""SerpApi Google-Shopping client -- the deterministic price-comp source for P1.2b.

Produces a list of `Comp` (price comparables) from SerpApi's Google-Shopping engine. This is the
**compliant compare baseline** (retail / Amazon / eBay-as-price-comps, no scraping). The comps are
DETERMINISTIC-ONLY: they are never sent to an LLM (plan sec.4 boundary B2); only the numeric price +
currency + a source tag are kept, no free text.

Security: SerpApi takes the API key as a **query parameter**, so the request URL contains the
secret -- never log the full URL. (There is no logging here yet; structlog + redaction land before
any logger touches this.) The key is passed in by the caller, unwrapped from
`config.serpapi_api_key`, never read from disk here. Tests mock the HTTP layer with respx; the
autouse egress backstop guarantees no live call escapes CI.
"""

from __future__ import annotations

from decimal import Decimal

import httpx

from .valuation import Comp, Currency

SERPAPI_URL = "https://serpapi.com/search.json"
SOURCE = "serpapi_google_shopping"

# Map the formatted-price symbol to a first-class currency; fall back to the request's locale.
_SYMBOL_CURRENCY: dict[str, Currency] = {"€": Currency.EUR, "£": Currency.GBP, "$": Currency.USD}


class SerpApiError(RuntimeError):
    """SerpApi returned an error payload (bad key, exhausted quota, ...)."""


def _currency_from_price(price: str, default: Currency) -> Currency:
    for symbol, currency in _SYMBOL_CURRENCY.items():
        if symbol in price:
            return currency
    return default


def _parse_comps(data: object, default_currency: Currency) -> list[Comp]:
    comps: list[Comp] = []
    if not isinstance(data, dict):
        return comps
    if "error" in data:
        raise SerpApiError(str(data["error"]))
    results = data.get("shopping_results")
    if not isinstance(results, list):
        return comps
    for item in results:
        if not isinstance(item, dict):
            continue
        extracted = item.get("extracted_price")
        # bool is an int subclass -- exclude it explicitly so a stray True can't become a price.
        if isinstance(extracted, bool) or not isinstance(extracted, (int, float)) or extracted <= 0:
            continue
        raw_price = item.get("price")
        price_str = raw_price if isinstance(raw_price, str) else ""
        currency = _currency_from_price(price_str, default_currency)
        comps.append(Comp(Decimal(str(extracted)), currency, SOURCE))
    return comps


def fetch_shopping_comps(
    query: str,
    *,
    api_key: str,
    gl: str = "be",
    hl: str = "nl",
    default_currency: Currency = Currency.EUR,
    client: httpx.Client | None = None,
    timeout: float = 15.0,
) -> list[Comp]:
    """Fetch Google-Shopping price comps for ``query`` via SerpApi. Pure data -> ``Comp`` list.

    ``gl``/``hl`` set the shopping locale (default Belgium/Dutch -> EUR). Inject ``client`` to reuse
    a connection (and for respx in tests); otherwise a short-lived client is used.
    """
    params = {"engine": "google_shopping", "q": query, "api_key": api_key, "gl": gl, "hl": hl}
    owns_client = client is None
    http = client if client is not None else httpx.Client(timeout=timeout)
    try:
        response = http.get(SERPAPI_URL, params=params)
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            http.close()
    return _parse_comps(data, default_currency)
