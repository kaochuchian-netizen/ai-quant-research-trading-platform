#!/usr/bin/env python3
"""Validate AI-DEV-168 US stock dedicated batch lifecycle foundation."""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.us_stock.batch import build_us_stock_batch_artifact, us_stock_batch_input_example
from app.us_stock.constants import US_SCORING_WEIGHTS

TEMPLATE = REPO_ROOT / "templates/us_stock_batch_artifact.example.json"
WATCHLIST_TEMPLATE = REPO_ROOT / "templates/us_stock_watchlist.example.json"
LOADER = REPO_ROOT / "app/loaders/google_sheet_loader.py"
DOC = REPO_ROOT / "docs/runbooks/us_stock_dedicated_batch_lifecycle_v1.md"
REQUIRED_WINDOWS = {
    "us_pre_market_2000": "20:00",
    "us_intraday_2300": "23:00",
    "us_post_close_review_0630": "06:30",
}
SECRET_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"ghp_",
        r"github_pat_",
        r"sk-[A-Za-z0-9_-]{16,}",
        r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}",
        r"api[_-]?key\s*[:=]",
        r"access[_-]?token\s*[:=]",
        r"password\s*[:=]",
        r"BEGIN (RSA|OPENSSH) PRIVATE KEY",
        r"\.env",
    ]
]

def load(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

def finite_or_null(value: Any) -> bool:
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)))

