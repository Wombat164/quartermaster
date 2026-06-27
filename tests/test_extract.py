"""Deterministic extraction: regex -> RamSpec + price. Parser-class, so totality is a property
(never raises on arbitrary text) on top of worked examples."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from quartermaster.extract import parse_price, parse_spec
from quartermaster.fitment import DdrGen, FormFactor
from quartermaster.valuation import Currency

# --- spec ---


def test_parse_full_kit() -> None:
    spec = parse_spec("Corsair Vengeance 2x16GB DDR4-3200 SO-DIMM")
    assert spec.ddr_gen is DdrGen.DDR4
    assert spec.form_factor is FormFactor.SODIMM
    assert spec.speed_mts == 3200
    assert spec.capacity_gb_per_module == 16
    assert spec.module_count == 2


def test_parse_single_stick() -> None:
    spec = parse_spec("Crucial 16GB DDR4 3200MHz SODIMM")
    assert spec.capacity_gb_per_module == 16
    assert spec.module_count == 1
    assert spec.speed_mts == 3200


def test_parse_ddr5_mts() -> None:
    spec = parse_spec("Kingston 2x32GB DDR5 5600 MT/s")
    assert spec.ddr_gen is DdrGen.DDR5
    assert spec.speed_mts == 5600
    assert spec.capacity_gb_per_module == 32
    assert spec.module_count == 2


def test_parse_ecc_and_registered() -> None:
    spec = parse_spec("Samsung 32GB DDR4 ECC RDIMM 2666MHz")
    assert spec.ecc is True
    assert spec.registered is True


def test_parse_non_ecc() -> None:
    assert parse_spec("16GB DDR4 non-ECC SODIMM").ecc is False


def test_parse_unknown_fields_are_none() -> None:
    spec = parse_spec("RAM for sale, good condition, pickup only")
    assert spec.ddr_gen is None
    assert spec.capacity_gb_per_module is None
    assert spec.module_count is None
    assert spec.speed_mts is None


@given(st.text())
def test_parse_spec_never_raises(text: str) -> None:
    parse_spec(text)  # totality: any string yields a RamSpec, never an exception


# --- price ---


def test_parse_price_symbol_before() -> None:
    assert parse_price("Price: €80") == (Decimal("80"), Currency.EUR)


def test_parse_price_code_after() -> None:
    assert parse_price("80 EUR for the kit") == (Decimal("80"), Currency.EUR)


def test_parse_price_european_decimal() -> None:
    assert parse_price("€ 79,99") == (Decimal("79.99"), Currency.EUR)


def test_parse_price_usd_and_gbp() -> None:
    assert parse_price("$120.00 shipped") == (Decimal("120.00"), Currency.USD)
    assert parse_price("100 GBP") == (Decimal("100"), Currency.GBP)


def test_parse_price_thousands_separator() -> None:
    assert parse_price("€1.299,00") == (Decimal("1299.00"), Currency.EUR)


def test_parse_price_none_when_absent() -> None:
    assert parse_price("RAM for sale, make an offer") is None


@given(st.text())
def test_parse_price_total_and_positive(text: str) -> None:
    result = parse_price(text)  # totality: never raises
    if result is not None:
        value, _currency = result
        assert value > 0
