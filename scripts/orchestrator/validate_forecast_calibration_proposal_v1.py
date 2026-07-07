#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON = ROOT / "artifacts/runtime/forecast_calibration_proposal_latest.json"
DEFAULT_MD = ROOT / "artifacts/runtime/forecast_calibration_proposal_latest.md"
HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
PUBLIC = "http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html"
GATES = {"blocked_insufficient_sample", "proposal_only", "ready_for_shadow_tuning", "ready_for_formula_change"}
SECRET_PATTERNS = [re.compile(p, re.I) for p in [r"ghp_", r"github_pat_", r"sk-[A-Za-z0-9_-]{16,}", r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", r"api[_-]?key\s*[:=]", r"access[_-]?token\s*[:=]", r"password\s*[:=]", r"BEGIN (RSA|OPENSSH) PRIVATE KEY", r"\.env"]]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_rate(name: str, value: Any, errors: list[str]) -> None:
    if value is None:
        return
    if not finite(value) or float(value) < 0 or float(value) > 100:
        errors.append(f"{name} must be null or 0-100")


def read_html(published: bool) -> str:
    if published:
        with urlopen(PUBLIC, timeout=10) as resp:
            return resp.read().decode("utf-8", "replace")
    return HTML.read_text(encoding="utf-8") if HTML.exists() else ""


def validate_dashboard(text: str, errors: list[str]) -> None:
    visible = re.sub(r"<[^>]+>", "", text)
    required = ["Forecast Calibration / 回測校準狀態", "deterministic_baseline_v1", "樣本數：9", "55.5556%", "隔日高低價區間命中率：資料不足", "樣本數不足", "尚不可直接修改公式", "不代表穩定績效"]
    for phrase in required:
        if phrase not in visible:
            errors.append(f"dashboard missing phrase: {phrase}")
    main = text.split("技術檢查 / Debug")[0]
    forbidden = ["模型已驗證成功", "正式績效已確認", "next-day interval hit rate: 0%"]
    for phrase in forbidden:
        if phrase in main and ("不可" + phrase) not in main:
            errors.append(f"dashboard overstates calibration result: {phrase}")


def validate(data: dict[str, Any], md_path: Path, html: str, published: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required = ["schema_version", "artifact_type", "generated_at", "method_under_test", "source_backtest_artifact", "stock_universe_count", "eligible_sample_count", "same_day_interval_hit_rate", "next_day_interval_hit_rate", "sample_limitations", "calibration_recommendations", "tuning_gate_status", "tuning_gate_reasons", "allowed_next_actions", "blocked_actions", "safety_policy"]
    for key in required:
        if key not in data:
            errors.append(f"missing required key: {key}")
    if data.get("artifact_type") != "forecast_calibration_proposal":
        errors.append("artifact_type must be forecast_calibration_proposal")
    if data.get("method_under_test") != "deterministic_baseline_v1":
        errors.append("method_under_test must be deterministic_baseline_v1")
    source = ROOT / str(data.get("source_backtest_artifact", ""))
    if not source.exists():
        errors.append("source_backtest_artifact does not exist")
    eligible = data.get("eligible_sample_count")
    if not isinstance(eligible, int) or eligible < 0:
        errors.append("eligible_sample_count must be a non-negative integer")
        eligible = -1
    validate_rate("same_day_interval_hit_rate", data.get("same_day_interval_hit_rate"), errors)
    validate_rate("next_day_interval_hit_rate", data.get("next_day_interval_hit_rate"), errors)
    if data.get("next_day_interval_hit_rate") is None and not any("next" in str(item).lower() or "隔日" in str(item) for item in data.get("sample_limitations", [])):
        errors.append("next-day null must have limitation reason")
    gate = data.get("tuning_gate_status")
    if gate not in GATES:
        errors.append("invalid tuning_gate_status")
    if isinstance(eligible, int) and eligible < 30 and gate == "ready_for_shadow_tuning":
        errors.append("eligible_sample_count < 30 cannot be ready_for_shadow_tuning")
    if isinstance(eligible, int) and eligible < 100 and gate == "ready_for_formula_change":
        errors.append("eligible_sample_count < 100 cannot be ready_for_formula_change")
    if not data.get("calibration_recommendations"):
        errors.append("calibration recommendations must exist")
    blocked = data.get("blocked_actions") if isinstance(data.get("blocked_actions"), list) else []
    if isinstance(eligible, int) and eligible < 30 and not any("formula" in str(item) or "baseline" in str(item) for item in blocked):
        errors.append("blocked actions must include formula mutation when sample insufficient")
    if not md_path.exists():
        errors.append("Markdown report missing")
    safety = data.get("safety_policy") if isinstance(data.get("safety_policy"), dict) else {}
    false_keys = ["deterministic_baseline_v1_formula_mutated", "production_rating_action_confidence_weight_mutated", "db_write", "scheduler_modified", "notification_sent", "python_main_executed", "production_pipeline_executed", "trading_or_order_executed", "secrets_read", "external_credentialed_api_called"]
    for key in false_keys:
        if safety.get(key) is not False:
            errors.append(f"safety_policy.{key} must be false")
    if safety.get("no_fake_metrics") is not True:
        errors.append("safety_policy.no_fake_metrics must be true")
    text = json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n" + (md_path.read_text(encoding="utf-8") if md_path.exists() else "") + "\n" + html
    if "NaN" in text or "Infinity" in text:
        errors.append("NaN / Infinity found")
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        errors.append("secret-like pattern found")
    validate_dashboard(html, errors)
    if published:
        warnings.append("published dashboard checked")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate forecast calibration proposal V1.")
    parser.add_argument("--proposal", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    parser.add_argument("--published", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    data = load(args.proposal)
    html = read_html(args.published)
    errors, warnings = validate(data, args.markdown, html, args.published)
    result = {"ok": not errors, "task_id": "AI-DEV-154", "errors": errors, "warnings": warnings, "summary": {"artifact_type": data.get("artifact_type"), "eligible_sample_count": data.get("eligible_sample_count"), "same_day_interval_hit_rate": data.get("same_day_interval_hit_rate"), "next_day_interval_hit_rate": data.get("next_day_interval_hit_rate"), "tuning_gate_status": data.get("tuning_gate_status")}, "side_effects": {"db_write": False, "notification_sent": False, "scheduler_modified": False, "production_pipeline_executed": False, "python_main_executed": False, "trading_or_order_executed": False, "secrets_read": False}}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
