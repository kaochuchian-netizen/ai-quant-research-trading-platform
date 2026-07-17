#!/usr/bin/env python3
"""Target-scope guard for the six non-07:00 production windows."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, write_snapshot
from app.dashboard.dashboard_url_registry import get_window_archive_path
from app.reports.window_report_contract import all_window_report_contracts


def validate() -> dict:
    expected = {
        "TW": ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"),
        "US": ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"),
    }
    contracts = {(item.market, item.window) for item in all_window_report_contracts()}
    archive_routes = {
        get_window_archive_path(market, window, position)
        for market, windows in expected.items()
        for window in windows
        for position in ("latest", "previous")
    }
    rows = []
    with tempfile.TemporaryDirectory(prefix="ai184-non-regression-") as temporary:
        root = Path(temporary)
        for market, windows in expected.items():
            for window in windows:
                if (market, window) == ("TW", "pre_open_0700"):
                    continue
                payload = {
                    "market": market, "window": window, "runtime_provenance": "scheduled_production",
                    "fixture": False, "validator": False, "validation_only": False,
                    "cards": [{"stock_id": f"{market}-{window}", "action": "觀察"}],
                }
                result = write_snapshot(
                    root, market=market, window=window, effective_trading_date="2099-07-17",
                    generated_at="2099-07-17T12:00:00+08:00", source_payload=payload,
                    status="completed", run_kind="scheduled", run_id=f"ai184-{market}-{window}",
                    effective_batch_time="2099-07-17T12:00:00+08:00",
                )
                rows.append({"market": market, "window": window, "admitted": result.get("written")})
    checks = {
        "window_registry_unchanged": MARKET_WINDOWS == expected,
        "seven_contracts_present": all((market, window) in contracts for market, windows in expected.items() for window in windows),
        "six_non_target_admissions": len(rows) == 6 and all(row["admitted"] is True for row in rows),
        "fourteen_unique_archive_routes": len(archive_routes) == 14,
    }
    return {"ok": all(checks.values()), "checks": checks, "non_target_matrix": rows, "production_modified": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
