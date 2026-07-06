#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, re, sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates/formal_prediction_runtime_artifact.example.json"
RUNTIME = ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"
REQUIRED_TOP = ["schema_version", "artifact_type", "generated_at", "runtime_window", "market", "source_mode", "is_example", "producer_name", "producer_version", "data_cutoff_at", "stock_universe_count", "stocks"]
REQUIRED_STOCK = ["stock_id", "stock_name", "prediction_date", "next_trading_date", "same_day_high_prediction", "same_day_low_prediction", "next_day_high_prediction", "next_day_low_prediction", "one_month_trend", "three_month_trend", "confidence_score", "confidence_level", "evidence_summary", "key_factors", "risk_notes", "source_evidence", "data_quality", "missing_fields", "insufficient_data_reasons", "model_version", "created_at"]
NUMERIC_FIELDS = ["same_day_high_prediction", "same_day_low_prediction", "next_day_high_prediction", "next_day_low_prediction"]
TREND_VALUES = {"bullish", "neutral", "bearish", "uncertain"}
SECRET_PATTERNS = [re.compile(p, re.I) for p in [r"ghp_", r"github_pat_", r"sk-[A-Za-z0-9_-]{16,}", r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", r"api[_-]?key\s*[:=]", r"access[_-]?token\s*[:=]", r"password\s*[:=]", r"BEGIN (RSA|OPENSSH) PRIVATE KEY", r"\.env"]]

def load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

def validate_doc(data: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"{label}: missing top-level field {key}")
    if data.get("artifact_type") != "formal_prediction_runtime":
        errors.append(f"{label}: artifact_type must be formal_prediction_runtime")
    if data.get("runtime_window") != "pre_open_0700":
        errors.append(f"{label}: runtime_window must be pre_open_0700")
    if not isinstance(data.get("is_example"), bool):
        errors.append(f"{label}: is_example must be boolean")
    stocks = data.get("stocks")
    if not isinstance(stocks, list) or not stocks:
        errors.append(f"{label}: stocks must be a non-empty list")
        return errors
    for i, stock in enumerate(stocks):
        if not isinstance(stock, dict):
            errors.append(f"{label}: stock {i} must be object")
            continue
        for key in REQUIRED_STOCK:
            if key not in stock:
                errors.append(f"{label}: stock {i} missing {key}")
        for key in NUMERIC_FIELDS:
            value = stock.get(key)
            if value is None:
                if key not in stock.get("missing_fields", []) or not stock.get("insufficient_data_reasons"):
                    errors.append(f"{label}: null {key} requires missing_fields and insufficient_data_reasons")
            elif not finite_number(value) or float(value) <= 0:
                errors.append(f"{label}: {key} must be null or positive number")
        score = stock.get("confidence_score")
        if score is not None and (not finite_number(score) or float(score) < 0 or float(score) > 100):
            errors.append(f"{label}: confidence_score must be null or 0-100")
        for key in ("one_month_trend", "three_month_trend"):
            value = stock.get(key)
            if value is not None and value not in TREND_VALUES:
                errors.append(f"{label}: {key} invalid trend value")
        if not isinstance(stock.get("source_evidence"), list):
            errors.append(f"{label}: source_evidence must be list")
        if not isinstance(stock.get("data_quality"), dict):
            errors.append(f"{label}: data_quality must exist")
    text = json.dumps(data, ensure_ascii=False)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{label}: secret-like pattern found")
    return errors

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", type=Path, default=RUNTIME)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    errors: list[str] = []
    template = load(TEMPLATE)
    if template is None:
        errors.append("template example missing")
    else:
        errors += validate_doc(template, "template")
        if template.get("is_example") is not True:
            errors.append("template: is_example must be true")
    runtime = load(args.artifact)
    runtime_checked = runtime is not None
    if runtime is not None:
        errors += validate_doc(runtime, "runtime")
        if runtime.get("is_example") is not False:
            errors.append("runtime: is_example must be false")
    result = {"ok": not errors, "errors": errors, "template_checked": template is not None, "runtime_checked": runtime_checked, "artifact": str(args.artifact), "summary": {"artifact_type": "formal_prediction_runtime", "runtime_window": "pre_open_0700", "secret_pattern_hits": 0 if not errors else None}}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
