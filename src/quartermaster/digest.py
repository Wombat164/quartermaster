"""The ranked digest -- Phase-1's only human-facing surface (plan v1, ux-mock #1).

Takes evaluated listings, drops the incompatible ones, ranks the rest (APPROVE-eligible first, then
by deal% within a tier), and renders an ASCII digest with a one-line header scorecard. Pure +
deterministic. ASCII only -- this is a terminal/email surface.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .evaluation import EvaluatedListing, Surface
from .ingest import Confidence

_SURFACE_RANK: dict[Surface, int] = {
    Surface.APPROVE_ELIGIBLE: 0,
    Surface.ALERT_ONLY: 1,
    Surface.DROP: 2,
}


@dataclass(frozen=True, slots=True)
class DigestItem:
    """One evaluated listing ready to render: identity + the funnel result + extraction trust."""

    title: str
    url: str
    evaluation: EvaluatedListing
    confidence: Confidence


def rank(items: Iterable[DigestItem]) -> list[DigestItem]:
    """Drop DROP-surface items; order APPROVE-eligible first, then by deal% descending."""
    visible = [it for it in items if it.evaluation.surface is not Surface.DROP]
    return sorted(
        visible, key=lambda it: (_SURFACE_RANK[it.evaluation.surface], -it.evaluation.deal)
    )


def _eur(cents: int) -> str:
    return f"EUR {cents // 100}.{cents % 100:02d}"


def render_digest(items: Iterable[DigestItem], *, dry_run: bool, fx_age_days: int) -> str:
    """Render the ranked digest. DROP items never appear; reasons explain every non-APPROVE row."""
    ranked = rank(items)
    approve = sum(1 for it in ranked if it.evaluation.surface is Surface.APPROVE_ELIGIBLE)
    alert = len(ranked) - approve
    header = (
        f"QUARTERMASTER digest -- DRY_RUN={str(dry_run).lower()} -- FX {fx_age_days}d old"
        f" -- {len(ranked)} items ({approve} approve-eligible, {alert} alert)"
    )
    lines = [header, "-" * len(header)]
    if not ranked:
        lines.append("(no listings surfaced)")
    for it in ranked:
        ev = it.evaluation
        tag = "APPROVE" if ev.surface is Surface.APPROVE_ELIGIBLE else "ALERT"
        deal = f"{ev.deal * 100:.0f}% below market"
        note = f" -- {ev.reasons[0]}" if ev.reasons else ""
        lines.append(
            f"[{tag:<7}] {deal:<18} {it.title}  landed {_eur(ev.landed_cents)}"
            f"  ({it.confidence.value.upper()}){note}"
        )
        if it.url:
            lines.append(f"          {it.url}")
    return "\n".join(lines)
