"""The funnel runner: assemble one extracted listing into a DigestItem; run a batch."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from quartermaster.evaluation import Surface
from quartermaster.fitment import G513QR, DdrGen, FormFactor, RamSpec
from quartermaster.fx import FxSnapshot
from quartermaster.ingest import Confidence, ExtractedListing, LlmExtraction
from quartermaster.listings import ListingSource
from quartermaster.pipeline import (
    RawListing,
    assemble,
    make_baseline_resolver,
    null_extractor,
    run_pass,
)
from quartermaster.ram import bootstrap_baseline
from quartermaster.serpapi import SerpApiError
from quartermaster.valuation import Baseline, BaselineTag, Comp, Currency, FxRates

FX = FxSnapshot(
    FxRates(
        {Currency.EUR: Decimal(1), Currency.USD: Decimal("0.92"), Currency.GBP: Decimal("1.17")}
    ),
    dt.date(2026, 6, 16),
)
TODAY = dt.date(2026, 6, 18)  # 2 days old -> fresh


def _extracted(price: Decimal | None, *, currency: Currency = Currency.EUR) -> ExtractedListing:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        speed_mts=3200,
        capacity_gb_per_module=32,
        module_count=2,  # 64 GB total -> bootstrap ref 14080
        ecc=False,
        registered=False,
        voltage_v=1.2,
    )
    return ExtractedListing(
        source=ListingSource.CLASSIFIEDS_EMAIL,
        title="t",
        url="u",
        spec=spec,
        price=price,
        currency=currency,
        confidence=Confidence.HIGH,
    )


def _live(_spec: RamSpec) -> Baseline:
    return Baseline(14080, BaselineTag.LIVE, n_comps=8)


def test_null_extractor_is_empty() -> None:
    assert null_extractor("anything") == LlmExtraction()


def test_assemble_without_price_is_none() -> None:
    assert (
        assemble(_extracted(None), profile=G513QR, fx=FX, baseline_for=_live, today=TODAY) is None
    )


def test_assemble_eu_eur_with_live_baseline_is_approve() -> None:
    item = assemble(
        _extracted(Decimal("80")), profile=G513QR, fx=FX, baseline_for=_live, today=TODAY
    )
    assert item is not None
    assert item.evaluation.landed_cents == 8000
    assert item.evaluation.surface is Surface.APPROVE_ELIGIBLE
    assert item.evaluation.deal > 0  # 80 EUR is below the 140.80 reference


def test_assemble_usd_listing_is_alert() -> None:
    item = assemble(
        _extracted(Decimal("100"), currency=Currency.USD),
        profile=G513QR,
        fx=FX,
        baseline_for=_live,
        today=TODAY,
    )
    assert item is not None
    assert item.evaluation.surface is Surface.ALERT_ONLY  # non-EUR -> costs incomplete


def test_assemble_bootstrap_baseline_is_alert() -> None:
    item = assemble(
        _extracted(Decimal("80")),
        profile=G513QR,
        fx=FX,
        baseline_for=bootstrap_baseline,
        today=TODAY,
    )
    assert item is not None
    assert item.evaluation.surface is Surface.ALERT_ONLY  # bootstrap (not live) -> ALERT
    assert item.evaluation.deal > 0


def test_run_pass_extracts_drops_no_price_and_assembles() -> None:
    raws = [
        RawListing(text="Corsair 2x32GB DDR4-3200 SO-DIMM EUR 80", title="a", url="https://x"),
        RawListing(text="No price here, just DDR4 SODIMM", title="b"),  # dropped (no price)
    ]
    items = run_pass(
        raws,
        llm=null_extractor,
        profile=G513QR,
        fx=FX,
        baseline_for=bootstrap_baseline,
        today=TODAY,
    )
    assert len(items) == 1
    assert items[0].evaluation.landed_cents == 8000


# --- live baseline resolver (SerpApi-backed, bootstrap fallback) ---


def _ddr4_64() -> RamSpec:
    return RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=32,
        module_count=2,
    )


def _comps(n: int) -> list[Comp]:
    return [Comp(Decimal("130"), Currency.EUR, "serpapi") for _ in range(n)]


def test_live_resolver_uses_comps() -> None:
    b = make_baseline_resolver(fetch=lambda _q: _comps(6), fx=FX.rates)(_ddr4_64())
    assert b is not None
    assert b.tag is BaselineTag.LIVE
    assert b.market_ref_cents == 13000  # trimmed median of the EUR 130 comps


def test_live_resolver_falls_back_when_thin() -> None:
    b = make_baseline_resolver(fetch=lambda _q: _comps(3), fx=FX.rates)(_ddr4_64())
    assert b is not None
    assert b.tag is BaselineTag.BOOTSTRAP  # < MIN_LIVE_COMPS -> bootstrap (14080 for DDR4 64 GB)
    assert b.market_ref_cents == 14080


def test_live_resolver_falls_back_on_serpapi_error() -> None:
    def _boom(_q: str) -> list[Comp]:
        raise SerpApiError("bad key")

    b = make_baseline_resolver(fetch=_boom, fx=FX.rates)(_ddr4_64())
    assert b is not None
    assert b.tag is BaselineTag.BOOTSTRAP  # error degrades to bootstrap, never crashes the pass


def test_live_resolver_caches_per_query() -> None:
    calls = {"n": 0}

    def _counting(_q: str) -> list[Comp]:
        calls["n"] += 1
        return _comps(6)

    resolve = make_baseline_resolver(fetch=_counting, fx=FX.rates)
    spec = _ddr4_64()
    resolve(spec)
    resolve(spec)
    assert calls["n"] == 1  # same query -> fetched once
