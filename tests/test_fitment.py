"""Fitment + compatibility gates: unit cases per verdict path + hypothesis properties.

Tier-A (plan sec.9): the compatibility predicates are a parser-class concern, so they
carry property tests on top of the worked examples.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from quartermaster.fitment import (
    G513QR,
    DdrGen,
    FormFactor,
    GateStatus,
    RamSpec,
    Verdict,
    assess,
)


def _perfect() -> RamSpec:
    """A matched, in-spec 2x32 GB DDR4-3200 SO-DIMM kit for the G513QR."""
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


# --- worked examples, one per outcome path ---


def test_perfect_kit_passes() -> None:
    a = assess(_perfect(), G513QR)
    assert a.verdict is Verdict.PASS
    assert a.blockers == ()
    assert a.notes == ()


def test_ddr5_module_rejected() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR5,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=16,
        module_count=2,
    )
    a = assess(spec, G513QR)
    assert a.verdict is Verdict.REJECT
    assert any("DDR5" in b for b in a.blockers)


def test_desktop_udimm_rejected() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4, form_factor=FormFactor.UDIMM, capacity_gb_per_module=16, module_count=2
    )
    assert assess(spec, G513QR).verdict is Verdict.REJECT


def test_buffered_module_rejected() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=16,
        module_count=2,
        registered=True,
    )
    assert assess(spec, G513QR).verdict is Verdict.REJECT


def test_oversized_module_rejected() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=64,
        module_count=2,
    )
    a = assess(spec, G513QR)
    assert a.verdict is Verdict.REJECT
    assert any("64 GB/module" in b for b in a.blockers)


def test_too_many_modules_rejected() -> None:
    # 4x16 = 64 GB total (within the cap) but only 2 slots -> reject on slot count.
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=16,
        module_count=4,
    )
    a = assess(spec, G513QR)
    assert a.verdict is Verdict.REJECT
    assert any("slots" in b for b in a.blockers)


def test_ecc_module_is_unverified() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=16,
        module_count=2,
        ecc=True,
    )
    a = assess(spec, G513QR)
    assert a.verdict is Verdict.UNVERIFIED
    assert any(g.status is GateStatus.RISK for g in a.gates)


def test_single_module_passes_with_note() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        speed_mts=3200,
        capacity_gb_per_module=32,
        module_count=1,
    )
    a = assess(spec, G513QR)
    assert a.verdict is Verdict.PASS
    assert any("single-channel" in n for n in a.notes)


def test_slower_ram_passes_with_note() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        speed_mts=2666,
        capacity_gb_per_module=16,
        module_count=2,
    )
    a = assess(spec, G513QR)
    assert a.verdict is Verdict.PASS
    assert any("below" in n for n in a.notes)


def test_faster_ram_passes_no_penalty() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        speed_mts=3600,
        capacity_gb_per_module=16,
        module_count=2,
    )
    a = assess(spec, G513QR)
    assert a.verdict is Verdict.PASS
    assert a.notes == ()
    assert any("downclocks" in g.reason for g in a.gates)


def test_unknown_generation_is_unverified() -> None:
    spec = RamSpec(
        form_factor=FormFactor.SODIMM, speed_mts=3200, capacity_gb_per_module=16, module_count=2
    )
    assert assess(spec, G513QR).verdict is Verdict.UNVERIFIED


def test_unknown_speed_still_passes() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=16,
        module_count=2,
        registered=False,
    )
    assert assess(spec, G513QR).verdict is Verdict.PASS


def test_empty_spec_is_unverified() -> None:
    assert assess(RamSpec(), G513QR).verdict is Verdict.UNVERIFIED


# --- properties ---

_ram_specs = st.builds(
    RamSpec,
    ddr_gen=st.none() | st.sampled_from(DdrGen),
    form_factor=st.none() | st.sampled_from(FormFactor),
    speed_mts=st.none() | st.integers(min_value=1600, max_value=6400),
    capacity_gb_per_module=st.none() | st.sampled_from([4, 8, 16, 32, 48, 64]),
    module_count=st.none() | st.integers(min_value=1, max_value=4),
    ecc=st.none() | st.booleans(),
    registered=st.none() | st.booleans(),
    voltage_v=st.none() | st.sampled_from([1.1, 1.2, 1.35, 1.5]),
)


@given(_ram_specs)
def test_assess_is_total(spec: RamSpec) -> None:
    """assess never raises and always yields a known verdict for any spec."""
    assert assess(spec, G513QR).verdict in set(Verdict)


@given(_ram_specs)
def test_unknown_never_passes(spec: RamSpec) -> None:
    """A spec missing any critical field can never PASS (plan: unknown -> never PASS)."""
    if spec.ddr_gen is None or spec.form_factor is None or spec.capacity_gb_per_module is None:
        assert assess(spec, G513QR).verdict is not Verdict.PASS


@given(_ram_specs)
def test_wrong_generation_always_rejected(spec: RamSpec) -> None:
    if spec.ddr_gen is not None and spec.ddr_gen != DdrGen.DDR4:
        assert assess(spec, G513QR).verdict is Verdict.REJECT


@given(_ram_specs)
def test_oversized_module_always_rejected(spec: RamSpec) -> None:
    if (
        spec.capacity_gb_per_module is not None
        and spec.capacity_gb_per_module > G513QR.max_per_module_gb
    ):
        assert assess(spec, G513QR).verdict is Verdict.REJECT


_in_spec_kits = st.builds(
    RamSpec,
    ddr_gen=st.just(DdrGen.DDR4),
    form_factor=st.just(FormFactor.SODIMM),
    speed_mts=st.sampled_from([3200, 3600]),
    capacity_gb_per_module=st.sampled_from([8, 16, 32]),
    module_count=st.just(2),
    ecc=st.just(False),
    registered=st.just(False),
    voltage_v=st.just(1.2),
)


@given(_in_spec_kits)
def test_in_spec_matched_kits_pass(spec: RamSpec) -> None:
    a = assess(spec, G513QR)
    assert a.verdict is Verdict.PASS
    assert a.blockers == ()
