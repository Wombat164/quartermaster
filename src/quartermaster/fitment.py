"""Fitment + compatibility core (Phase 1; the plan's "verify" block, sec.4/sec.6).

Deterministic, network-free RAM compatibility gating. Given a (possibly partial) parsed
listing spec and a target machine's ``FitmentProfile``, decide ``PASS`` / ``UNVERIFIED``
/ ``REJECT`` with a per-gate reason trail. This is the *funnel before the click*: the
compatibility filter that runs BEFORE any valuation or human attention.

Plan rules honoured (sec.4):
- **Unknown (missing) data on a CRITICAL gate -> UNVERIFIED, never PASS.**
- Hard incompatibility -> REJECT.
- Compatible-but-risky (e.g. ECC on a non-ECC platform) -> RISK -> UNVERIFIED (human checks).
- Compatible-but-suboptimal (slower than rated, single-channel) -> PASS with a note.

No listing text reaches an LLM here: extraction (LLM + llm-guard, upstream) produces the
``RamSpec``; this module is pure deterministic logic over already-structured data. The gate
set is intentionally small + extensible (the plan's "~20 predicates" grow as edge cases
surface). See DECISIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DdrGen(StrEnum):
    DDR3 = "DDR3"
    DDR4 = "DDR4"
    DDR5 = "DDR5"


class FormFactor(StrEnum):
    SODIMM = "SO-DIMM"  # laptop / SFF
    UDIMM = "UDIMM"  # desktop unbuffered DIMM
    # Buffered server modules (RDIMM/LRDIMM) are captured by RamSpec.registered.


class GateStatus(StrEnum):
    OK = "OK"  # compatible
    REJECT = "REJECT"  # hard-incompatible (won't fit / won't run)
    UNKNOWN = "UNKNOWN"  # required data missing
    RISK = "RISK"  # compatible-but-risky -> needs a human check
    SUBOPTIMAL = "SUBOPTIMAL"  # compatible but not ideal -> note only


class Verdict(StrEnum):
    PASS = "PASS"  # noqa: S105  # nosec B105 -- enum member value, not a secret
    UNVERIFIED = "UNVERIFIED"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class RamSpec:
    """A parsed RAM listing's spec. Every field is Optional: ``None`` means "not stated
    in the listing" = unknown. An unknown on a CRITICAL gate forces UNVERIFIED (the plan's
    "never PASS on unknown" rule)."""

    ddr_gen: DdrGen | None = None
    form_factor: FormFactor | None = None
    speed_mts: int | None = None  # data rate in MT/s, e.g. 3200
    capacity_gb_per_module: int | None = None
    module_count: int | None = None
    ecc: bool | None = None
    registered: bool | None = None  # True = buffered (RDIMM/LRDIMM)
    voltage_v: float | None = None

    @property
    def total_gb(self) -> int | None:
        if self.capacity_gb_per_module is None or self.module_count is None:
            return None
        return self.capacity_gb_per_module * self.module_count


@dataclass(frozen=True, slots=True)
class FitmentProfile:
    """A target machine's RAM constraints."""

    name: str
    ddr_gen: DdrGen
    form_factor: FormFactor
    rated_speed_mts: int  # platform-rated data rate (e.g. 3200)
    slots: int
    max_total_gb: int
    max_per_module_gb: int
    ecc_supported: bool = False  # consumer laptops: no ECC
    voltage_v: float = 1.2  # JEDEC DDR4 SO-DIMM


# The concrete profile that seeded the project: the ASUS ROG Strix G15 G513QR
# (Ryzen 9 5900HX). 2 SO-DIMM slots, DDR4-3200, 64 GB max (2x32), non-ECC, 1.2 V.
G513QR = FitmentProfile(
    name="ASUS ROG Strix G15 G513QR",
    ddr_gen=DdrGen.DDR4,
    form_factor=FormFactor.SODIMM,
    rated_speed_mts=3200,
    slots=2,
    max_total_gb=64,
    max_per_module_gb=32,
    ecc_supported=False,
    voltage_v=1.2,
)


@dataclass(frozen=True, slots=True)
class GateResult:
    gate: str
    status: GateStatus
    reason: str


# Gate names whose UNKNOWN result forces UNVERIFIED (data we MUST have to confirm fit).
# Non-critical gates (speed, voltage, dual-channel) never block a PASS by being unknown.
CRITICAL: frozenset[str] = frozenset({"ddr_gen", "form_factor", "per_module_capacity", "kit_fit"})


@dataclass(frozen=True, slots=True)
class Assessment:
    verdict: Verdict
    gates: tuple[GateResult, ...]

    @property
    def notes(self) -> tuple[str, ...]:
        """Compatible-but-suboptimal observations (verdict is still PASS-eligible)."""
        return tuple(g.reason for g in self.gates if g.status is GateStatus.SUBOPTIMAL)

    @property
    def blockers(self) -> tuple[str, ...]:
        """Reasons that prevented a PASS (rejects, risks, critical unknowns)."""
        return tuple(
            g.reason
            for g in self.gates
            if g.status is GateStatus.REJECT
            or g.status is GateStatus.RISK
            or (g.status is GateStatus.UNKNOWN and g.gate in CRITICAL)
        )


# --- Gates: each a pure (spec, profile) -> GateResult. ---


