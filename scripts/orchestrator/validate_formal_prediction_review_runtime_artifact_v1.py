#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, re, sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates/formal_prediction_review_runtime_artifact.example.json"
RUNTIME = ROOT / "artifacts/runtime/formal_prediction_review_runtime_latest.json"
REQUIRED_TOP = ["schema_version", "artifact_type", "generated_at", "runtime_window", "market", "source_mode", "is_example", "producer_name", "producer_version", "review_window_days", "review_date", "stock_universe_count", "stocks"]
REQUIRED_STOCK = ["stock_id", "stock_name", "review_date", "review_window_start", "review_window_end", "actual_high", "actual_low", "actual_close", "direction_result", "high_low_forecast_error", "hit_miss_status", "seven_day_hit_rate", "confidence_calibration", "factor_effectiveness", "error_reasons", "recommendation_for_improvement", "source_evidence", "data_quality", "missing_fields", "insufficient_data_reasons", "created_at"]
ACTUAL_PRICE_FIELDS = ["actual_high", "actual_low", "actual_close"]
HIT_VALUES = {"hit", "partial_hit", "miss", "insufficient_data", None}
DIRECTION_VALUES = {"correct", "incorrect", "neutral", "insufficient_data", None}
SECRET_PATTERNS = [re.compile(p, re.I) for p in [r"ghp_", r"github_pat_", r"sk-[A-Za-z0-9_-]{16,}", r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", r"api[_-]?key\s*[:=]", r"access[_-]?token\s*[:=]", r"password\s*[:=]", r"BEGIN (RSA|OPENSSH) PRIVATE KEY", r"\.env"]]

def load(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

def validate_doc(data: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_TOP:
        if key not in data: errors.append(f"{label}: missing top-level field {key}")
    if data.get("artifact_type") != "formal_prediction_review_runtime": errors.append(f"{label}: artifact_type must be formal_prediction_review_runtime")
    if data.get("runtime_window") != "prediction_review_1500": errors.append(f"{label}: runtime_window must be prediction_review_1500")
    if data.get("review_window_days") != 7: errors.append(f"{label}: review_window_days must be 7")
    stocks = data.get("stocks")
    if not isinstance(stocks, list) or not stocks:
        errors.append(f"{label}: stocks must be non-empty list"); return errors
    for i, stock in enumerate(stocks):
        if not isinstance(stock, dict): errors.append(f"{label}: stock {i} must be object"); continue
        for key in REQUIRED_STOCK:
            if key not in stock: errors.append(f"{label}: stock {i} missing {key}")
        for key in ACTUAL_PRICE_FIELDS:
            value = stock.get(key)
            if value is not None and (not finite_number(value) or float(value) <= 0): errors.append(f"{label}: {key} must be null or positive number")
        if stock.get("hit_miss_status") not in HIT_VALUES: errors.append(f"{label}: invalid hit_miss_status")
        if stock.get("direction_result") not in DIRECTION_VALUES: errors.append(f"{label}: invalid direction_result")
        hit_rate = stock.get("seven_day_hit_rate")
        if hit_rate is not None and (not finite_number(hit_rate) or float(hit_rate) < 0 or float(hit_rate) > 100): errors.append(f"{label}: seven_day_hit_rate must be null or 0-100")
        if hit_rate is None and "seven_day_hit_rate" not in stock.get("missing_fields", []): errors.append(f"{label}: null seven_day_hit_rate must be explicit missing field")
        if not isinstance(stock.get("source_evidence"), list) or not stock.get("source_evidence"): errors.append(f"{label}: source_evidence required")
        if not isinstance(stock.get("data_quality"), dict): errors.append(f"{label}: data_quality required")
        err_obj = stock.get("high_low_forecast_error")
        if err_obj is not None and not isinstance(err_obj, dict): errors.append(f"{label}: high_low_forecast_error must be object or null")
    text = json.dumps(data, ensure_ascii=False)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text): errors.append(f"{label}: secret-like pattern found")
    return errors

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--artifact", type=Path, default=RUNTIME); ap.add_argument("--pretty", action="store_true"); args = ap.parse_args()
    errors: list[str] = []
    template = load(TEMPLATE)
    if template is None: errors.append("template example missing")
    else:
        errors += validate_doc(template, "template")
        if template.get("is_example") is not True: errors.append("template: is_example must be true")
    runtime = load(args.artifact); runtime_checked = runtime is not None
    if runtime is not None:
        errors += validate_doc(runtime, "runtime")
        if runtime.get("is_example") is not False: errors.append("runtime: is_example must be false")
        if runtime.get("safety", {}).get("fabricated_review_metrics") is not False: errors.append("runtime: fabricated_review_metrics must be false")
    result = {"ok": not errors, "errors": errors, "template_checked": template is not None, "runtime_checked": runtime_checked, "artifact": str(args.artifact), "summary": {"artifact_type": "formal_prediction_review_runtime", "runtime_window": "prediction_review_1500", "reviewable_stock_count": runtime.get("reviewable_stock_count") if runtime else None, "secret_pattern_hits": 0 if not errors else None}}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True); sys.stdout.write("\n")
    return 0 if result["ok"] else 2
if __name__ == "__main__": raise SystemExit(main())
