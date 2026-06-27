"""FX rates from the ECB euro reference rates -- never hardcoded.

The ``currency_converter`` library bundles (and can refresh) the European Central Bank daily
reference rates. ``ecb_fx_rates()`` builds a timestamped ``FxRates`` snapshot from that source for
the first-class currencies; the snapshot's ``as_of`` date lets callers guard against staleness
rather than silently trusting an old rate. Refresh by updating the dependency or pointing the
library at a freshly downloaded ECB file (a prod refresh job; out of scope here).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from currency_converter import CurrencyConverter

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