def _ddr_gen(spec: RamSpec, profile: FitmentProfile) -> GateResult:
    if spec.ddr_gen is None:
        return GateResult("ddr_gen", GateStatus.UNKNOWN, "DDR generation not stated")
    if spec.ddr_gen != profile.ddr_gen:
        return GateResult(
            "ddr_gen",
            GateStatus.REJECT,
            f"{spec.ddr_gen} module; {profile.name} needs {profile.ddr_gen}",
        )
    return GateResult("ddr_gen", GateStatus.OK, f"{profile.ddr_gen}")


def _form_factor(spec: RamSpec, profile: FitmentProfile) -> GateResult:
    if spec.form_factor is None:
        return GateResult("form_factor", GateStatus.UNKNOWN, "form factor not stated")
    if spec.form_factor != profile.form_factor:
        return GateResult(
            "form_factor",
            GateStatus.REJECT,
            f"{spec.form_factor} module; {profile.name} needs {profile.form_factor}",
        )
    return GateResult("form_factor", GateStatus.OK, f"{profile.form_factor}")


def _buffered(spec: RamSpec, profile: FitmentProfile) -> GateResult:
    # Buffered (RDIMM/LRDIMM) modules need a server platform; consumer SO-DIMMs are
    # unbuffered, so an unstated value is assumed unbuffered (the overwhelming common case).
    if spec.registered is True:
        return GateResult(
            "buffered", GateStatus.REJECT, "buffered (RDIMM/LRDIMM); needs a server platform"
        )
    return GateResult("buffered", GateStatus.OK, "unbuffered")


def _ecc(spec: RamSpec, profile: FitmentProfile) -> GateResult:
    if spec.ecc is True and not profile.ecc_supported:
        return GateResult(
            "ecc",
            GateStatus.RISK,
            "ECC module on a non-ECC platform: usually runs as non-ECC but not guaranteed; verify",
        )
    return GateResult("ecc", GateStatus.OK, "non-ECC")


def _per_module_capacity(spec: RamSpec, profile: FitmentProfile) -> GateResult:
    cap = spec.capacity_gb_per_module
    if cap is None:
        return GateResult("per_module_capacity", GateStatus.UNKNOWN, "module capacity not stated")
    if cap > profile.max_per_module_gb:
        return GateResult(
            "per_module_capacity",
            GateStatus.REJECT,
            f"{cap} GB/module exceeds the {profile.max_per_module_gb} GB/module max",
        )
    return GateResult("per_module_capacity", GateStatus.OK, f"{cap} GB/module")


def _kit_fit(spec: RamSpec, profile: FitmentProfile) -> GateResult:
    count, total = spec.module_count, spec.total_gb
    if count is None or total is None:
        return GateResult("kit_fit", GateStatus.UNKNOWN, "kit configuration not stated")
    if count > profile.slots:
        return GateResult(
            "kit_fit", GateStatus.REJECT, f"{count}-module kit; only {profile.slots} slots"
        )
    if total > profile.max_total_gb:
        return GateResult(
            "kit_fit",
            GateStatus.REJECT,
            f"{total} GB total exceeds the {profile.max_total_gb} GB max",
        )
    return GateResult("kit_fit", GateStatus.OK, f"{count}x -> {total} GB")


def _dual_channel(spec: RamSpec, profile: FitmentProfile) -> GateResult:
    if spec.module_count == 1 and profile.slots >= 2:
        return GateResult(
            "dual_channel",
            GateStatus.SUBOPTIMAL,
            "single module = single-channel; a matched pair is strongly preferred",
        )
    return GateResult("dual_channel", GateStatus.OK, "dual-channel capable")


def _speed(spec: RamSpec, profile: FitmentProfile) -> GateResult:
    s = spec.speed_mts
    if s is None:
        return GateResult("speed", GateStatus.OK, "speed not stated; runs at platform JEDEC")
    if s < profile.rated_speed_mts:
        return GateResult(
            "speed",
            GateStatus.SUBOPTIMAL,
            f"{s} MT/s, below the platform's rated {profile.rated_speed_mts} MT/s",
        )
    if s > profile.rated_speed_mts:
        return GateResult(
            "speed", GateStatus.OK, f"{s} MT/s downclocks to {profile.rated_speed_mts} MT/s"
        )
    return GateResult("speed", GateStatus.OK, f"{s} MT/s")


def _voltage(spec: RamSpec, profile: FitmentProfile) -> GateResult:
    v = spec.voltage_v
    if v is None or abs(v - profile.voltage_v) <= 0.05:
        return GateResult("voltage", GateStatus.OK, f"{profile.voltage_v} V")
    return GateResult(
        "voltage",
        GateStatus.SUBOPTIMAL,
        f"rated {v} V; will run at platform JEDEC {profile.voltage_v} V",
    )


GATE_FUNCS = (
    _ddr_gen,
    _form_factor,
    _buffered,
    _ecc,
    _per_module_capacity,
    _kit_fit,
    _dual_channel,
    _speed,
    _voltage,
)


def assess(spec: RamSpec, profile: FitmentProfile) -> Assessment:
    """Run every gate and aggregate into a verdict. Total (never raises) for any RamSpec.

    REJECT dominates; else any RISK or any CRITICAL-gate UNKNOWN -> UNVERIFIED; else PASS.
    """
    results = tuple(gate(spec, profile) for gate in GATE_FUNCS)
    if any(r.status is GateStatus.REJECT for r in results):
        verdict = Verdict.REJECT
    elif any(r.status is GateStatus.RISK for r in results) or any(
        r.status is GateStatus.UNKNOWN and r.gate in CRITICAL for r in results
    ):
        verdict = Verdict.UNVERIFIED
    else:
        verdict = Verdict.PASS
    return Assessment(verdict=verdict, gates=results)
