"""RAM as a hardware category: how to search for it + how to cold-start price it.

Quartermaster is a generic, fitment-gated deal-hunter; RAM is its first category. This module holds
the bits that are RAM-specific but live OUTSIDE pure compatibility (``fitment.py``) and outside the
category-agnostic valuation engine (``valuation.py``): the search-query builder and the cold-start
EUR/GB bootstrap table. A second category (SSDs, GPUs, ...) adds a sibling module of the same shape;
the generic funnel (evaluate / valuation / serpapi / listings) consumes any of them unchanged.

``RamSpec`` itself stays RAM-specific by design -- it models DDR / ECC / voltage fields that are
meaningless for other categories. Generalisation means MORE category modules, not a renamed spec.
"""

from __future__ import annotations

from decimal import Decimal

from .fitment import DdrGen, RamSpec
from .valuation import Baseline, BaselineTag, to_cents


def query_for(spec: RamSpec) -> str:
    """A Google-Shopping search string for the RAM described by ``spec``."""
    parts: list[str] = []
    if spec.ddr_gen is not None:
        parts.append(spec.ddr_gen.value)
    if spec.speed_mts is not None:
        parts.append(f"{spec.speed_mts}MHz")
    if spec.total_gb is not None:
        parts.append(f"{spec.total_gb}GB")
    if spec.form_factor is not None:
        parts.append(spec.form_factor.value)
    parts.append("RAM")
    return " ".join(parts)


# Cold-start bootstrap EUR/GB by DDR generation (manual; refresh as live comps accrue).
# Deliberately conservative -- only used until enough LIVE comps exist (plan sec.3 cold-start).
BOOTSTRAP_EUR_PER_GB: dict[DdrGen, Decimal] = {
    DdrGen.DDR3: Decimal("1.20"),
    DdrGen.DDR4: Decimal("2.20"),
    DdrGen.DDR5: Decimal("3.50"),
}


def bootstrap_baseline(spec: RamSpec) -> Baseline | None:
    """Cold-start market reference from the EUR/GB table. None if generation or size unknown."""
    if spec.ddr_gen is None or spec.total_gb is None:
        return None
    per_gb = BOOTSTRAP_EUR_PER_GB.get(spec.ddr_gen)
    if per_gb is None:
        return None
    return Baseline(to_cents(per_gb * spec.total_gb), BaselineTag.BOOTSTRAP)
