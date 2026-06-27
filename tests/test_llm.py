"""Anthropic adapter: parse a forced tool-call into LlmExtraction, defensively coercing values.
Uses a fake `create` callable -- no SDK client, no network."""

from __future__ import annotations

from decimal import Decimal

from quartermaster.ingest import LlmExtraction
from quartermaster.llm import CreateFn, build_extractor


class _Block:
    def __init__(self, type_: str, inp: dict[str, object]) -> None:
        self.type = type_
        self.input = inp


class _Resp:
    def __init__(self, content: list[object]) -> None:
        self.content = content


def _returns(inp: dict[str, object]) -> CreateFn:
    def create(**_kwargs: object) -> object:
        return _Resp([_Block("tool_use", inp)])

    return create


def test_parses_tool_use_into_extraction() -> None:
    create = _returns(
        {
            "ddr_gen": "DDR4",
            "form_factor": "SO-DIMM",
            "speed_mts": 3200,
            "capacity_gb_per_module": 16,
            "module_count": 2,
            "ecc": False,
            "price": 80,
            "currency": "EUR",
        }
    )
    assert build_extractor(create=create)("WRAPPED") == LlmExtraction(
        ddr_gen="DDR4",
        form_factor="SO-DIMM",
        speed_mts=3200,
        capacity_gb_per_module=16,
        module_count=2,
        ecc=False,
        price=Decimal("80"),
        currency="EUR",
    )


def test_coerces_string_and_float_numbers() -> None:
    ext = build_extractor(create=_returns({"speed_mts": "3200", "price": 79.99}))("x")
    assert ext.speed_mts == 3200
    assert ext.price == Decimal("79.99")


def test_invalid_fields_become_none() -> None:
    ext = build_extractor(create=_returns({"speed_mts": "fast", "ddr_gen": 123, "ecc": "yes"}))("x")
    assert ext.speed_mts is None
    assert ext.ddr_gen is None
    assert ext.ecc is None


def test_no_tool_use_returns_empty() -> None:
    def create(**_kwargs: object) -> object:
        return _Resp([_Block("text", {})])  # not a tool_use block

    assert build_extractor(create=create)("x") == LlmExtraction()


def test_forces_the_emit_tool_and_passes_the_wrapped_prompt() -> None:
    captured: dict[str, object] = {}

    def create(**kwargs: object) -> object:
        captured.update(kwargs)
        return _Resp([_Block("tool_use", {"ddr_gen": "DDR4"})])

    build_extractor(create=create, model="m")("WRAPPED BODY")
    assert captured["model"] == "m"
    assert captured["tool_choice"] == {"type": "tool", "name": "emit_listing"}
    assert captured["messages"] == [{"role": "user", "content": "WRAPPED BODY"}]