def validate_artifact(data: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != "us_stock_dedicated_batch_lifecycle_v1":
        errors.append(f"{label}: schema_version invalid")
    if data.get("artifact_type") != "us_stock_batch_lifecycle":
        errors.append(f"{label}: artifact_type invalid")
    if data.get("market") != "US" or data.get("currency") != "USD":
        errors.append(f"{label}: market/currency must be US/USD")
    watch = data.get("source_watchlist", {})
    if watch.get("source_sheet") != "工作表2" or watch.get("source_kind") != "google_sheet_us_watchlist":
        errors.append(f"{label}: US watchlist must target 工作表2")
    if watch.get("tw_watchlist_sheet") != "工作表1":
        errors.append(f"{label}: TW watchlist sheet must remain 工作表1")
    for window, time_value in REQUIRED_WINDOWS.items():
        meta = data.get("scheduler_contract", {}).get("windows", {}).get(window)
        if not meta:
            errors.append(f"{label}: missing scheduler window {window}")
        elif meta.get("scheduled_time_tw") != time_value:
            errors.append(f"{label}: {window} must be {time_value} Asia/Taipei")
    sched = data.get("scheduler_contract", {})
    if sched.get("timezone") != "Asia/Taipei" or sched.get("scheduler_runtime_activation") is not False:
        errors.append(f"{label}: scheduler must be Asia/Taipei and not activated")
    sep = data.get("market_separation_policy", {})
    for key in ["us_symbols_to_shioaji", "us_symbols_to_twse", "us_symbols_to_taiwan_chip_modules", "us_symbols_to_taiwan_margin_modules"]:
        if sep.get(key) is not False:
            errors.append(f"{label}: {key} must be false")
    market_data = data.get("market_data_source_contract", {})
    if market_data.get("primary_source") != "yfinance_yahoo" or market_data.get("role") != "market_external_reference":
        errors.append(f"{label}: yfinance/Yahoo must be market external reference")
    if market_data.get("not_official_disclosure_source") is not True or market_data.get("external_api_called") is not False:
        errors.append(f"{label}: yfinance must not be official disclosure and external_api_called=false")
    scoring = data.get("scoring_contract", {})
    if scoring.get("weights") != US_SCORING_WEIGHTS or scoring.get("tw_scoring_formula_reused") is not False:
        errors.append(f"{label}: US scoring weights/governance invalid")
    predictions = data.get("prediction_contract", {}).get("items", [])
    if not predictions:
        errors.append(f"{label}: prediction items required")
    for item in predictions:
        for key in ["current_or_last_price", "predicted_session_high", "predicted_session_low", "predicted_next_session_high", "predicted_next_session_low", "one_month_trend", "three_month_trend", "confidence_score", "prediction_rationale", "prediction_window", "generated_at", "market", "currency"]:
            if key not in item:
                errors.append(f"{label}: prediction item missing {key}")
        if item.get("market") != "US" or item.get("currency") != "USD":
            errors.append(f"{label}: prediction market/currency invalid")
        for key in ["predicted_session_high", "predicted_session_low", "predicted_next_session_high", "predicted_next_session_low", "confidence_score"]:
            if not finite_or_null(item.get(key)):
                errors.append(f"{label}: prediction {key} must be finite or null")
        if item.get("prediction_status") == "insufficient_data" and not item.get("missing_fields"):
            errors.append(f"{label}: insufficient_data prediction requires missing_fields")
    review = data.get("prediction_review_contract", {})
    for key in ["reviewable_stock_count", "reviewed_stock_count", "skipped_stock_count"]:
        if key not in review:
            errors.append(f"{label}: review missing {key}")
    for item in review.get("items", []):
        for key in ["direction_hit", "high_low_error", "confidence_calibration", "rating_action_effectiveness", "pending_policy"]:
            if key not in item:
                errors.append(f"{label}: review item missing {key}")
    for item in data.get("news_company_info_contract", []):
        bilingual = item.get("bilingual_items", [])
        if not bilingual:
            errors.append(f"{label}: bilingual news item required")
        for news in bilingual:
            if "chinese_translation" not in news or "vocabulary" not in news or "investment_reading" not in news:
                errors.append(f"{label}: bilingual news fields missing")
            if "english_headline" not in news and "english_excerpt" not in news:
                errors.append(f"{label}: english headline/excerpt field missing")
    dashboard = data.get("dashboard_ready_contract", {})
    if dashboard.get("market_label") != "美股" or not dashboard.get("cards"):
        errors.append(f"{label}: dashboard-ready US cards required")
    delivery = data.get("delivery_policy", {})
    if delivery.get("line_delivery_allowed") is not False or delivery.get("email_delivery_allowed") is not False or delivery.get("delivery_executed") is not False:
        errors.append(f"{label}: delivery policy must default to no LINE/Email send")
    safety = data.get("safety_policy", {})
    for key in ["external_api_called", "production_pipeline_executed", "line_email_notification_sent", "scheduler_runtime_activation", "db_write", "trading_or_order_executed", "secrets_read", "valid_manual_rerun_triggered"]:
        if safety.get(key) is not False:
            errors.append(f"{label}: safety {key} must be false")
    text = json.dumps(data, ensure_ascii=False)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{label}: secret-like pattern found")
    return errors

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    generated = build_us_stock_batch_artifact(us_stock_batch_input_example(), window="us_pre_market_2000")
    errors += validate_artifact(generated, "generated")
    template = load(TEMPLATE)
    if template is None:
        errors.append("template artifact missing")
    else:
        errors += validate_artifact(template, "template")
    watchlist = load(WATCHLIST_TEMPLATE)
    if watchlist is None:
        errors.append("watchlist template missing")
    else:
        if watchlist.get("source_sheet") != "工作表2" or watchlist.get("source_kind") != "google_sheet_us_watchlist":
            errors.append("watchlist template must identify 工作表2")
        if not all(item.get("market") == "US" and item.get("currency") == "USD" for item in watchlist.get("items", [])):
            errors.append("watchlist template items must be US/USD")
    loader_text = LOADER.read_text(encoding="utf-8") if LOADER.exists() else ""
    for needle in ["TW_SOURCE_WORKSHEET", "US_SOURCE_WORKSHEET", "工作表1", "工作表2", "load_us_stock_watchlist"]:
        if needle not in loader_text:
            errors.append(f"loader missing {needle}")
    for path in [DOC, REPO_ROOT / "scripts/orchestrator/run_us_stock_batch.py", REPO_ROOT / "scripts/orchestrator/build_us_stock_report_artifact.py"]:
        if not path.exists():
            errors.append(f"missing required file {path.relative_to(REPO_ROOT)}")
    result = {
        "ok": not errors,
        "errors": errors,
        "task_id": "AI-DEV-168",
        "windows": REQUIRED_WINDOWS,
        "scheduler_runtime_activation": False,
        "line_email_sent": False,
        "external_api_called": False,
        "summary": {
            "us_loader_sheet": "工作表2",
            "tw_loader_sheet": "工作表1",
            "enabled_sample_symbols": generated.get("source_watchlist", {}).get("symbols", []),
            "dashboard_ready_card_count": len(generated.get("dashboard_ready_contract", {}).get("cards", [])),
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
