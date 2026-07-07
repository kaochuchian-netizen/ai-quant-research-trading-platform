#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = ROOT / "artifacts/runtime/formal_forecast_backtest_report_latest.json"
SECRET_PATTERNS = [
    re.compile(pattern, re.I)
    for pattern in [
        r"ghp_[A-Za-z0-9_]+",
        r"github_pat_[A-Za-z0-9_]+",
        r"sk-[A-Za-z0-9_-]{16,}",
        r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}",
        r"api[_-]?key\s*[:=]",
        r"access[_-]?token\s*[:=]",
        r"password\s*[:=]",
        r"BEGIN (RSA|OPENSSH) PRIVATE KEY",
        r"\.env",
    ]
]
RATE_KEYS = ["same_day_interval_hit_rate", "next_day_interval_hit_rate", "partial_hit_rate", "under_covered_rate", "over_wide_rate", "direction_accuracy", "confidence_calibration_gap"]
ERROR_KEYS = ["high_error_abs_mean", "low_error_abs_mean", "high_error_pct_mean", "low_error_pct_mean", "interval_width_pct_mean"]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_rate(name: str, value: Any, errors: list[str]) -> None:
    if value is None:
        return
    if not finite(value) or float(value) < -100 or float(value) > 100:
        errors.append(f"{name} must be null or finite percent")


def validate_non_negative(name: str, value: Any, errors: list[str]) -> None:
    if value is None:
        return
    if not finite(value) or float(value) < 0:
        errors.append(f"{name} must be null or non-negative")


def validate_report(report: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required = ["schema_version", "artifact_type", "task_id", "generated_at", "method_under_test", "backtest_window", "stock_universe_count", "metrics", "per_stock_results", "insufficient_data", "calibration_analysis", "source_evidence", "safety_policy"]
    for key in required:
        if key not in report:
            errors.append(f"missing required key: {key}")
    if report.get("schema_version") != "formal_forecast_backtest_report_v1":
        errors.append("schema_version mismatch")
    if report.get("artifact_type") != "formal_forecast_backtest_report":
        errors.append("artifact_type must be formal_forecast_backtest_report")
    if report.get("method_under_test") != "deterministic_baseline_v1":
        errors.append("method_under_test must be deterministic_baseline_v1")
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    metric_required = ["same_day_interval_hit_rate", "next_day_interval_hit_rate", "high_error_abs_mean", "low_error_abs_mean", "high_error_pct_mean", "low_error_pct_mean", "interval_width_pct_mean", "over_wide_rate", "under_covered_rate", "direction_accuracy", "confidence_bucket_hit_rate", "confidence_calibration_gap", "per_stock_hit_rate", "per_trend_regime_hit_rate", "per_volatility_regime_hit_rate"]
    for key in metric_required:
        if key not in metrics:
            errors.append(f"missing metric: {key}")
    for key in RATE_KEYS:
        validate_rate(key, metrics.get(key), errors)
    for key in ERROR_KEYS:
        validate_non_negative(key, metrics.get(key), errors)
    if not isinstance(report.get("per_stock_results"), list) or not report.get("per_stock_results"):
        errors.append("per_stock_results must be a non-empty list")
    for row in report.get("per_stock_results", []):
        if not isinstance(row, dict):
            errors.append("per_stock_results entries must be objects")
            continue
        if not row.get("stock_id"):
            errors.append("per_stock_results entry missing stock_id")
        validate_rate(f"per_stock {row.get('stock_id')} hit", row.get("same_day_interval_hit_rate"), errors)
        validate_non_negative(f"per_stock {row.get('stock_id')} high_error_abs_mean", row.get("high_error_abs_mean"), errors)
    buckets = metrics.get("confidence_bucket_hit_rate")
    if not isinstance(buckets, list) or len(buckets) != 3:
        errors.append("confidence_bucket_hit_rate must contain low/medium/medium_high buckets")
    else:
        names = {row.get("confidence_bucket") for row in buckets if isinstance(row, dict)}
        if names != {"low", "medium", "medium_high"}:
            errors.append("confidence buckets must be low, medium, medium_high")
        for row in buckets:
            if isinstance(row, dict):
                validate_rate(f"bucket {row.get('confidence_bucket')} hit_rate", row.get("hit_rate"), errors)
                if row.get("status") not in {"ok", "insufficient_sample_size"}:
                    errors.append("confidence bucket status must be ok or insufficient_sample_size")
    cal = report.get("calibration_analysis") if isinstance(report.get("calibration_analysis"), dict) else {}
    if not cal.get("recommendations"):
        errors.append("calibration recommendations must exist")
    for rec in cal.get("recommendations", []):
        if not isinstance(rec, dict):
            errors.append("recommendations must be objects")
            continue
        if rec.get("production_formula_changed") is not False:
            errors.append("recommendation must not change production formula")
    safety = report.get("safety_policy") if isinstance(report.get("safety_policy"), dict) else {}
    expected_false = ["production_forecast_engine_mutated", "production_rating_action_confidence_weight_mutated", "db_write", "notification_sent", "scheduler_modified", "python_main_executed", "trading_or_order_executed", "secrets_read", "external_credentialed_api_called"]
    for key in expected_false:
        if safety.get(key) is not False:
            errors.append(f"safety_policy.{key} must be false")
    if safety.get("no_fake_metrics") is not True:
        errors.append("safety_policy.no_fake_metrics must be true")
    if safety.get("insufficient_data_explicit") is not True:
        errors.append("safety_policy.insufficient_data_explicit must be true")
    text = json.dumps(report, ensure_ascii=False, sort_keys=True)
    if "NaN" in text or "Infinity" in text:
        errors.append("report must not contain NaN or Infinity")
    secret_hits = sum(1 for pattern in SECRET_PATTERNS if pattern.search(text))
    if secret_hits:
        errors.append("secret-like pattern hit")
    if metrics.get("eligible_sample_count") == 0:
        warnings.append("eligible_sample_count is zero; report is explicit insufficient_data only")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate formal forecast backtest report V1.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    report = load(args.report)
    errors, warnings = validate_report(report)
    result = {"ok": not errors, "task_id": "AI-DEV-153", "report": str(args.report), "errors": errors, "warnings": warnings, "summary": {"artifact_type": report.get("artifact_type"), "method_under_test": report.get("method_under_test"), "stock_universe_count": report.get("stock_universe_count"), "eligible_sample_count": (report.get("metrics") or {}).get("eligible_sample_count"), "same_day_interval_hit_rate": (report.get("metrics") or {}).get("same_day_interval_hit_rate"), "next_day_interval_hit_rate": (report.get("metrics") or {}).get("next_day_interval_hit_rate"), "recommendation_count": len(((report.get("calibration_analysis") or {}).get("recommendations") or []))}, "side_effects": {"files_modified": False, "db_write": False, "notification_sent": False, "production_pipeline_executed": False, "python_main_executed": False, "trading_or_order_executed": False, "secrets_read": False}}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
