#!/usr/bin/env python3
"""Deterministic AI-DEV-230 TW 07:00 structured-card ordering gate."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.reports.tw_pre_open_structured import aggregate


PIPELINE_PATH = Path("app/pipelines/pre_open_pipeline.py")


def _load_pipeline_helpers():
    source = PIPELINE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {
        "_store_structured_pre_open_card",
        "_reconstruct_structured_pre_open_cards",
    }
    definitions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    if {node.name for node in definitions} != wanted:
        raise AssertionError("missing_pre_open_ordering_helpers")
    namespace: dict = {}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(PIPELINE_PATH), "exec"), namespace)
    return (
        namespace["_reconstruct_structured_pre_open_cards"],
        namespace["_store_structured_pre_open_card"],
    )


_reconstruct_structured_pre_open_cards, _store_structured_pre_open_card = _load_pipeline_helpers()


PRODUCTION_ORDER = [
    "2330", "009816", "2337", "2353", "6873",
    "4743", "2305", "00878", "1409", "3293",
]


def _card(symbol: str, *, unavailable: bool = False) -> dict:
    return {
        "symbol": symbol,
        "availability_status": "unavailable" if unavailable else "complete",
        "entry_readiness": "unavailable" if unavailable else "watch",
        "risk_adjusted_score": 50,
    }


def _ordered(selected: list[str], unavailable: set[str]) -> list[dict]:
    by_symbol: dict[str, dict] = {}
    # Model production collection: exclusions first, admitted analysis cards later.
    for symbol in selected:
        if symbol in unavailable:
            _store_structured_pre_open_card(by_symbol, _card(symbol, unavailable=True))
    for symbol in selected:
        if symbol not in unavailable:
            _store_structured_pre_open_card(by_symbol, _card(symbol))
    return _reconstruct_structured_pre_open_cards(by_symbol, selected)


def _fails(error: str, operation) -> bool:
    try:
        operation()
    except ValueError as exc:
        return str(exc) == error
    return False


def main() -> int:
    checks: dict[str, bool] = {}

    cases = {
        "all_symbols_admitted": set(),
        "unavailable_at_beginning": {PRODUCTION_ORDER[0]},
        "unavailable_in_middle": {PRODUCTION_ORDER[4]},
        "multiple_unavailable_interleaved": {"009816", "00878"},
        "unavailable_at_end": {PRODUCTION_ORDER[-1]},
    }
    for name, unavailable in cases.items():
        ordered = _ordered(PRODUCTION_ORDER, unavailable)
        checks[name] = [item["symbol"] for item in ordered] == PRODUCTION_ORDER
        checks[f"{name}_strict_aggregate"] = bool(aggregate(ordered, PRODUCTION_ORDER))

    leading = ["009816", "2330", "00878"]
    checks["leading_zero_symbols_preserved"] = [
        item["symbol"] for item in _ordered(leading, {"00878"})
    ] == leading

    generic = ["2330", "7777", "00878"]
    checks["generic_new_equity_is_not_special_cased"] = [
        item["symbol"] for item in _ordered(generic, {"00878"})
    ] == generic

    duplicate_map = {"2330": _card("2330")}
    checks["duplicate_card_fails_closed"] = _fails(
        "duplicate_structured_pre_open_symbol",
        lambda: _store_structured_pre_open_card(duplicate_map, _card("2330")),
    )
    checks["missing_card_fails_closed"] = _fails(
        "missing_structured_pre_open_symbol",
        lambda: _reconstruct_structured_pre_open_cards({"2330": _card("2330")}, ["2330", "2337"]),
    )
    checks["unexpected_card_fails_closed"] = _fails(
        "unexpected_structured_pre_open_symbol",
        lambda: _reconstruct_structured_pre_open_cards(
            {"2330": _card("2330"), "9999": _card("9999")}, ["2330"]
        ),
    )
    checks["strict_aggregator_order_guard_retained"] = _fails(
        "structured_pre_open_symbol_order_mismatch",
        lambda: aggregate([_card("2337"), _card("2330")], ["2330", "2337"]),
    )
    checks["production_fixture_exact_order"] = [
        item["symbol"] for item in _ordered(PRODUCTION_ORDER, {"009816", "00878"})
    ] == PRODUCTION_ORDER

    report = {
        "schema_version": "validate_ai_dev_230_tw_preopen_structured_card_ordering_v1",
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "ok": all(checks.values()),
        "production_mutation": False,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
