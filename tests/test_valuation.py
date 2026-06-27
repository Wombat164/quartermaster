"""Valuation: first-class EUR/USD/GBP currencies, landed cost, baseline, deal scoring.

Tier-A (plan sec.9): money/parse code carries property tests on top of worked examples.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from quartermaster.fitment import DdrGen, FormFactor, RamSpec
from quartermaster.valuation import (
    BOOTSTRAP_EUR_PER_GB,
    BaselineTag,
    Currency,
    FxRates,
    LandedCost,
    bootstrap_baseline,
    deal_pct,
)

# Sample snapshot: 1 USD = 0.92 EUR, 1 GBP = 1.17 EUR.
FX = FxRates(
    {Currency.EUR: Decimal(1), Currency.USD: Decimal("0.92"), Currency.GBP: Decimal("1.17")}
)


# --- currencies are first-class ---


def test_landed_eur() -> None:
    assert LandedCost(price=Decimal("50.00"), shipping=Decimal("5.00")).eur_cents(FX) == 5500


def test_landed_usd_first_class() -> None:
    assert LandedCost(price=Decimal("100.00"), currency=Currency.USD).eur_cents(FX) == 9200


def test_landed_gbp_first_class() -> None:
    assert LandedCost(price=Decimal("40.00"), currency=Currency.GBP).eur_cents(FX) == 4680


def test_landed_import_vat_added() -> None:
    assert (
        LandedCost(price=Decimal("100.00"), import_vat_rate=Decimal("0.21")).eur_cents(FX) == 12100
    )


def test_landed_rounds_half_up() -> None:
    assert LandedCost(price=Decimal("9.995")).eur_cents(FX) == 1000  # 999.5 -> 1000


def test_landed_rejects_absurd_vat_rate() -> None:
    with pytest.raises(ValueError, match="import_vat_rate"):
        LandedCost(price=Decimal("100.00"), import_vat_rate=Decimal(21))  # 21, not 0.21


def test_landed_rejects_negative_price() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        LandedCost(price=Decimal("-1.00"))


def test_to_eur_eur_is_identity() -> None:
    assert FX.to_eur(Decimal("123.45"), Currency.EUR) == Decimal("123.45")


def test_fx_requires_every_currency() -> None:
    with pytest.raises(ValueError, match="GBP"):
        FxRates({Currency.EUR: Decimal(1), Currency.USD: Decimal("0.92")})


def test_fx_eur_must_be_one() -> None:
    with pytest.raises(ValueError, match="EUR rate"):
        FxRates(
            {
                Currency.EUR: Decimal("1.01"),
                Currency.USD: Decimal("0.92"),
                Currency.GBP: Decimal("1.17"),
            }
        )


def test_fx_rejects_nonpositive() -> None:
    with pytest.raises(ValueError, match="positive"):
        FxRates({Currency.EUR: Decimal(1), Currency.USD: Decimal(0), Currency.GBP: Decimal("1.17")})


def test_fx_rejects_implausible_rate() -> None:
    # A mis-scaled/inverted rate (USD=100) must not silently 100x every landed cost.
    with pytest.raises(ValueError, match="plausibility band"):
        FxRates(
            {Currency.EUR: Decimal(1), Currency.USD: Decimal(100), Currency.GBP: Decimal("1.17")}
        )


# --- baseline + deal scoring ---


def test_bootstrap_ddr4_64gb() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=32,
        module_count=2,
    )
    b = bootstrap_baseline(spec)
    assert b is not None
    assert b.market_ref_cents == 14080  # 2.20 EUR/GB * 64 GB
    assert b.tag is BaselineTag.BOOTSTRAP


def test_bootstrap_unknown_returns_none() -> None:
    assert bootstrap_baseline(RamSpec(ddr_gen=DdrGen.DDR4)) is None  # no size
    assert bootstrap_baseline(RamSpec(capacity_gb_per_module=16, module_count=2)) is None  # no gen


def test_bootstrap_table_covers_all_ddr_gens() -> None:
    # Adding a DdrGen without a table row would silently give that generation no valuation.
    assert set(BOOTSTRAP_EUR_PER_GB) == set(DdrGen)


def test_deal_pct_below_market() -> None:
    assert round(deal_pct(10000, 14080), 4) == Decimal("0.2898")


def test_deal_pct_at_or_above_market_is_zero() -> None:
    assert deal_pct(14080, 14080) == Decimal(0)
    assert deal_pct(16000, 14080) == Decimal(0)


def test_deal_pct_free_is_one() -> None:
    assert deal_pct(0, 14080) == Decimal(1)


def test_deal_pct_no_baseline_is_zero() -> None:
    assert deal_pct(5000, 0) == Decimal(0)


# --- properties ---

_amounts = st.decimals(
    min_value=Decimal(0),
    max_value=Decimal("100000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)
_rates = st.decimals(
    min_value=Decimal("0.10"), max_value=Decimal(5), allow_nan=False, allow_infinity=False, places=4
)
_fx = st.builds(
    lambda u, g: FxRates({Currency.EUR: Decimal(1), Currency.USD: u, Currency.GBP: g}),
    _rates,
    _rates,
)
_cents = st.integers(min_value=0, max_value=10_000_000)


@given(_amounts, _amounts, st.sampled_from(Currency), _fx)
def test_eur_cents_is_nonnegative(
    price: Decimal, shipping: Decimal, cur: Currency, fx: FxRates
) -> None:
    assert LandedCost(price=price, shipping=shipping, currency=cur).eur_cents(fx) >= 0


@given(_amounts, _amounts, st.sampled_from(Currency), _fx)
def test_eur_cents_monotonic_in_price(
    price: Decimal, delta: Decimal, cur: Currency, fx: FxRates
) -> None:
    lo = LandedCost(price=price, currency=cur).eur_cents(fx)
    hi = LandedCost(price=price + delta, currency=cur).eur_cents(fx)
    assert hi >= lo


@given(_amounts, _fx)
def test_to_eur_eur_identity_property(amount: Decimal, fx: FxRates) -> None:
    assert fx.to_eur(amount, Currency.EUR) == amount


@given(_cents, st.integers(min_value=1, max_value=10_000_000))
def test_deal_pct_in_unit_interval(landed: int, ref: int) -> None:
    assert Decimal(0) <= deal_pct(landed, ref) <= Decimal(1)
