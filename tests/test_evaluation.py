"""Evaluation seam: the funnel composing fitment + valuation into a surface decision.

Tier-A: the surface rule gates whether a human ever sees a listing, so it carries property
tests (REJECT always DROPs; APPROVE_ELIGIBLE implies every safety condition) on top of the
worked examples.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from quartermaster.evaluation import (
    MAX_FX_AGE_DAYS,
    EvaluatedListing,
    Surface,
    evaluate,
)
from quartermaster.fitment import (
    G513QR,
    Assessment,
    DdrGen,
    FormFactor,
    RamSpec,
    Verdict,
    assess,
)
from quartermaster.valuation import Baseline, BaselineTag, deal_pct

LIVE = Baseline(14080, BaselineTag.LIVE, n_comps=12)
BOOTSTRAP = Baseline(14080, BaselineTag.BOOTSTRAP)


def _perfect_spec() -> RamSpec:
    return RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        speed_mts=3200,
        capacity_gb_per_module=32,
        module_count=2,
        ecc=False,
        registered=False,
        voltage_v=1.2,
    )


def _ddr5_spec() -> RamSpec:
    return RamSpec(
        ddr_gen=DdrGen.DDR5,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=16,
        module_count=2,
    )


def _ecc_spec() -> RamSpec:
    return RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=16,
        module_count=2,
        ecc=True,
    )


def _pass() -> Assessment:
    return assess(_perfect_spec(), G513QR)


# --- worked examples, one per surface path ---


def test_full_pass_is_approve_eligible() -> None:
    ev = evaluate(_pass(), 10000, LIVE, is_eu=True, costs_complete=True, fx_age_days=0)
    assert isinstance(ev, EvaluatedListing)
    assert ev.surface is Surface.APPROVE_ELIGIBLE
    assert ev.reasons == ()
    assert ev.deal == deal_pct(10000, 14080)  # ~0.29 below market


def test_bootstrap_baseline_is_alert() -> None:
    ev = evaluate(_pass(), 10000, BOOTSTRAP, is_eu=True, costs_complete=True, fx_age_days=0)
    assert ev.surface is Surface.ALERT_ONLY
    assert "no live market baseline" in ev.reasons


def test_non_eu_is_alert() -> None:
    ev = evaluate(_pass(), 10000, LIVE, is_eu=False, costs_complete=True, fx_age_days=0)
    assert ev.surface is Surface.ALERT_ONLY
    assert "non-EU seller" in ev.reasons


def test_incomplete_costs_is_alert() -> None:
    ev = evaluate(_pass(), 10000, LIVE, is_eu=True, costs_complete=False, fx_age_days=0)
    assert ev.surface is Surface.ALERT_ONLY
    assert "landed cost incomplete" in ev.reasons


def test_stale_fx_is_alert() -> None:
    ev = evaluate(
        _pass(), 10000, LIVE, is_eu=True, costs_complete=True, fx_age_days=MAX_FX_AGE_DAYS + 6
    )
    assert ev.surface is Surface.ALERT_ONLY
    assert any("FX snapshot stale" in r for r in ev.reasons)


def test_reject_is_drop_with_blockers() -> None:
    ev = evaluate(
        assess(_ddr5_spec(), G513QR), 10000, LIVE, is_eu=True, costs_complete=True, fx_age_days=0
    )
    assert ev.surface is Surface.DROP
    assert ev.reasons  # the blocker reasons travel with the drop


def test_unverified_is_alert() -> None:
    ev = evaluate(
        assess(_ecc_spec(), G513QR), 10000, LIVE, is_eu=True, costs_complete=True, fx_age_days=0
    )
    assert ev.surface is Surface.ALERT_ONLY
    assert "fitment unverified" in ev.reasons


def test_no_baseline_deal_is_zero() -> None:
    ev = evaluate(_pass(), 10000, None, is_eu=True, costs_complete=True, fx_age_days=0)
    assert ev.deal == deal_pct(10000, 0)  # 0 -- no positive baseline
    assert ev.surface is Surface.ALERT_ONLY


# --- properties ---

_SPECS = [_perfect_spec(), _ddr5_spec(), _ecc_spec()]


@given(
    st.sampled_from(_SPECS),
    st.sampled_from(list(BaselineTag)),
    st.booleans(),
    st.booleans(),
    st.integers(min_value=0, max_value=30),
)
def test_surface_invariants(
    spec: RamSpec, tag: BaselineTag, is_eu: bool, complete: bool, fx_age: int
) -> None:
    a = assess(spec, G513QR)
    ev = evaluate(
        a, 10000, Baseline(14080, tag), is_eu=is_eu, costs_complete=complete, fx_age_days=fx_age
    )
    if a.verdict is Verdict.REJECT:
        assert ev.surface is Surface.DROP
    if ev.surface is Surface.APPROVE_ELIGIBLE:
        # APPROVE_ELIGIBLE is reachable ONLY when every safety condition holds.
        assert a.verdict is Verdict.PASS
        assert tag is BaselineTag.LIVE
        assert is_eu
        assert complete
        assert fx_age <= MAX_FX_AGE_DAYS
