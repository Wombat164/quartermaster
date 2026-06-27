"""Classifieds-email ingest orchestration (P1.3b-ii) -- the LLM-enriches half.

Ties the pieces together for ONE classifieds alert-email body:

    assert_llm_allowed(source)            # B1 boundary: only classifieds bodies reach an LLM
    -> guard scan (drop / sanitise)       # injection defense (guard.py)
    -> wrap_untrusted + injected LLM    # Claude structured output (injected; mocked in CI)
    -> cross-validate vs the regex extractor (extract.py)
    -> ExtractedListing(spec, price, confidence, reasons)

Cross-validation is the safety core: on the MONEY-CRITICAL fields (price, total capacity) the LLM
is trusted only when it AGREES with the deterministic read; on conflict the deterministic value
wins and confidence drops to LOW. A field from only one source is MEDIUM; agreement is HIGH -- so
an injected or hallucinated number can at worst yield a LOW-confidence spec, never a trusted one.

The LLM is an injected ``Callable[[str], LlmExtraction]`` -- this module stays network-free and
fully testable; the real Anthropic client is a thin adapter (next).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from .extract import parse_price, parse_spec
from .fitment import DdrGen, FormFactor, RamSpec
from .guard import default_scanner, wrap_untrusted
from .listings import Listing, ListingSource, assert_llm_allowed
from .valuation import Currency


class Confidence(StrEnum):
    HIGH = "high"  # LLM + regex agree on the field
    MEDIUM = "medium"  # only one source had the field (uncorroborated)
    LOW = "low"  # the sources conflict, or the body was flagged unsafe (deterministic-only)


_RANK: dict[Confidence, int] = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}


def _weakest(*cs: Confidence) -> Confidence:
    return min(cs, key=lambda c: _RANK[c])


@dataclass(frozen=True, slots=True)
class LlmExtraction:
    """The model's structured output; all Optional, enum fields are raw strings validated here."""

    ddr_gen: str | None = None
    form_factor: str | None = None
    speed_mts: int | None = None
    capacity_gb_per_module: int | None = None
    module_count: int | None = None
    ecc: bool | None = None
    registered: bool | None = None
    price: Decimal | None = None
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedListing:
    """The result of ingesting one listing: spec + price + a cross-validation confidence."""

    source: ListingSource
    title: str
    url: str
    spec: RamSpec
    price: Decimal | None
    currency: Currency | None
    confidence: Confidence
    reasons: tuple[str, ...] = ()

    def to_listing(self) -> Listing | None:
        """Build a `Listing` for evaluation -- None until a price + currency are known."""
        if self.price is None or self.currency is None:
            return None
        return Listing(
            source=self.source,
            title=self.title,
            url=self.url,
            price=self.price,
            currency=self.currency,
        )


LlmExtractor = Callable[[str], LlmExtraction]


def extract_listing(
    body: str,
    *,
    llm: LlmExtractor,
    source: ListingSource,
    title: str = "",
    url: str = "",
) -> ExtractedListing:
    """Ingest one classifieds body into a cross-validated `ExtractedListing`."""
    assert_llm_allowed(source)  # raises LlmBoundaryViolation for deterministic-only sources
    det = parse_spec(body)
    det_price = parse_price(body)

    scan = default_scanner().scan(body)
    if not scan.safe:
        # never send flagged content to the model -- fall back to the deterministic read
        return ExtractedListing(
            source=source,
            title=title,
            url=url,
            spec=det,
            price=det_price[0] if det_price else None,
            currency=det_price[1] if det_price else None,
            confidence=Confidence.LOW,
            reasons=("body flagged unsafe; deterministic-only", *scan.reasons),
        )

    ext = llm(wrap_untrusted(scan.sanitized))

    ddr, c_ddr, r_ddr = _reconcile("DDR gen", det.ddr_gen, _ddr(ext.ddr_gen))
    form, c_form, r_form = _reconcile("form factor", det.form_factor, _form(ext.form_factor))
    per, count, c_cap, r_cap = _reconcile_capacity(det, ext)
    price, c_price, r_price = _reconcile("price", det_price, _llm_price(ext))

    spec = RamSpec(
        ddr_gen=ddr,
        form_factor=form,
        speed_mts=ext.speed_mts if ext.speed_mts is not None else det.speed_mts,
        capacity_gb_per_module=per,
        module_count=count,
        ecc=ext.ecc if ext.ecc is not None else det.ecc,
        registered=ext.registered if ext.registered is not None else det.registered,
    )
    reasons = tuple(r for r in (r_ddr, r_form, r_cap, r_price) if r is not None)
    return ExtractedListing(
        source=source,
        title=title,
        url=url,
        spec=spec,
        price=price[0] if price else None,
        currency=price[1] if price else None,
        confidence=_weakest(c_ddr, c_form, c_cap, c_price),
        reasons=reasons,
    )


def _reconcile[T](
    name: str, det: T | None, llm: T | None
) -> tuple[T | None, Confidence, str | None]:
    """Cross-validate one field: agreement -> HIGH; single source -> MEDIUM; conflict -> LOW
    (deterministic wins, since the regex is the trustworthy reference for money-critical fields)."""
    if det is not None and llm is not None:
        if det == llm:
            return det, Confidence.HIGH, None
        return det, Confidence.LOW, f"{name} mismatch (regex={det!r} / llm={llm!r})"
    if det is not None:
        return det, Confidence.MEDIUM, None
    if llm is not None:
        return llm, Confidence.MEDIUM, None
    return None, Confidence.HIGH, None


def _reconcile_capacity(
    det: RamSpec, ext: LlmExtraction
) -> tuple[int | None, int | None, Confidence, str | None]:
    """Cross-validate on TOTAL GB (the money value), then prefer the LLM's kit config when totals
    agree (the model parses NxM better than the regex's bare-capacity guess)."""
    det_total = det.total_gb
    llm_total = (
        ext.capacity_gb_per_module * ext.module_count
        if ext.capacity_gb_per_module is not None and ext.module_count is not None
        else None
    )
    if det_total is not None and llm_total is not None:
        if det_total == llm_total:
            return ext.capacity_gb_per_module, ext.module_count, Confidence.HIGH, None
        return (
            det.capacity_gb_per_module,
            det.module_count,
            Confidence.LOW,
            f"capacity mismatch (regex total={det_total}GB / llm total={llm_total}GB)",
        )
    if llm_total is not None:
        return ext.capacity_gb_per_module, ext.module_count, Confidence.MEDIUM, None
    if det_total is not None:
        return det.capacity_gb_per_module, det.module_count, Confidence.MEDIUM, None
    return None, None, Confidence.HIGH, None


def _ddr(s: str | None) -> DdrGen | None:
    if s is None:
        return None
    try:
        return DdrGen(s.upper().replace(" ", ""))
    except ValueError:
        return None


def _form(s: str | None) -> FormFactor | None:
    if s is None:
        return None
    t = s.upper().replace(" ", "").replace("-", "")
    if t == "SODIMM":
        return FormFactor.SODIMM
    if t in ("UDIMM", "DIMM"):
        return FormFactor.UDIMM
    return None


def _llm_price(ext: LlmExtraction) -> tuple[Decimal, Currency] | None:
    if ext.price is None or ext.currency is None or ext.price <= 0:
        return None
    try:
        return ext.price, Currency(ext.currency.upper())
    except ValueError:
        return None
