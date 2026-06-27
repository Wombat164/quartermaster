"""RAM category glue: the search-query builder + the cold-start EUR/GB bootstrap baseline."""

from __future__ import annotations

from quartermaster.fitment import DdrGen, FormFactor, RamSpec
from quartermaster.ram import BOOTSTRAP_EUR_PER_GB, bootstrap_baseline, query_for
from quartermaster.valuation import BaselineTag


def test_query_for_builds_search_string() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        speed_mts=3200,
        capacity_gb_per_module=32,
        module_count=2,
    )
    assert query_for(spec) == "DDR4 3200MHz 64GB SO-DIMM RAM"


def test_bootstrap_ddr4_64gb() -> None:
    spec = RamSpec(
        ddr_gen=DdrGen.DDR4,
        form_factor=FormFactor.SODIMM,
        capacity_gb_per_module=32,
        module_count=2,
    )
    b = bootstrap_baseline(spec)
    assert b is not None
    assert b.market_ref_cents == 14080  # 2.20 EUR/GB * 64 GB
    assert b.tag is BaselineTag.BOOTSTRAP


def test_bootstrap_unknown_returns_none() -> None:
    assert bootstrap_baseline(RamSpec(ddr_gen=DdrGen.DDR4)) is None  # no size
    assert bootstrap_baseline(RamSpec(capacity_gb_per_module=16, module_count=2)) is None  # no gen


def test_bootstrap_table_covers_all_ddr_gens() -> None:
    # Adding a DdrGen without a table row would silently give that generation no valuation.
    assert set(BOOTSTRAP_EUR_PER_GB) == set(DdrGen)
