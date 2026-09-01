#!/usr/bin/env python3
"""Deterministic AI-DEV-227 TW Sheet watchlist robustness gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.loaders.google_sheet_loader import (
    TWWatchlistSchemaError,
    _extract_tw_stock_ids,
    load_stock_ids_with_provenance,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    checks: list[dict[str, object]] = []

    def check(value: object, name: str) -> None:
        ok = bool(value)
        checks.append({"name": name, "ok": ok})
        if not ok:
            raise AssertionError(name)

    symbols, duplicates = _extract_tw_stock_ids([["stock_id"], ["2330"], ["3293"]])
    check(symbols == ["2330", "3293"] and not duplicates, "normal single stock_id column")

    symbols, _ = _extract_tw_stock_ids([
        ["stock_id", "", "", "notes", ""],
        [" 2330 ", "", "", "", ""],
        ["009816", "", "", "", ""],
        ["00878", "", "", "", ""],
        ["3293", "", "", "", ""],
        ["", "", "", "", ""],
    ])
    check(symbols == ["2330", "009816", "00878", "3293"], "blank headers ignored and leading zeroes preserved")

    symbols, duplicates = _extract_tw_stock_ids([
        ["stock_id", "", ""], ["2330"], ["2330"], [""], ["3293"], ["3293"]
    ])
    check(symbols == ["2330", "3293"] and duplicates == ["2330", "3293"], "duplicates keep first deterministic occurrence")

    try:
        _extract_tw_stock_ids([["name", "", ""], ["台積電", "", ""]])
    except TWWatchlistSchemaError as exc:
        check(str(exc) == "TW_WATCHLIST_STOCK_ID_HEADER_MISSING", "missing required column fails closed")
    else:
        raise AssertionError("missing required column must fail")

    current = ["2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409", "3293"]
    fallback = current[:-1]

    def failed_loader(**_: object) -> list[str]:
        raise TWWatchlistSchemaError("TW_WATCHLIST_SCHEMA_INVALID", observed_symbols=current)

    selected, evidence = load_stock_ids_with_provenance(
        primary_loader=failed_loader,
        fallback_loader=lambda: {
            "stock_ids": fallback,
            "snapshot_id": "tw-old-9",
            "effective_trading_date": "2026-08-28",
            "revision": 1,
            "source_payload_hash": "hash-old-9",
        },
        as_of_date="2026-09-01",
    )
    check(selected == fallback, "fallback remains bounded to admitted snapshot")
    check(evidence["source_status"] == "DEGRADED_STALE_FALLBACK" and evidence["fallback_used"], "fallback cannot report normal status")
    check(evidence["fallback_snapshot_age"] == 4, "fallback age is explicit")
    check(evidence["current_symbol_count"] == 10 and evidence["fallback_symbol_count"] == 9, "current and fallback counts are explicit")
    check(evidence["symbol_count_drift"] == -1 and evidence["symbol_drift_status"] == "DRIFT_DETECTED", "10 versus 9 drift is explicit")
    check(evidence["missing_symbols"] == ["3293"] and evidence["extra_symbols"] == [], "missing 3293 is attributable")

    selected, healthy = load_stock_ids_with_provenance(primary_loader=lambda **_: current)
    check(selected[-1] == "3293" and healthy["source_status"] == "READY" and healthy["stock_count"] == 10, "3293 enters next batch universe without hard coding")
    check(healthy["current_symbol_count"] == 10 and healthy["fallback_symbol_count"] == 0, "healthy source counts remain truthful")

    pipeline = (ROOT / "app/pipelines/pre_open_pipeline.py").read_text(encoding="utf-8")
    check('"stock_universe_evidence": stock_universe_evidence or {}' in pipeline, "runtime artifact preserves universe provenance")
    check('"data_quality_status"' in pipeline and '"degraded"' in pipeline, "fallback report is visibly degraded")

    loader = (ROOT / "app/loaders/google_sheet_loader.py").read_text(encoding="utf-8")
    check("3293" not in loader, "production loader contains no hard-coded 3293")
    check("get_all_records" not in loader.split("def load_tw_stock_ids", 1)[1].split("def load_us_stock_watchlist", 1)[0], "TW loader ignores unrelated duplicate headers")

    result = {
        "schema_version": "validate_ai_dev_227_tw_watchlist_loader_robustness_v1",
        "ok": all(item["ok"] for item in checks),
        "passed": sum(bool(item["ok"]) for item in checks),
        "total": len(checks),
        "checks": checks,
        "safety": {
            "production_rerun": False,
            "sheet_mutation": False,
            "notification_sent": False,
            "trading_executed": False,
            "production_db_mutation": False,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
