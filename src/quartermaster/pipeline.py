"""The funnel runner -- ties ingest -> evaluation -> a `DigestItem` (P1.4 assembly).

`assemble()` runs ONE extracted listing through the rest of the funnel (fitment + landed cost +
baseline -> surface) and packages a renderable `DigestItem`. `run_pass()` does it over a batch.
Pure + injectable: the LLM, the FX snapshot, and the baseline resolver are all passed in, so the
whole pass is testable without network. `null_extractor` is a deterministic-only LLM (returns
nothing) so the funnel runs on the regex extractor alone when no Anthropic key is available.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .digest import DigestItem
from .evaluation import evaluate
from .fitment import FitmentProfile, RamSpec, assess
from .fx import FxSnapshot
from .ingest import ExtractedListing, LlmExtraction, LlmExtractor, extract_listing
from .listings import ListingSource
from .valuation import Baseline, Currency, LandedCost

# How to get a market reference for a spec (live SerpApi comps, or the bootstrap table).
BaselineResolver = Callable[[RamSpec], Baseline | None]


@dataclass(frozen=True, slots=True)
class RawListing:
    """An un-parsed listing as it arrives (e.g. from a classifieds alert email)."""

    text: str
    title: str = ""
    url: str = ""


def null_extractor(_prompt: str) -> LlmExtraction:
    """Deterministic-only LLM: returns nothing, so the funnel uses the regex extractor alone."""
    return LlmExtraction()


def assemble(
    extracted: ExtractedListing,
    *,
    profile: FitmentProfile,
    fx: FxSnapshot,
    baseline_for: BaselineResolver,
    today: dt.date,
) -> DigestItem | None:
    """Run one extracted listing through fitment + valuation + the surface rule -> `DigestItem`.

    Returns None when there is no price (nothing to value -> not surfaced in a deal-ranked digest).
    Phase-1 defaults: classifieds = EU; an EU + EUR listing is treated as costs-complete (the price
    is the landed cost -- domestic pickup); anything else stays costs-incomplete -> ALERT.
    """
    if extracted.price is None or extracted.currency is None:
        return None
    assessment = assess(extracted.spec, profile)
    landed = LandedCost(price=extracted.price, currency=extracted.currency).eur_cents(fx.rates)
    is_eu = extracted.source is ListingSource.CLASSIFIEDS_EMAIL
    costs_complete = is_eu and extracted.currency is Currency.EUR
    evaluation = evaluate(
        assessment,
        landed,
        baseline_for(extracted.spec),
        is_eu=is_eu,
        costs_complete=costs_complete,
        fx_age_days=fx.age_days(today),
    )
    return DigestItem(
        title=extracted.title,
        url=extracted.url,
        evaluation=evaluation,
        confidence=extracted.confidence,
    )


def run_pass(
    raws: Iterable[RawListing],
    *,
    llm: LlmExtractor,
    profile: FitmentProfile,
    fx: FxSnapshot,
    baseline_for: BaselineResolver,
    today: dt.date,
    source: ListingSource = ListingSource.CLASSIFIEDS_EMAIL,
) -> list[DigestItem]:
    """Extract + assemble a batch of raw listings into digest items (priced ones only)."""
    items: list[DigestItem] = []
    for raw in raws:
        extracted = extract_listing(raw.text, llm=llm, source=source, title=raw.title, url=raw.url)
        item = assemble(extracted, profile=profile, fx=fx, baseline_for=baseline_for, today=today)
        if item is not None:
            items.append(item)
    return items
