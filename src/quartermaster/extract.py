"""Deterministic extraction from classifieds text (the heuristic-first half of P1.3).

Regex-parses a RAM listing's title/body into a `RamSpec` + price, with NO LLM. Two jobs:
1. a standalone extractor for well-structured listings ("Corsair 2x16GB DDR4-3200 SO-DIMM EUR 80"),
2. the cross-validation oracle for the LLM path (P1.3b) -- the model's structured output must
   corroborate these deterministic reads on money-critical fields (price, capacity), else the spec
   is held UNVERIFIED.

Pure + network-free. RAM-aware for now; when a second category lands, extraction generalises behind
a protocol. The engine (valuation / evaluate / serpapi) stays category-clean.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .fitment import DdrGen, FormFactor, RamSpec
from .valuation import Currency

# --- RAM spec ---

_DDR_RE = re.compile(r"DDR\s?([345])", re.IGNORECASE)
_SPEED_MHZ_RE = re.compile(r"(\d{4})\s?(?:MHz|MT/?s)", re.IGNORECASE)
_DDR_DASH_RE = re.compile(r"DDR[345][-\s](\d{4})", re.IGNORECASE)
_KIT_RE = re.compile(r"(\d+)\s?x\s?(\d+)\s?GB", re.IGNORECASE)  # "2x16GB", "2 x 16 GB"
_TOTAL_RE = re.compile(r"(\d+)\s?GB", re.IGNORECASE)
_SODIMM_RE = re.compile(r"so[-\s]?dimm", re.IGNORECASE)
_UDIMM_RE = re.compile(r"\bu?dimm\b", re.IGNORECASE)  # plain DIMM/UDIMM (SO-DIMM checked first)
_ECC_RE = re.compile(r"\becc\b", re.IGNORECASE)
_NONECC_RE = re.compile(r"non[-\s]?ecc", re.IGNORECASE)
_REG_RE = re.compile(r"\b(?:rdimm|lrdimm|registered|buffered)\b", re.IGNORECASE)


def _speed(text: str) -> int | None:
    m = _SPEED_MHZ_RE.search(text) or _DDR_DASH_RE.search(text)
    return int(m.group(1)) if m else None


def _kit(text: str) -> tuple[int | None, int | None]:
    m = _KIT_RE.search(text)
    if m:
        return int(m.group(2)), int(m.group(1))  # (per_module, count)
    m = _TOTAL_RE.search(text)
    if m:
        return int(m.group(1)), 1  # bare capacity -> assume a single module (LLM cross-checks)
    return None, None


def _form(text: str) -> FormFactor | None:
    if _SODIMM_RE.search(text):
        return FormFactor.SODIMM
    if _UDIMM_RE.search(text):
        return FormFactor.UDIMM
    return None


def _ecc(text: str) -> bool | None:
    if _NONECC_RE.search(text):
        return False
    if _ECC_RE.search(text):
        return True
    return None


def parse_spec(text: str) -> RamSpec:
    """Regex-extract a `RamSpec` from listing text. Unparsed fields stay None (-> UNVERIFIED)."""
    ddr = _DDR_RE.search(text)
    per_module, count = _kit(text)
    return RamSpec(
        ddr_gen=DdrGen(f"DDR{ddr.group(1)}") if ddr else None,
        form_factor=_form(text),
        speed_mts=_speed(text),
        capacity_gb_per_module=per_module,
        module_count=count,
        ecc=_ecc(text),
        registered=True if _REG_RE.search(text) else None,
    )


# --- price ---

_CUR: dict[str, Currency] = {
    "€": Currency.EUR,
    "EUR": Currency.EUR,
    "£": Currency.GBP,
    "GBP": Currency.GBP,
    "$": Currency.USD,
    "USD": Currency.USD,
}
_NUM = r"\d[\d.,]*"
_PRICE_RE = re.compile(
    rf"(?P<a>€|£|\$|EUR|GBP|USD)\s?(?P<an>{_NUM})"
    rf"|(?<![A-Za-z])(?P<bn>{_NUM})\s?(?P<b>€|£|\$|EUR|GBP|USD)",  # number not glued to letters
    re.IGNORECASE,
)


def _to_decimal(raw: str) -> Decimal | None:
    s = raw.strip()
    if "," in s and "." in s:
        # the LAST separator is the decimal point; the other is a thousands grouping
        s = (
            s.replace(".", "").replace(",", ".")
            if s.rfind(",") > s.rfind(".")
            else s.replace(",", "")
        )
    elif "," in s:
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_price(text: str) -> tuple[Decimal, Currency] | None:
    """Extract the first money amount + currency from free text. None if none / unparseable."""
    m = _PRICE_RE.search(text)
    if m is None:
        return None
    sym = m.group("a") or m.group("b")
    num = m.group("an") or m.group("bn")
    if sym is None or num is None:
        return None
    value = _to_decimal(num)
    if value is None or value <= 0:
        return None
    return value, _CUR[sym.upper() if sym.isalpha() else sym]
