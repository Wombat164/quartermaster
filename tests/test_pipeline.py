"""The funnel runner: assemble one extracted listing into a DigestItem; run a batch."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from quartermaster.evaluation import Surface
from quartermaster.fitment import G513QR, DdrGen, FormFactor, RamSpec
from quartermaster.fx import FxSnapshot
from quartermaster.ingest import Confidence, ExtractedListing, LlmExtraction
from quartermaster.listings import ListingSource
from quartermaster.pipeline import RawListing, assemble, null_extractor, run_pass
from quartermaster.ram import bootstrap_baseline
from quartermaster.valuation import Baseline, BaselineTag, Currency, FxRates

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
