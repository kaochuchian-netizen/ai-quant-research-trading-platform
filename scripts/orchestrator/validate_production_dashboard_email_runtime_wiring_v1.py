#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.dashboard.dashboard_url_registry import get_tw_dashboard_url

PUBLIC_HTML = Path("/var/www/stock-ai-dashboard/dashboard/tw/index.html")
EMAIL_JSON = ROOT / "artifacts/runtime/email_scheduled_delivery_preview_latest.json"
PROD_EXPORT = ROOT / "templates/four_window_dashboard_production_runtime_export.example.json"
SNAPSHOT_INDEX = ROOT / "artifacts/archive/formal_forecast_snapshots/index/formal_forecast_snapshot_index_latest.json"
DASHBOARD_URL = get_tw_dashboard_url()
FORBIDDEN_EMAIL = (
    "pipeline_type",
    "pipeline_run_id",
    "analysis/output",
    "Strategy Ranking",
    "historical CSV",
    "advisory_only",
    "sample artifact",
    "Report content:",
    "stock_analysis_reports_available",
)
FORBIDDEN_DASHBOARD = (
    "預覽版 / 尚未接正式即時資料",
    "Report Content",
    "pipeline_type",
    "pipeline_run_id",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def finite(value: Any) -> bool:
    return not isinstance(value, float) or math.isfinite(value)


def validate() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    html = PUBLIC_HTML.read_text(encoding="utf-8", errors="ignore") if PUBLIC_HTML.exists() else ""
    email = load_json(EMAIL_JSON)
    export = load_json(PROD_EXPORT)
    snapshot = load_json(SNAPSHOT_INDEX)

    if not PUBLIC_HTML.exists():
        errors.append(f"public Dashboard HTML missing: {PUBLIC_HTML}")
    if DASHBOARD_URL not in html:
        warnings.append("public HTML does not include canonical Dashboard URL string; local file path still validated")
    for term in FORBIDDEN_DASHBOARD:
        if term in html:
            errors.append(f"Dashboard main HTML contains forbidden legacy term: {term}")
    if "今日評等資料：" not in html:
        errors.append("Dashboard missing rating/action/score coverage summary")
    if "最新資料時間：" not in html:
        errors.append("Dashboard missing latest data timestamp")
    if html.count("預測方法說明") != 1:
        errors.append(f"Dashboard should show common method explanation once, got {html.count('預測方法說明')}")
    if html.count("風險提醒") > 2:
        errors.append("Dashboard appears to repeat common risk wording too often")
    if "正式評等 / 動作 / 分數覆蓋" not in html:
        errors.append("Dashboard missing production rating/action/score binding wording")

    stocks = export.get("per_stock_summaries") or []
    rating_available = sum(1 for item in stocks if item.get("rating") and item.get("total_score") is not None)
    if stocks and rating_available == 0:
        errors.append("production export has stocks but no rating/score coverage")
    if export.get("latest_runtime_timestamp") and "2026-07-06" in html and "2026-07-09" in str(export.get("latest_runtime_timestamp")):
        errors.append("Dashboard still shows 2026-07-06 while production export has 2026-07-09")

    if not EMAIL_JSON.exists():
        errors.append(f"Email preview missing: {EMAIL_JSON}")
    body = str(email.get("message_body", ""))
    if email.get("is_actual_send") is not False:
        errors.append("Email preview must be dry-run only")
    if email.get("safety_mode") != "dry_run_preview_only":
        errors.append("Email preview safety_mode must be dry_run_preview_only")
    if DASHBOARD_URL not in body:
        errors.append("Email preview missing Dashboard URL")
    if "今日狀態：" not in body:
        errors.append("Email preview missing PM-readable status summary")
    if "本信不包含下單建議" not in body:
        errors.append("Email preview missing no-order/no-trading wording")
    for term in FORBIDDEN_EMAIL:
        if term in body:
            errors.append(f"Email preview contains forbidden raw content: {term}")
    if email.get("actual_email_sent") is not False:
        errors.append("validator expected no actual Email send")
    if email.get("actual_line_sent") is not False:
        errors.append("validator expected no actual LINE send")

    for key in ("prediction_snapshot_count", "actual_outcome_snapshot_count", "review_snapshot_count"):
        if key not in snapshot:
            warnings.append(f"snapshot index missing {key}")
        elif not isinstance(snapshot.get(key), int) or snapshot.get(key) < 0:
            errors.append(f"snapshot index has invalid {key}")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "dashboard_html": str(PUBLIC_HTML),
        "email_preview": str(EMAIL_JSON),
        "rating_coverage": {"available": rating_available, "total": len(stocks)},
        "snapshot_counts": {
            "prediction": snapshot.get("prediction_snapshot_count"),
            "actual_outcome": snapshot.get("actual_outcome_snapshot_count"),
            "review": snapshot.get("review_snapshot_count"),
        },
        "actual_email_sent": False,
        "actual_line_sent": False,
        "scheduler_modified": False,
        "production_pipeline_executed": False,
        "values_included_or_printed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
