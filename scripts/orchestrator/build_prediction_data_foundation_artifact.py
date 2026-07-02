#!/usr/bin/env python3
"""Build deterministic AI-DEV-122 prediction data foundation artifact."""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from app.evaluation.actual_outcome import load_actual_outcome, pending_actual_outcome
from app.evaluation.evaluator import evaluate_prediction_snapshot
from app.prediction.missing_data_policy import build_missing_data_policy_summary
from app.prediction.snapshot_builder import build_example_prediction_snapshots
from app.prediction.source_coverage import build_source_coverage_matrix
from app.prediction.source_inventory import build_data_source_inventory
SCHEMA_VERSION = "prediction_data_foundation_artifact_v1"
def now_iso() -> str: return "2026-07-02T00:00:00Z"
def safety_summary() -> dict[str, bool]:
    return {"broker_login": False, "simulation_order": False, "production_order": False, "line_send": False, "email_send": False, "scheduler_change": False, "production_db_write": False, "secrets_read": False, "production_forecast_weight_change": False, "large_ai_or_gemini_batch_call": False, "dashboard_production_publish": False, "nginx_systemd_cron_mutation": False}
def backtest_readiness() -> dict[str, Any]:
    return {"status": "data_foundation_ready_runtime_not_integrated", "runtime_integration": "not_in_scope", "future_consumable_artifacts": ["prediction snapshot", "actual outcome", "evaluation artifact", "rating", "score", "action", "confidence", "source coverage", "source quality"], "future_strategy_use_cases": ["rating threshold strategy", "score threshold strategy", "action-based strategy", "holding period strategy", "stop-loss / take-profit", "transaction cost", "position sizing", "parameter comparison"]}
def build_artifact() -> dict[str, Any]:
    inventory = build_data_source_inventory(); coverage_matrix = build_source_coverage_matrix(inventory=inventory); snapshots = build_example_prediction_snapshots()
    completed = load_actual_outcome("2330", "2026-06-23"); pending = pending_actual_outcome("2330", "2099-01-03", status="pending"); etf_pending = pending_actual_outcome("00878", "2099-04-03", status="pending")
    evaluations = [evaluate_prediction_snapshot(snapshots[0], completed), evaluate_prediction_snapshot(snapshots[0], pending), evaluate_prediction_snapshot(snapshots[1], completed)]
    return {"schema_version": SCHEMA_VERSION, "generated_at": now_iso(), "prediction_snapshots": [item.to_dict() for item in snapshots], "actual_outcomes": [item.to_dict() for item in [completed, pending, etf_pending]], "evaluations": [item.to_dict() for item in evaluations], "data_source_inventory": inventory, "source_coverage_matrix": coverage_matrix, "missing_data_policy_summary": build_missing_data_policy_summary(), "backtest_integration_readiness": backtest_readiness(), "safety_summary": safety_summary()}
def main() -> int:
    parser = argparse.ArgumentParser(description="Build prediction data foundation artifact JSON."); parser.add_argument("--pretty", action="store_true"); parser.add_argument("--output"); args = parser.parse_args()
    text = json.dumps(build_artifact(), ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        path = Path(args.output); path = path if path.is_absolute() else ROOT / path; path.write_text(text + "\n", encoding="utf-8")
    else: sys.stdout.write(text + "\n")
    return 0
if __name__ == "__main__": raise SystemExit(main())
