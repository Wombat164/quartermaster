"""Digest: ranking (tier then deal%, DROP excluded) + ASCII rendering."""

from __future__ import annotations

from quartermaster.digest import DigestItem, rank, render_digest
from quartermaster.evaluation import evaluate
from quartermaster.fitment import G513QR, DdrGen, FormFactor, RamSpec, assess
from quartermaster.ingest import Confidence
from quartermaster.valuation import Baseline, BaselineTag


def _perfect() -> RamSpec:
    return RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        speed_mts=3200,
        capacity_gb_per_module=16,
        module_count=2,
        ecc=False,
        registered=False,
        voltage_v=1.2,
    )


def _item(
    title: str,
    landed: int,
    market: int,
    tag: BaselineTag,
    *,
    url: str = "",
    conf: Confidence = Confidence.HIGH,
) -> DigestItem:
    ev = evaluate(
        assess(_perfect(), G513QR),
        landed,
        Baseline(market, tag),
        is_eu=True,
        costs_complete=True,
        fx_age_days=0,
    )
    return DigestItem(title=title, url=url, evaluation=ev, confidence=conf)


def _drop_item() -> DigestItem:
    ddr5 = RamSpec(
        ddr_gen=DdrGen.DDR5,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=16,
        module_count=2,
    )
    ev = evaluate(
        assess(ddr5, G513QR),
        8000,
        Baseline(14080, BaselineTag.LIVE),
        is_eu=True,
        costs_complete=True,
        fx_age_days=0,
    )
    return DigestItem(title="drop", url="", evaluation=ev, confidence=Confidence.HIGH)


def test_rank_orders_by_tier_then_deal_and_drops_incompatible() -> None:
    approve = _item("approve", 8000, 14080, BaselineTag.LIVE)  # PASS+live+eu+complete+fresh
    alert_big = _item("alert-big", 7000, 14080, BaselineTag.BOOTSTRAP)  # ALERT (bootstrap), ~50%
    alert_small = _item("alert-small", 13000, 14080, BaselineTag.BOOTSTRAP)  # ALERT, ~8%
    ranked = rank([alert_small, _drop_item(), alert_big, approve])
    assert [it.title for it in ranked] == ["approve", "alert-big", "alert-small"]


def test_render_has_header_and_rows() -> None:
    item = _item("Corsair 2x16GB DDR4", 8000, 14080, BaselineTag.LIVE, url="https://example.test/x")
    out = render_digest([item], dry_run=True, fx_age_days=2)
    assert "QUARTERMASTER digest" in out
    assert "DRY_RUN=true" in out
    assert "FX 2d old" in out
    assert "[APPROVE]" in out
    assert "Corsair 2x16GB DDR4" in out
    assert "landed EUR 80.00" in out
    assert "https://example.test/x" in out


def test_alert_row_shows_reason() -> None:
    out = render_digest(
        [_item("Crucial 32GB", 9000, 14080, BaselineTag.BOOTSTRAP)], dry_run=True, fx_age_days=0
    )
    assert "[ALERT" in out
    assert "no live market baseline" in out  # the demoting reason travels onto the row


def test_render_empty_and_drop_only() -> None:
    assert "(no listings surfaced)" in render_digest([], dry_run=True, fx_age_days=0)
    assert "(no listings surfaced)" in render_digest([_drop_item()], dry_run=True, fx_age_days=0)
