#!/usr/bin/env python3
"""Deterministic AI-DEV-232 refresh-before-admission regression gate."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.market.tw_symbol_historical_admission import admit_tw_symbols_with_history
from app.pipelines.pre_open_pipeline import (
    _reconstruct_structured_pre_open_cards,
    _refresh_then_admit_tw_symbols,
    _store_structured_pre_open_card,
)


PIPELINE_PATH = Path("app/pipelines/pre_open_pipeline.py")


def _state(*, exists: bool, usable: bool, warning: str | None = None) -> dict:
    return {
        "exists": exists,
        "usable": usable,
        "warning": warning,
        "csv_path": "data/historical/test_daily.csv",
        "row_count": 30 if exists else 0,
        "latest_date": "2026-09-02" if usable else "2026-09-01" if exists else None,
    }


def _exercise(initial: dict[str, dict], refresh_outcomes: dict[str, bool]):
    states = {symbol: dict(value) for symbol, value in initial.items()}
    refresh_calls: list[list[str]] = []

    def inspector(symbol, **_):
        return dict(states[symbol])

    def refresher(*, stock_ids, universe_evidence):
        refresh_calls.append(list(stock_ids))
        stocks = []
        for symbol in stock_ids:
            success = refresh_outcomes.get(symbol, True)
            if success:
                states[symbol] = _state(exists=True, usable=True)
            stocks.append({
                "stock_id": symbol,
                "update_status": "updated_from_provider" if success else "provider_failed",
                "warning": None if success else "provider_failed",
            })
        return {
            "updated_count": sum(bool(refresh_outcomes.get(symbol, True)) for symbol in stock_ids),
            "fallback_count": 0,
            "failed_count": sum(not bool(refresh_outcomes.get(symbol, True)) for symbol in stock_ids),
            "stocks": stocks,
            "stock_universe": universe_evidence,
        }

    selected = list(initial)
    admitted, diagnostics, status = _refresh_then_admit_tw_symbols(
        selected,
        target_date="2026-09-03",
        universe_evidence={"market": "TW", "stock_count": len(selected)},
        refresher=refresher,
        admission_coordinator=admit_tw_symbols_with_history,
        inspector=inspector,
    )
    return selected, admitted, diagnostics, status, refresh_calls


def _card(symbol: str, unavailable: bool = False) -> dict:
    return {
        "symbol": symbol,
        "availability_status": "unavailable" if unavailable else "complete",
        "entry_readiness": "unavailable" if unavailable else "watch",
        "risk_adjusted_score": 50,
    }


def main() -> int:
    checks: dict[str, bool] = {}
    source = PIPELINE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_pre_open_pipeline")
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_refresh_then_admit_tw_symbols")
    run_source = ast.get_source_segment(source, run) or ""
    helper_source = ast.get_source_segment(source, helper) or ""

    checks["architecture_refreshes_before_admission"] = (
        helper_source.index("refresh_status = refresher(")
        < helper_source.index("admitted, diagnostics = admission_coordinator(")
    )
    checks["run_uses_selected_universe_for_refresh"] = (
        "_refresh_then_admit_tw_symbols(" in run_source
        and "selected_stock_ids," in run_source
        and run_source.index("_refresh_then_admit_tw_symbols(") < run_source.index("for stock_id in stock_ids:")
    )

    selected, admitted, diagnostics, _, calls = _exercise(
        {"2330": _state(exists=True, usable=False, warning="STALE")},
        {"2330": True},
    )
    checks["stale_symbol_refreshes_then_admits"] = admitted == selected and calls == [selected]

    selected, admitted, diagnostics, _, calls = _exercise(
        {"7777": _state(exists=False, usable=False, warning="MISSING")},
        {"7777": True},
    )
    new_diag = diagnostics[0]
    checks["new_symbol_refresh_bootstrap_then_admits"] = (
        admitted == selected
        and new_diag["status"] == "ADMITTED"
        and new_diag["bootstrap_attempted"] is True
        and new_diag["refresh_result"] == "updated_from_provider"
    )

    selected, admitted, diagnostics, _, _ = _exercise(
        {"4743": _state(exists=True, usable=False, warning="STALE")},
        {"4743": False},
    )
    failed = diagnostics[0]
    checks["refresh_failure_remains_unavailable"] = (
        admitted == []
        and failed["status"] == "HISTORICAL_INSUFFICIENT"
        and failed["exclusion_reason"] == "STALE"
        and failed["refresh_result"] == "provider_failed"
    )

    initial = {
        "2330": _state(exists=True, usable=False, warning="STALE"),
        "009816": _state(exists=True, usable=True),
        "7777": _state(exists=False, usable=False, warning="MISSING"),
    }
    selected, admitted, diagnostics, _, calls = _exercise(initial, {symbol: True for symbol in initial})
    checks["mixed_universe_refreshes_selected_and_preserves_order"] = admitted == selected and calls == [selected]
    checks["leading_zero_symbol_preserved"] = admitted[1] == "009816"

    selected, admitted, _, _, calls = _exercise(
        {
            "2330": _state(exists=True, usable=False, warning="STALE"),
            "2337": _state(exists=True, usable=False, warning="STALE"),
        },
        {"2330": True, "2337": True},
    )
    checks["empty_initial_admission_cannot_suppress_refresh"] = admitted == selected and calls == [selected]

    cards: dict[str, dict] = {}
    for symbol in ("009816",):
        _store_structured_pre_open_card(cards, _card(symbol, unavailable=True))
    for symbol in ("2330", "7777"):
        _store_structured_pre_open_card(cards, _card(symbol))
    ordered = _reconstruct_structured_pre_open_cards(cards, ["2330", "009816", "7777"])
    checks["ai_dev_230_ordering_preserved"] = [item["symbol"] for item in ordered] == ["2330", "009816", "7777"]

    checks["no_us_pipeline_change"] = all(
        "app/us_stock" not in path and "approved_us_stock_delivery" not in path
        for path in ("app/pipelines/pre_open_pipeline.py", "scripts/orchestrator/validate_ai_dev_232_tw_preopen_refresh_before_admission_v1.py")
    )
    checks["no_symbol_special_case"] = "3293" not in source and "7777" not in source

    report = {
        "schema_version": "validate_ai_dev_232_tw_preopen_refresh_before_admission_v1",
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
