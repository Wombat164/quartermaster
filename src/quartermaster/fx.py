"""FX rates from the ECB euro reference rates -- never hardcoded.

The ``currency_converter`` library bundles (and can refresh) the European Central Bank daily
reference rates. ``ecb_fx_rates()`` builds a timestamped ``FxRates`` snapshot from that source for
the first-class currencies; the snapshot's ``as_of`` date lets callers guard against staleness
rather than silently trusting an old rate. Production callers pass ``live_ecb_converter()`` to use a
freshly downloaded ECB file; ``ecb_fx_rates()`` itself stays network-free (bundled) so tests need no
network.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from currency_converter import ECB_URL, CurrencyConverter

from .valuation import Currency, FxRates


@dataclass(frozen=True, slots=True)
class FxSnapshot:
    """An ``FxRates`` plus the ECB date it was sourced from (provenance for staleness checks)."""

    rates: FxRates
    as_of: dt.date

    def age_days(self, today: dt.date) -> int:
        # Clamp at 0: a future as_of (clock skew) must never read as a "fresh" negative age.
        return max(0, (today - self.as_of).days)


def ecb_fx_rates(converter: CurrencyConverter | None = None) -> FxSnapshot:
    """Build an ``FxRates`` snapshot from ECB reference rates (EUR per 1 unit of each currency).

    Reads the library's bundled ECB data (no network); inject a ``converter`` to override.
    """
    c = converter if converter is not None else CurrencyConverter()
    eur_per: dict[Currency, Decimal] = {Currency.EUR: Decimal(1)}
    dates: list[dt.date] = []
    for cur in Currency:
        if cur is Currency.EUR:
            continue
        eur_per[cur] = Decimal(str(c.convert(1, cur.value, "EUR")))
        dates.append(c.bounds[cur.value].last_date)
    return FxSnapshot(FxRates(eur_per), min(dates))


def live_ecb_converter() -> CurrencyConverter:
    """A converter from a freshly downloaded ECB daily file (current rates) -- for the CLI.

    Falls back to the library's bundled snapshot if the download fails (offline); that then reads as
    stale and the staleness guard handles it. ``ecb_fx_rates()`` itself stays network-free.
    """
    try:
        return CurrencyConverter(ECB_URL)
    except Exception:  # best-effort fetch; offline -> bundled fallback (will read as stale)
        return CurrencyConverter()
