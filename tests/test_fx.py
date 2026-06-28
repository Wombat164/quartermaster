"""ECB FX source: rates are loaded from the ECB reference data (offline bundled), not
hardcoded. The autouse network-egress blocker guarantees this touches no network."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from currency_converter import CurrencyConverter

from quartermaster.fx import ecb_fx_rates, live_ecb_converter
from quartermaster.valuation import Currency, FxRates


def test_ecb_fx_rates_load() -> None:
    snap = ecb_fx_rates()
    assert isinstance(snap.rates, FxRates)
    # EUR is the base (rate 1); USD/GBP are present + positive, sourced from ECB.
    assert snap.rates.eur_per[Currency.EUR] == Decimal(1)
    assert snap.rates.eur_per[Currency.USD] > 0
    assert snap.rates.eur_per[Currency.GBP] > 0
    assert isinstance(snap.as_of, dt.date)


def test_snapshot_age() -> None:
    snap = ecb_fx_rates()
    assert snap.age_days(snap.as_of) == 0
    assert snap.age_days(snap.as_of + dt.timedelta(days=5)) == 5
    assert snap.age_days(snap.as_of - dt.timedelta(days=3)) == 0  # clock skew clamps to 0


def test_live_ecb_converter_falls_back_when_offline() -> None:
    # the autouse egress blocker fails the download -> bundled fallback, never crashes
    assert isinstance(live_ecb_converter(), CurrencyConverter)
