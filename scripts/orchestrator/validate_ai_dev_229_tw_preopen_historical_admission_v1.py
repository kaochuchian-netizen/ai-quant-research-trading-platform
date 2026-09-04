#!/usr/bin/env python3
"""Deterministic AI-DEV-229 TW 07:00 historical-admission gate."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.market.historical_storage import inspect_historical_csv
from app.market.tw_symbol_historical_admission import admit_tw_symbols_with_history


PRE_OPEN_PATH = Path("app/pipelines/pre_open_pipeline.py")


def _history() -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-09-01", periods=30)
    return pd.DataFrame({
        "date": dates.date,
        "open": range(100, 130),
        "high": range(101, 131),
        "low": range(99, 129),
        "close": range(100, 130),
        "volume": [1000] * 30,
    })


def main() -> int:
    checks: dict[str, bool] = {}
    source = PRE_OPEN_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    run_function = next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "run_pre_open_pipeline"
    )
    run_source = ast.get_source_segment(source, run_function) or ""
    orchestration_helper = next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_refresh_then_admit_tw_symbols"
    )
    calls = {
        node.func.id
        for node in ast.walk(run_function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    helper_calls = {
        node.func.id
        for node in ast.walk(orchestration_helper)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    checks["preopen_imports_shared_coordinator"] = (
        "from app.market.tw_symbol_historical_admission import admit_tw_symbols_with_history" in source
    )
    checks["preopen_calls_shared_coordinator"] = (
        "_refresh_then_admit_tw_symbols" in calls
        and "admission_coordinator = admission_coordinator or admit_tw_symbols_with_history"
        in (ast.get_source_segment(source, orchestration_helper) or "")
        and "admission_coordinator" in helper_calls
    )
    checks["architecture_rejects_missing_csv_bypass"] = (
        "missing_historical_csv" not in run_source and "os.path.exists(csv_path)" not in run_source
    )
    checks["refresh_precedes_admission_and_analysis"] = (
        run_source.index("_refresh_then_admit_tw_symbols(")
        < run_source.index("for stock_id in stock_ids:")
        and source.index("refresh_status = refresher(")
        < source.index("admitted, diagnostics = admission_coordinator(")
    )
    checks["runtime_persists_admission_diagnostics"] = (
        '"historical_symbol_admission": list(historical_admission or [])' in source
    )
    checks["runtime_does_not_own_notification_delivery"] = (
        "send_reports_in_batches" not in source and "send_line_report" not in source
    )
    checks["cross_market_guardrail"] = "app.us_stock" not in source and '"market": "TW"' in source

    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)

        def inspector(symbol, **kwargs):
            return inspect_historical_csv(symbol, folder=str(folder), **kwargs)

        _history().to_csv(folder / "2330_daily.csv", index=False)
        attempts: list[str] = []

        def bootstrap(symbol, **_):
            attempts.append(symbol)
            if symbol == "4743":
                return {"success": False, "result": "provider_unavailable", "reason": "provider_unavailable"}
            _history().to_csv(folder / f"{symbol}_daily.csv", index=False)
            return {"success": True, "result": "bootstrap_success"}

        admitted, diagnostics = admit_tw_symbols_with_history(
            ["2330", "3293", "4743", "009816"],
            target_date="2026-09-02",
            inspector=inspector,
            bootstrapper=bootstrap,
        )
        by_symbol = {item["symbol"]: item for item in diagnostics}
        checks["new_symbol_bootstrap_admitted"] = (
            "3293" in admitted
            and by_symbol["3293"]["status"] == "ADMITTED"
            and by_symbol["3293"]["readiness_status"] == "HISTORICAL_BOOTSTRAP_REQUIRED"
        )
        checks["existing_valid_csv_is_noop"] = (
            "2330" in admitted
            and "2330" not in attempts
            and by_symbol["2330"]["readiness_status"] == "LIVE_READY"
        )
        checks["bootstrap_failure_isolated"] = (
            "4743" not in admitted
            and {"2330", "3293", "009816"}.issubset(admitted)
            and by_symbol["4743"]["status"] == "HISTORICAL_BOOTSTRAP_FAILED"
            and by_symbol["4743"]["exclusion_stage"] == "historical_data_admission"
        )
        checks["leading_zero_symbol_preserved"] = (
            "009816" in admitted and by_symbol["009816"]["symbol"] == "009816"
        )
        checks["bounded_exclusion_diagnostics"] = all(
            key in by_symbol["4743"]
            for key in (
                "symbol", "exclusion_stage", "exclusion_reason", "historical_path",
                "bootstrap_attempted", "bootstrap_result",
            )
        )

    report = {
        "schema_version": "validate_ai_dev_229_tw_preopen_historical_admission_v1",
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
