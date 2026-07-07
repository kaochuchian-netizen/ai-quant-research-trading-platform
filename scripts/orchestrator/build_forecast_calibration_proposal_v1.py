#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKTEST = ROOT / "artifacts/runtime/formal_forecast_backtest_report_latest.json"
DEFAULT_JSON = ROOT / "artifacts/runtime/forecast_calibration_proposal_latest.json"
DEFAULT_MD = ROOT / "artifacts/runtime/forecast_calibration_proposal_latest.md"
GATE_VALUES = {"blocked_insufficient_sample", "proposal_only", "ready_for_shadow_tuning", "ready_for_formula_change"}


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def gate_status(report: dict[str, Any]) -> tuple[str, list[str]]:
    metrics = report.get("metrics", {}) if isinstance(report.get("metrics"), dict) else {}
    eligible = int(metrics.get("eligible_sample_count") or report.get("backtest_window", {}).get("available_sample_count") or 0)
    next_day_hit = metrics.get("next_day_interval_hit_rate")
    bucket_rows = metrics.get("confidence_bucket_hit_rate") if isinstance(metrics.get("confidence_bucket_hit_rate"), list) else []
    reasons: list[str] = []
    if eligible < 30:
        reasons.append("eligible_sample_count_less_than_30")
    if next_day_hit is None:
        reasons.append("next_day_actual_outcome_insufficient")
    if not any(isinstance(row, dict) and row.get("status") == "ok" for row in bucket_rows):
        reasons.append("confidence_bucket_sample_size_insufficient")
    if eligible < 30:
        return "blocked_insufficient_sample", reasons
    if eligible < 100:
        return "ready_for_shadow_tuning", reasons
    return "ready_for_formula_change", reasons


def build_proposal(source: Path = BACKTEST) -> dict[str, Any]:
    report = load_json(source)
    metrics = report.get("metrics", {}) if isinstance(report.get("metrics"), dict) else {}
    cal = report.get("calibration_analysis", {}) if isinstance(report.get("calibration_analysis"), dict) else {}
    status, reasons = gate_status(report)
    next_day = metrics.get("next_day_interval_hit_rate")
    limitations = []
    eligible = int(metrics.get("eligible_sample_count") or 0)
    if eligible < 30:
        limitations.append("目前 eligible sample count 低於 30，只能作初步 proposal visibility，不能進入 shadow tuning。")
    if next_day is None:
        limitations.append("隔日高低價區間命中率為 null，因 selected window 沒有 usable next-day actual outcome。")
    if not limitations:
        limitations.append("目前樣本足以檢視 proposal，但任何調參仍需獨立 shadow tuning 任務。")
    blocked_actions = [
        "direct_deterministic_baseline_v1_formula_mutation",
        "production_rating_action_confidence_weight_mutation",
        "treat_55_5556_percent_as_validated_model_performance",
        "display_next_day_null_as_zero_or_failure",
    ]
    allowed_next_actions = [
        "accumulate_more_formal_forecast_actual_pairs",
        "continue_dashboard_visibility_of_sample_limitations",
        "prepare_shadow_tuning_only_after_minimum_sample_gate",
    ]
    return {
        "schema_version": "forecast_calibration_proposal_v1",
        "artifact_type": "forecast_calibration_proposal",
        "task_id": "AI-DEV-154",
        "generated_at": datetime(2026, 7, 7, 9, 45).isoformat() + "+08:00",
        "method_under_test": report.get("method_under_test", "deterministic_baseline_v1"),
        "source_backtest_artifact": str(source.relative_to(ROOT)),
        "stock_universe_count": report.get("stock_universe_count"),
        "eligible_sample_count": eligible,
        "same_day_interval_hit_rate": metrics.get("same_day_interval_hit_rate"),
        "next_day_interval_hit_rate": next_day,
        "sample_limitations": limitations,
        "calibration_recommendations": cal.get("recommendations", []),
        "tuning_gate_status": status,
        "tuning_gate_reasons": reasons,
        "allowed_next_actions": allowed_next_actions,
        "blocked_actions": blocked_actions,
        "dashboard_wording_policy": {
            "must_show_sample_count": True,
            "must_show_insufficient_sample_warning": True,
            "must_not_claim_model_validated": True,
            "must_not_display_next_day_null_as_zero": True,
            "must_not_hide_sample_count": True,
        },
        "safety_policy": {
            "deterministic_baseline_v1_formula_mutated": False,
            "production_rating_action_confidence_weight_mutated": False,
            "db_write": False,
            "scheduler_modified": False,
            "notification_sent": False,
            "python_main_executed": False,
            "production_pipeline_executed": False,
            "trading_or_order_executed": False,
            "secrets_read": False,
            "external_credentialed_api_called": False,
            "no_fake_metrics": True,
        },
    }


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Forecast Calibration Proposal V1",
        "",
        f"Task: {data['task_id']}",
        f"Method: `{data['method_under_test']}`",
        f"Source: `{data['source_backtest_artifact']}`",
        "",
        "## Dashboard Summary",
        "",
        f"- Stock universe count: {data['stock_universe_count']}",
        f"- Eligible sample count: {data['eligible_sample_count']}",
        f"- Same-day interval hit rate: {data['same_day_interval_hit_rate']}",
        f"- Next-day interval hit rate: {data['next_day_interval_hit_rate'] if data['next_day_interval_hit_rate'] is not None else '資料不足'}",
        f"- Tuning gate status: {data['tuning_gate_status']}",
        "",
        "## Sample Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in data["sample_limitations"])
    lines.extend(["", "## Blocked Actions", ""])
    lines.extend(f"- {item}" for item in data["blocked_actions"])
    lines.extend(["", "## Safety", "", "This proposal does not change deterministic_baseline_v1, production scores, delivery behavior, scheduler, DB, notifications, or trading behavior.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build forecast calibration proposal from AI-DEV-153 backtest report.")
    parser.add_argument("--source", type=Path, default=BACKTEST)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    data = build_proposal(args.source)
    if data["tuning_gate_status"] not in GATE_VALUES:
        raise SystemExit("invalid tuning gate")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(stable_json(data), encoding="utf-8")
    args.output_md.write_text(render_markdown(data), encoding="utf-8")
    summary = {
        "ok": True,
        "artifact_type": data["artifact_type"],
        "output_json": str(args.output_json),
        "output_md": str(args.output_md),
        "eligible_sample_count": data["eligible_sample_count"],
        "same_day_interval_hit_rate": data["same_day_interval_hit_rate"],
        "next_day_interval_hit_rate": data["next_day_interval_hit_rate"],
        "tuning_gate_status": data["tuning_gate_status"],
        "blocked_actions": data["blocked_actions"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
