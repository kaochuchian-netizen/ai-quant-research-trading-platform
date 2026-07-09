#!/usr/bin/env python3
"""Validate AI-DEV-165 approved delivery nonblocking wiring and dashboard prediction binding."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

APPROVED_DELIVERY = REPO_ROOT / "scripts/orchestrator/approved_pre_open_delivery.py"
DASHBOARD_ROUTE = REPO_ROOT / "app/dashboard/four_window_route_integration.py"
FORMAL_PREDICTION = REPO_ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"

REQUIRED_DASHBOARD_LABELS = [
    "今日預測區間",
    "隔日預測區間",
    "1 個月趨勢",
    "信心分數",
    "重大新聞資料待接",
]
FORBIDDEN_VALID_ARTIFACT_FALLBACKS = [
    "尚未找到正式 prediction runtime artifact，不產生假預測",
    "資料尚未完成，不產生假預測",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _daily_prediction_section(html: str) -> str:
    marker = "每日股價預測資料狀態"
    start = html.find(marker)
    if start < 0:
        return ""
    next_section = html.find("<section", start + len(marker))
    if next_section < 0:
        next_section = html.find("</main>", start)
    return html[start: next_section if next_section > start else len(html)]


def validate() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    approved_source = APPROVED_DELIVERY.read_text(encoding="utf-8")
    dashboard_source = DASHBOARD_ROUTE.read_text(encoding="utf-8")

    timezone_ok = "from datetime import datetime, timezone" in approved_source or "import timezone" in approved_source
    checks["timezone_import_safe"] = timezone_ok
    if not timezone_ok:
        errors.append("approved_pre_open_delivery.py must import timezone before using timezone.utc")

    guard_markers = {
        "post_delivery_artifact_wiring_call": "post_delivery_artifact_wiring(window_id=args.window, generated_at=generated_at)" in approved_source,
        "nonblocking_except": "failed_non_blocking" in approved_source and "except Exception as exc" in approved_source,
        "delivery_continues": "delivery_continues" in approved_source,
        "line_email_delivery_not_blocked": "line_email_delivery_not_blocked" in approved_source,
        "error_type": "error_type" in approved_source,
        "error_message": "error_message" in approved_source,
    }
    checks["approved_delivery_nonblocking_guard"] = guard_markers
    for name, ok in guard_markers.items():
        if not ok:
            errors.append(f"approved delivery nonblocking guard missing marker: {name}")

    result_payload_ok = "\"post_run_artifact_wiring\": post_run_artifacts" in approved_source
    checks["approved_delivery_result_records_post_run_artifact_wiring"] = result_payload_ok
    if not result_payload_ok:
        errors.append("delivery result must record post_run_artifact_wiring status")

    timeout_guard_preserved = "timeout_delivery_artifact" in approved_source and "late_delivery_suppressed" in approved_source
    checks["timeout_and_late_delivery_guard_preserved"] = timeout_guard_preserved
    if not timeout_guard_preserved:
        errors.append("timeout / late delivery guard markers must remain present")

    dashboard_fallback_markers = {
        "fallback_reads_formal_prediction_runtime_latest": "formal_prediction_runtime_latest.json" in dashboard_source,
        "uses_repo_root_for_fallback": "REPO_ROOT / 'artifacts/runtime/formal_prediction_runtime_latest.json'" in dashboard_source,
        "requires_formal_prediction_artifact_type": "artifact.get('artifact_type') == 'formal_prediction_runtime'" in dashboard_source,
        "rejects_example_artifact": "artifact.get('is_example') is False" in dashboard_source,
        "requires_nonempty_stocks": "and artifact.get('stocks')" in dashboard_source,
    }
    checks["dashboard_formal_prediction_fallback_source_markers"] = dashboard_fallback_markers
    for name, ok in dashboard_fallback_markers.items():
        if not ok:
            errors.append(f"dashboard formal prediction fallback missing marker: {name}")

    artifact = _load_json(FORMAL_PREDICTION) if FORMAL_PREDICTION.exists() else {}
    valid_artifact = (
        artifact.get("artifact_type") == "formal_prediction_runtime"
        and artifact.get("is_example") is False
        and isinstance(artifact.get("stocks"), list)
        and len(artifact.get("stocks") or []) > 0
    )
    checks["formal_prediction_runtime_artifact_valid_for_binding"] = {
        "path": str(FORMAL_PREDICTION),
        "valid": valid_artifact,
        "stock_count": len(artifact.get("stocks") or []) if isinstance(artifact.get("stocks"), list) else 0,
    }
    if not valid_artifact:
        errors.append("formal_prediction_runtime_latest.json must be a non-example formal_prediction_runtime with stocks")

    try:
        from app.dashboard import four_window_route_integration as route

        prediction_html = route.prediction_cards({})
        route_html = route.render_route_html({}, "")
        section = _daily_prediction_section(route_html)
        labels_present = {label: (label in prediction_html or label in section) for label in REQUIRED_DASHBOARD_LABELS}
        checks["rendered_prediction_labels"] = labels_present
        for label, ok in labels_present.items():
            if not ok:
                errors.append(f"dashboard prediction render missing label: {label}")
        fallback_hits = [phrase for phrase in FORBIDDEN_VALID_ARTIFACT_FALLBACKS if phrase in section]
        checks["valid_artifact_daily_prediction_forbidden_fallback_hits"] = fallback_hits
        if valid_artifact and fallback_hits:
            errors.append("daily prediction section must not show no-fake-prediction fallback when valid artifact exists")
        card_count = prediction_html.count("stock-forecast-card")
        checks["rendered_prediction_card_count"] = card_count
        if valid_artifact and card_count < len(artifact.get("stocks") or []):
            errors.append("dashboard prediction fallback must render one stock forecast card per formal prediction stock")
        if valid_artifact:
            missing_stock_labels = [
                str(stock.get("stock_id"))
                for stock in artifact.get("stocks", [])
                if isinstance(stock, dict) and str(stock.get("stock_id")) not in prediction_html
            ]
            checks["rendered_prediction_missing_stock_labels"] = missing_stock_labels
            if missing_stock_labels:
                errors.append("dashboard prediction fallback missing stock labels: " + ", ".join(missing_stock_labels))
    except Exception as exc:  # pragma: no cover - validator diagnostic path
        errors.append(f"dashboard render import failed: {exc.__class__.__name__}: {exc}")

    safety = {
        "external_api_called": False,
        "secrets_read": False,
        "db_write": False,
        "line_sent": False,
        "email_sent": False,
        "production_pipeline_executed": False,
        "python_main_executed": False,
        "scheduler_modified": False,
        "trading_or_order_executed": False,
    }
    return {
        "schema_version": "approved_delivery_artifact_wiring_nonblocking_dashboard_prediction_binding_validator_v1",
        "task_id": "AI-DEV-165",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "safety": safety,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-165 runtime hotfix formalization.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
