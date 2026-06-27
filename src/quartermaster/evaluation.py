"""Evaluation -- the funnel before the click (plan sec.4 + architecture sec.2).

Composes the two pure cores -- fitment (does it fit?) and valuation (is it a deal?) -- into one
surfaced result with a SURFACE decision. Phase-1 is alert-only: ``APPROVE_ELIGIBLE`` means "would
be approvable" (there is no button yet), everything uncertain is ``ALERT_ONLY``, and a hard-
incompatible listing is ``DROP``. Pure + network-free -- the first place fitment and valuation are
exercised together.

Surface rule (plan): ``DROP`` if the fitment verdict is REJECT; else ``APPROVE_ELIGIBLE`` only when
ALL of {verdict PASS, baseline LIVE, EU seller, landed cost complete, FX snapshot fresh} hold;
otherwise ``ALERT_ONLY`` -- the fail-safe, a human looks. The reasons that demoted it travel with
the result so the digest can explain itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from .fitment import Assessment, Verdict
from .valuation import Baseline, BaselineTag, deal_pct

# ECB publishes daily; a snapshot older than this is treated as stale -> ALERT (plan sec.3).
MAX_FX_AGE_DAYS = 4


class Surface(StrEnum):
    APPROVE_ELIGIBLE = "approve_eligible"  # PASS + live baseline + EU + costs known + fresh FX
    ALERT_ONLY = "alert_only"  # surfaced for a human; never auto-actioned (the Phase-1 default)
    DROP = "drop"  # hard-incompatible; not surfaced


@dataclass(frozen=True, slots=True)
class EvaluatedListing:
    """One listing run through the full funnel: fit + value + a surface decision with reasons."""

    assessment: Assessment
    landed_cents: int
    baseline: Baseline | None
    deal: Decimal
    surface: Surface
    reasons: tuple[str, ...] = ()


def evaluate(
    assessment: Assessment,
    landed_cents: int,
    baseline: Baseline | None,
    *,
    is_eu: bool,
    costs_complete: bool,
    fx_age_days: int,
) -> EvaluatedListing:
    """Compose fitment + valuation into a surfaced result. Pure; no network, no LLM."""
    deal = deal_pct(landed_cents, baseline.market_ref_cents) if baseline is not None else Decimal(0)
    surface, reasons = _surface(
        assessment,
        baseline,
        is_eu=is_eu,
        costs_complete=costs_complete,
        fx_age_days=fx_age_days,
    )
    return EvaluatedListing(assessment, landed_cents, baseline, deal, surface, reasons)


def _surface(
    assessment: Assessment,
    baseline: Baseline | None,
    *,
    is_eu: bool,
    costs_complete: bool,
    fx_age_days: int,
) -> tuple[Surface, tuple[str, ...]]:
    if assessment.verdict is Verdict.REJECT:
        return Surface.DROP, assessment.blockers or ("incompatible",)
    reasons: list[str] = []
    if assessment.verdict is not Verdict.PASS:
        reasons.append("fitment unverified")
    if baseline is None or baseline.tag is not BaselineTag.LIVE:
        reasons.append("no live market baseline")
    if not is_eu:
        reasons.append("non-EU seller")
    if not costs_complete:
        reasons.append("landed cost incomplete")
    if fx_age_days > MAX_FX_AGE_DAYS:
        reasons.append(f"FX snapshot stale ({fx_age_days}d)")
    if reasons:
        return Surface.ALERT_ONLY, tuple(reasons)
    return Surface.APPROVE_ELIGIBLE, ()
