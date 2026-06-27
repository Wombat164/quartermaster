"""Valuation -- currencies, landed cost, cold-start baseline, deal scoring (Phase-1 "value"
block, plan sec.3).

EUR, USD and GBP are **first-class** (the `Currency` enum + `FxRates`); no currency is special-
cased -- EUR simply has rate 1. Money is computed in `Decimal` and rounded to integer **EUR
cents** (the ledger's settlement unit; never float -- a plan antipattern). EUR is the comparison
base because settlement is in EUR; listings and comps may be priced in any first-class currency
and are converted via a single FX snapshot (sourced upstream, e.g. timestamped ECB).

Pure + network-free: the live price baseline (SerpApi) is a separate upstream concern (P1.2b);
here a `Baseline` is taken or produced from the cold-start table, always carrying a provenance tag
(bootstrap | live | stale) so the digest can show how trustworthy a valuation is.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

_CENTS = Decimal(1)


def to_cents(eur: Decimal) -> int:
    """Round a EUR amount to integer cents (ROUND_HALF_UP) -- the money unit boundary."""
    return int((eur * 100).quantize(_CENTS, rounding=ROUND_HALF_UP))


class Currency(StrEnum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"


@dataclass(frozen=True, slots=True)
class FxRates:
    """A snapshot of EUR-per-1-unit rates. Every first-class currency must be present and
    positive; EUR is exactly 1. Treats all currencies symmetrically."""

    eur_per: Mapping[Currency, Decimal]

    def __post_init__(self) -> None:
        for cur in Currency:
            rate = self.eur_per.get(cur)
            if rate is None:
                raise ValueError(f"FxRates missing rate for {cur.value}")
            if rate <= 0:
                raise ValueError(f"FxRates rate for {cur.value} must be positive")
            # Plausibility band (EUR-per-unit): catch a mis-scaled / inverted / corrupt rate
            # before it silently multiplies every landed cost. EUR/USD/GBP all sit in [0.1, 10].
            if cur is not Currency.EUR and not (Decimal("0.1") <= rate <= Decimal(10)):
                raise ValueError(
                    f"FxRates rate for {cur.value} ({rate}) outside plausibility band 0.1..10"
                )
        if self.eur_per[Currency.EUR] != Decimal(1):
            raise ValueError("FxRates: EUR rate must be exactly 1")

    def to_eur(self, amount: Decimal, currency: Currency) -> Decimal:
        return amount * self.eur_per[currency]


class BaselineTag(StrEnum):
    BOOTSTRAP = "bootstrap"  # cold-start table; weak -- keep items ALERT-only
    LIVE = "live"  # enough fresh comps to trust
    STALE = "stale"  # comps too old -> treat as weak


@dataclass(frozen=True, slots=True)
class Baseline:
    """A market reference price (EUR cents) with provenance."""

    market_ref_cents: int
    tag: BaselineTag
    n_comps: int = 0


@dataclass(frozen=True, slots=True)
class Comp:
    """A single price comparable from a deterministic source (NEVER sent to an LLM). Any
    first-class currency; ``source`` is provenance (e.g. "serpapi_google_shopping")."""

    price: Decimal
    currency: Currency
    source: str


@dataclass(frozen=True, slots=True)
class LandedCost:
    """All-in cost of buying a listing, priced in any first-class currency. `import_vat_rate`
    is > 0 only when the purchase adds VAT (cross-border / retail); private EU classifieds add
    none. `eur_cents` converts to the EUR settlement base via an FX snapshot."""

    price: Decimal
    shipping: Decimal = Decimal(0)
    currency: Currency = Currency.EUR
    import_vat_rate: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if self.price < 0 or self.shipping < 0:
            raise ValueError("LandedCost price and shipping must be non-negative")
        if not (Decimal(0) <= self.import_vat_rate < Decimal(1)):
            raise ValueError("import_vat_rate must be in [0, 1) -- a rate like 0.21, not 21")

    def eur_cents(self, fx: FxRates) -> int:
        subtotal = fx.to_eur(self.price + self.shipping, self.currency)
        total = subtotal * (Decimal(1) + self.import_vat_rate)
        return to_cents(total)


# A live baseline needs enough comps to trust; below this it stays bootstrap/ALERT (plan sec.3).
MIN_LIVE_COMPS = 5
# Drop the top + bottom fraction before the median, so a single mispriced comp can't move it.
TRIM_FRACTION = Decimal("0.1")


def _trimmed_median_cents(values: Sequence[int]) -> int:
    ordered = sorted(values)
    k = int(len(ordered) * TRIM_FRACTION)
    core = ordered[k : len(ordered) - k] or ordered
    mid = len(core) // 2
    if len(core) % 2 == 1:
        return core[mid]
    return (core[mid - 1] + core[mid]) // 2


def live_baseline(comps: Sequence[Comp], fx: FxRates) -> Baseline | None:
    """Trimmed-median market reference (EUR cents) over deterministic comps, each FX-converted.

    ``None`` when there are too few comps to trust -- the caller then falls back to the bootstrap
    table (tagged so the funnel keeps the listing ALERT-only).
    """
    if len(comps) < MIN_LIVE_COMPS:
        return None
    cents = [to_cents(fx.to_eur(c.price, c.currency)) for c in comps]
    return Baseline(_trimmed_median_cents(cents), BaselineTag.LIVE, n_comps=len(comps))


def deal_pct(landed_cents: int, market_ref_cents: int) -> Decimal:
    """``clamp((market_ref - landed) / market_ref, 0, 1)`` -- the fraction below market.

    0 when there is no positive baseline or the listing is at/above market; 1 when free.
    """
    if market_ref_cents <= 0:
        return Decimal(0)
    raw = (Decimal(market_ref_cents) - Decimal(landed_cents)) / Decimal(market_ref_cents)
    return min(Decimal(1), max(Decimal(0), raw))
