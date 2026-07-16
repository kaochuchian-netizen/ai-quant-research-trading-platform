#!/usr/bin/env python3
"""Validate AI-DEV-178 window report contract and manual batch control center."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.dashboard_url_registry import get_window_archive_url, is_legacy_dashboard_url
from app.dashboard.multi_market_dashboard import OUTPUT_DIR, build_pages
from app.reports.window_report_contract import TW_POST_CLOSE_LATEST_URL, all_window_report_contracts, get_window_report_contract, no_send_matrix
from scripts.orchestrator.manual_rerun_single_window import ALLOWED_WINDOWS, ALLOWED_MODE, handle_request, pin_hash

LANDING = OUTPUT_DIR / "index.html"
TW = OUTPUT_DIR / "tw_index.html"
US = OUTPUT_DIR / "us_index.html"

TW_MARKERS = ["07:00 盤前決策", "13:05 盤中變化", "13:35 收盤快照", "15:00 盤後檢討"]
US_MARKERS = ["20:00 美股盤前", "23:00 美股盤中", "06:30 美股檢討"]
LANDING_MARKERS = [
    "手動批次控制中心", "台股手動批次", "美股手動批次",
    "重跑 07:00 盤前", "重跑 13:05 盤中", "重跑 13:35 收盤快照", "重跑 15:00 盤後檢討",
    "重跑 20:00 美股盤前", "重跑 23:00 美股盤中", "重跑 06:30 美股檢討",
    "6 位數字重跑密碼", "不會發送 LINE / Email", "不會執行交易",
]
FORBIDDEN_DASHBOARD_FORM_MARKERS = ["manual-batch-form", "manual-rerun-form", "6 位數字重跑密碼", "確認執行手動批次按鈕"]


def section_sets() -> dict[str, list[str]]:
    return {f"{c.market}:{c.window}": list(c.dashboard_sections) for c in all_window_report_contracts()}


def validate() -> dict[str, object]:
    manifest = build_pages(OUTPUT_DIR)
    errors: list[str] = []
    warnings: list[str] = []
    landing = LANDING.read_text(encoding="utf-8")
    tw = TW.read_text(encoding="utf-8")
    us = US.read_text(encoding="utf-8")

    contracts = all_window_report_contracts()
    by_market = {"TW": [c for c in contracts if c.market == "TW"], "US": [c for c in contracts if c.market == "US"]}
    for contract in contracts:
        route = OUTPUT_DIR / f"dashboard/archive/{contract.market.lower()}/{contract.window}/latest/index.html"
        route_text = route.read_text(encoding="utf-8") if route.exists() else ""
        if f'data-window="{contract.window}"' not in route_text:
            errors.append(f"archive latest renderer missing: {contract.market} {contract.window}")
    if 'data-snapshot-id=' not in tw or 'data-payload-hash=' not in tw:
        errors.append("TW market Dashboard missing active snapshot identity")
    if 'data-snapshot-id=' not in us or 'data-payload-hash=' not in us:
        errors.append("US market Dashboard missing active snapshot identity")
    for marker in LANDING_MARKERS:
        if marker not in landing:
            errors.append(f"Landing marker missing: {marker}")

    for market, rows in by_market.items():
        for left, right in zip(rows, rows[1:]):
            if set(left.dashboard_sections) == set(right.dashboard_sections):
                errors.append(f"{market} windows have identical dashboard sections: {left.window} vs {right.window}")
            if set(left.email_sections) == set(right.email_sections):
                errors.append(f"{market} windows have identical email sections: {left.window} vs {right.window}")
            if set(left.line_summary_scope) == set(right.line_summary_scope):
                errors.append(f"{market} windows have identical line scope: {left.window} vs {right.window}")

    for name, html in {"TW": tw, "US": us}.items():
        for marker in FORBIDDEN_DASHBOARD_FORM_MARKERS:
            if marker in html:
                errors.append(f"{name} dashboard contains full manual control marker: {marker}")
    if "手動批次控制請回到總覽頁" not in tw:
        errors.append("TW dashboard must point manual batch control back to Landing")

    required_backend = [c.window for c in contracts]
    for window in required_backend:
        if window not in ALLOWED_WINDOWS:
            errors.append(f"backend missing manual window: {window}")
        meta = ALLOWED_WINDOWS.get(window, {})
        contract = get_window_report_contract(meta.get("market"), window) if meta else None
        if contract and meta.get("dashboard_url") != contract.dashboard_url:
            errors.append(f"backend dashboard URL mismatch: {window}")
        if contract and not meta.get("backend_command"):
            errors.append(f"backend command missing: {window}")

    mock_hash = pin_hash("426810")
    no_send_rows = []
    for contract in contracts:
        req = {"window": contract.window, "mode": ALLOWED_MODE, "pin": "426810", "confirm_single_window_only": True}
        out = handle_request(req, pin_hash_value=mock_hash, write=False)
        row = {
            "market": contract.market,
            "window": contract.window,
            "dashboard_url": contract.dashboard_url,
            "email": out.get("email_attempted"),
            "line": out.get("line_attempted"),
            "trading": out.get("trading_or_order_executed"),
            "scheduler_changed": out.get("scheduler_changed"),
            "accepted": out.get("accepted"),
            "result": "PASS" if out.get("accepted") and out.get("email_attempted") is False and out.get("line_attempted") is False and out.get("trading_or_order_executed") is False and out.get("scheduler_changed") is False else "FAIL",
        }
        no_send_rows.append(row)
        if row["result"] != "PASS":
            errors.append(f"no-send manual verification failed: {contract.market} {contract.window}")
        if contract.dashboard_url != get_window_archive_url(contract.market, contract.window):
            errors.append(f"canonical archive URL mismatch: {contract.market} {contract.window}")
        if is_legacy_dashboard_url(contract.dashboard_url):
            errors.append(f"legacy dashboard URL in contract: {contract.window}")
        if any(is_legacy_dashboard_url(str(x)) for x in meta.values()) if (meta := ALLOWED_WINDOWS.get(contract.window)) else False:
            errors.append(f"legacy dashboard URL in backend metadata: {contract.window}")

    css_ok = {
        "safe_area": "env(safe-area-inset-left)" in landing,
        "button_touch_size": "min-height:44px" in landing,
        "pin_not_edge": "manual-batch-pin input" in landing and "padding:10px" in landing,
        "mobile_no_horizontal": "overflow-x:hidden" in landing,
        "mobile_single_column": "manual-batch-buttons{grid-template-columns:1fr}" in landing,
    }
    for key, ok in css_ok.items():
        if not ok:
            errors.append(f"Landing mobile CSS missing: {key}")

    return {
        "ok": not errors,
        "schema_version": "window_report_contract_manual_batch_validation_v1",
        "task_id": "AI-DEV-178",
        "manifest_schema_version": manifest.get("schema_version"),
        "window_section_sets": section_sets(),
        "manual_backend_windows": sorted(ALLOWED_WINDOWS),
        "controlled_no_send_matrix": no_send_rows,
        "contract_no_send_matrix": no_send_matrix(),
        "landing_mobile_css": css_ok,
        "errors": errors,
        "warnings": warnings,
        "safety": {
            "email_attempted": False,
            "line_attempted": False,
            "production_pipeline_executed": False,
            "trading_or_order_executed": False,
            "scheduler_changed": False,
            "python3_main_executed": False,
            "secrets_accessed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
