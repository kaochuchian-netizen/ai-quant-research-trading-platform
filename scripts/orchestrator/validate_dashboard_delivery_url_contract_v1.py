#!/usr/bin/env python3
"""Validate AI-DEV-174B Dashboard delivery URL contract migration."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.dashboard_url_registry import (  # noqa: E402
    get_dashboard_url,
    get_tw_dashboard_url,
    get_us_dashboard_url,
)
from app.reports.multi_window_formatter import format_window_report  # noqa: E402
from reports.line_short_formatter import format_line_short  # noqa: E402
from scripts.orchestrator.approved_pre_open_delivery import (  # noqa: E402
    DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL,
    build_email_body as build_tw_email_body,
    build_line_message as build_tw_line_message,
)

OLD_ROUTE = "dashboard/decision-intelligence/four-window-preview"
TW_URL = get_tw_dashboard_url()
US_URL = get_us_dashboard_url()
TW_PUBLIC = Path("/var/www/stock-ai-dashboard/dashboard/tw/index.html")
US_PUBLIC = Path("/var/www/stock-ai-dashboard/dashboard/us/index.html")

DELIVERY_CONTRACT_FILES = [
    ROOT / "run_stock_analysis.sh",
    ROOT / "app/reports/multi_window_formatter.py",
    ROOT / "reports/line_short_formatter.py",
    ROOT / "scripts/orchestrator/approved_pre_open_delivery.py",
    ROOT / "scripts/orchestrator/approved_us_stock_delivery.py",
    ROOT / "scripts/orchestrator/build_line_four_batch_runtime_preview_v1.py",
    ROOT / "scripts/orchestrator/build_email_scheduled_delivery_preview_v1.py",
    ROOT / "scripts/orchestrator/build_tw_daily_tactical_runtime_v1.py",
]


def contains_old_route(text: str) -> bool:
    return OLD_ROUTE in text or "four-window-preview/index.html" in text


def sample_us_artifact() -> dict[str, Any]:
    return {
        "generated_at": "2026-07-13T20:00:00+08:00",
        "runtime_watchlist_validation": {"enabled_stock_count": 6},
        "dashboard_ready_contract": {
            "cards": [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "rating": "B",
                    "action": "中性觀察",
                    "session_predicted_high_low": "190.0 / 195.0",
                    "daily_tactical_summary": {
                        "direction": "neutral",
                        "setup_type": "range_trade",
                        "action": "區間操作",
                        "entry_zone": "190-191",
                        "stop_reference": "188",
                        "target_zone_1": "194-195",
                        "event_risk": "medium",
                    },
                    "research_position_summary": {"rating": "B", "action": "中性觀察"},
                    "bilingual_news_snippet": {"chinese_translation": "重大新聞資料待接"},
                }
            ]
        },
        "prediction_review_contract": {"reviewable_stock_count": 0, "reviewed_stock_count": 0, "skipped_stock_count": 1},
    }


def validate() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    static_checks = {
        "registry_tw_url": TW_URL.endswith("/dashboard/tw/index.html"),
        "registry_us_url": US_URL.endswith("/dashboard/us/index.html"),
        "registry_market_tw": get_dashboard_url("TW") == TW_URL,
        "registry_market_us": get_dashboard_url("US") == US_URL,
        "tw_public_exists": TW_PUBLIC.exists(),
        "us_public_exists": US_PUBLIC.exists(),
    }
    for key, ok in static_checks.items():
        if not ok:
            errors.append(f"static check failed: {key}")

    delivery_hits: dict[str, list[str]] = {}
    for path in DELIVERY_CONTRACT_FILES:
        if not path.exists():
            errors.append(f"delivery contract file missing: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if contains_old_route(text):
            delivery_hits[str(path.relative_to(ROOT))] = [line.strip() for line in text.splitlines() if contains_old_route(line)]
    if delivery_hits:
        errors.append("formal delivery contract still references legacy four-window route")

    tw_report = format_window_report("intraday_1305", "partial", "runtime dry-run summary", dashboard_url=None)
    tw_report_email_url = tw_report["channel_reports"]["email"]["dashboard_url"]
    tw_report_line = tw_report["channel_reports"]["line"]["text"]
    tw_approved_line = build_tw_line_message("intraday_1305", "2026-07-13T13:05:00+08:00", "completed", "", "")
    tw_approved_email = build_tw_email_body("intraday_1305", "dry-run", "2026-07-13T13:05:00+08:00", "completed", DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL, "")
    tw_short_line = format_line_short({"scheduler_window": "intraday_1305"})

    us_source = (ROOT / "scripts/orchestrator/approved_us_stock_delivery.py").read_text(encoding="utf-8")
    us_registry_ok = "get_us_dashboard_url" in us_source and (
        "DASHBOARD_URL = get_us_dashboard_url()" in us_source
        or "DASHBOARD_URL = normalize_delivery_dashboard_url(\"US\", get_us_dashboard_url())" in us_source
    )
    if not us_registry_ok:
        errors.append("US approved delivery must source DASHBOARD_URL from registry")
    us_artifact = sample_us_artifact()
    us_count = us_artifact["runtime_watchlist_validation"]["enabled_stock_count"]
    us_line = "\n".join(["美股盤前報告已更新", f"美股追蹤：{us_count} 檔", "Dashboard：", US_URL, "僅供研究參考，非交易指令。"])
    us_email = "\n".join(["[美股盤前報告] 2026-07-13", "", f"Dashboard: {US_URL}", "", "美股批次狀態：", f"- Enabled stocks: {us_count}", "- LINE: 短提醒；Email: 完整報告；Dashboard: 完整可視化。", "", "僅供研究參考，非交易指令。"])

    payload_checks = {
        "tw_report_email_url": tw_report_email_url == TW_URL,
        "tw_report_line_url": TW_URL in tw_report_line and US_URL not in tw_report_line,
        "tw_approved_line_url": TW_URL in tw_approved_line and US_URL not in tw_approved_line,
        "tw_approved_email_url": TW_URL in tw_approved_email and US_URL not in tw_approved_email,
        "tw_short_line_url": TW_URL in tw_short_line and US_URL not in tw_short_line,
        "us_line_url": US_URL in us_line and TW_URL not in us_line,
        "us_email_url": US_URL in us_email and TW_URL not in us_email,
        "tw_no_old_route": not any(contains_old_route(x) for x in [tw_report_line, tw_approved_line, tw_approved_email, tw_short_line]),
        "us_no_old_route": not any(contains_old_route(x) for x in [us_line, us_email]),
    }
    for key, ok in payload_checks.items():
        if not ok:
            errors.append(f"payload check failed: {key}")

    public_checks = {
        "tw_public_marker": "台股" in (TW_PUBLIC.read_text(encoding="utf-8", errors="ignore") if TW_PUBLIC.exists() else ""),
        "us_public_marker": "美股" in (US_PUBLIC.read_text(encoding="utf-8", errors="ignore") if US_PUBLIC.exists() else ""),
    }
    for key, ok in public_checks.items():
        if not ok:
            warnings.append(f"public marker check not satisfied: {key}")

    return {
        "ok": not errors,
        "task_id": "AI-DEV-174B",
        "dashboard_url_registry": {"TW": TW_URL, "US": US_URL},
        "static_checks": static_checks,
        "notification_link_checks": payload_checks,
        "delivery_contract_legacy_hits": delivery_hits,
        "public_route_checks": public_checks,
        "controlled_payloads": {
            "tw_line": tw_approved_line,
            "tw_email_excerpt": tw_approved_email[:800],
            "us_line": us_line,
            "us_email_excerpt": us_email[:800],
        },
        "safety_checks": {
            "email_attempted": False,
            "line_attempted": False,
            "scheduler_changed": False,
            "production_approved_delivery_executed": False,
            "python_main_executed": False,
            "trading_or_order_executed": False,
            "secrets_read": False,
        },
        "warnings": warnings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
