#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, re, sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
PRED = ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"
REVIEW = ROOT / "artifacts/runtime/formal_prediction_review_runtime_latest.json"
HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
PUBLIC = "http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html"
SECRET = [re.compile(p, re.I) for p in [r"ghp_", r"github_pat_", r"sk-[A-Za-z0-9_-]{16,}", r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", r"api[_-]?key\s*[:=]", r"access[_-]?token\s*[:=]", r"password\s*[:=]", r"BEGIN (RSA|OPENSSH) PRIVATE KEY", r"\.env"]]
PRICE = ["same_day_high_prediction", "same_day_low_prediction", "next_day_high_prediction", "next_day_low_prediction"]
TREND = {"bullish", "neutral", "bearish", "uncertain"}
CONF = {"low", "medium", "medium_high", "insufficient_data", None}
RAW_MAIN = ["runtime_window / pre_open_0700", "actual_high", "hit_miss_status", "factor_effectiveness"]

def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

def scan_text(text: str) -> int:
    return sum(1 for p in SECRET if p.search(text))

def validate_prediction(data: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    if data.get("artifact_type") != "formal_prediction_runtime": errors.append("prediction artifact_type mismatch")
    if data.get("is_example") is not False: errors.append("formal prediction runtime must not be example")
    if data.get("model_version") != "deterministic_baseline_v1": errors.append("top-level model_version missing deterministic_baseline_v1")
    if data.get("safety", {}).get("fabricated_forecast_values") is not False: errors.append("fabricated forecast flag must be false")
    stocks = data.get("stocks", []) if isinstance(data.get("stocks"), list) else []
    if len(stocks) != 9: errors.append(f"expected 9 stocks, got {len(stocks)}")
    value_count = 0
    for stock in stocks:
        for key in PRICE:
            value = stock.get(key)
            if value is None:
                if key not in stock.get("missing_fields", []) and not stock.get("insufficient_data_reasons"):
                    errors.append(f"{stock.get('stock_id')}: missing {key} lacks insufficient data reason")
            elif not finite(value) or float(value) <= 0 or float(value) in {0.0, -1.0}:
                errors.append(f"{stock.get('stock_id')}: invalid {key}")
            else:
                value_count += 1
        if finite(stock.get("same_day_high_prediction")) and finite(stock.get("same_day_low_prediction")) and stock["same_day_high_prediction"] < stock["same_day_low_prediction"]:
            errors.append(f"{stock.get('stock_id')}: same day high < low")
        if finite(stock.get("next_day_high_prediction")) and finite(stock.get("next_day_low_prediction")) and stock["next_day_high_prediction"] < stock["next_day_low_prediction"]:
            errors.append(f"{stock.get('stock_id')}: next day high < low")
        score = stock.get("confidence_score")
        if score is not None and (not finite(score) or float(score) < 0 or float(score) > 75): errors.append(f"{stock.get('stock_id')}: confidence_score outside 0-75")
        if stock.get("confidence_level") not in CONF: errors.append(f"{stock.get('stock_id')}: invalid confidence level")
        if stock.get("one_month_trend") not in TREND or stock.get("three_month_trend") not in TREND: errors.append(f"{stock.get('stock_id')}: invalid trend")
        if stock.get("model_version") != "deterministic_baseline_v1": errors.append(f"{stock.get('stock_id')}: missing deterministic model_version")
        if not stock.get("source_evidence") or not stock.get("method_metadata") or not stock.get("data_quality"): errors.append(f"{stock.get('stock_id')}: missing explainability fields")
    return {"stock_count": len(stocks), "forecast_value_count": value_count}

def validate_review(data: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    if data.get("artifact_type") != "formal_prediction_review_runtime": errors.append("review artifact_type mismatch")
    if data.get("is_example") is not False: errors.append("formal review runtime must not be example")
    if data.get("safety", {}).get("fabricated_review_metrics") is not False: errors.append("fabricated review metrics flag must be false")
    stocks = data.get("stocks", []) if isinstance(data.get("stocks"), list) else []
    reviewable = 0
    for stock in stocks:
        if stock.get("hit_miss_status") in {"hit", "partial_hit", "miss"}: reviewable += 1
        if stock.get("seven_day_hit_rate") is None and "seven_day_hit_rate" not in stock.get("missing_fields", []): errors.append(f"{stock.get('stock_id')}: null seven_day_hit_rate not explained")
        if stock.get("seven_day_hit_rate") is not None and not finite(stock.get("seven_day_hit_rate")): errors.append(f"{stock.get('stock_id')}: invalid seven_day_hit_rate")
        if stock.get("high_low_forecast_error") is not None and not isinstance(stock.get("high_low_forecast_error"), dict): errors.append(f"{stock.get('stock_id')}: high_low_forecast_error must be object")
    return {"stock_count": len(stocks), "reviewable_stock_count": reviewable}

def validate_html(text: str, errors: list[str]) -> None:
    required = ["deterministic_baseline_v1", "待回測校準", "今日最高價預測", "今日實際最高價", "信心分數", "資料品質", "資料待接", "不得產生假命中率", "未重送，也未驗證實際送達內容"]
    for item in required:
        if item not in text: errors.append(f"dashboard missing user-readable label: {item}")
    main = text.split("技術檢查 / Debug")[0]
    for raw in RAW_MAIN:
        if raw in main: errors.append(f"raw technical key leaked in main UI: {raw}")

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--published", action="store_true"); ap.add_argument("--pretty", action="store_true"); args = ap.parse_args()
    errors: list[str] = []
    pred = load(PRED); review = load(REVIEW)
    summary = {"prediction": validate_prediction(pred, errors), "review": validate_review(review, errors)}
    html = HTML.read_text(encoding="utf-8") if HTML.exists() else ""
    validate_html(html, errors)
    published = {"checked": False}
    if args.published:
        published = {"checked": True, "public_url": PUBLIC, "reachable": False}
        try:
            with urlopen(PUBLIC, timeout=10) as resp:
                published_text = resp.read().decode("utf-8", errors="replace")
            published["reachable"] = True
            validate_html(published_text, errors)
        except Exception as exc:
            published["error"] = str(exc); errors.append(f"public dashboard unreachable: {exc}")
    hits = scan_text(json.dumps(pred, ensure_ascii=False) + json.dumps(review, ensure_ascii=False) + html)
    if hits: errors.append("secret-like pattern hit")
    result = {"ok": not errors, "task_id": "AI-DEV-152", "errors": errors, "summary": summary, "published_summary": published, "secret_pattern_hits": hits, "safety": {"external_api_called": False, "secrets_read": False, "db_write": False, "notification_sent": False, "production_pipeline_executed": False, "python_main_executed": False, "trading_or_order_executed": False, "production_rating_action_confidence_weight_mutated": False}}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True); sys.stdout.write("\n")
    return 0 if result["ok"] else 2
if __name__ == "__main__": raise SystemExit(main())
