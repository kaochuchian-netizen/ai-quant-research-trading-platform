#!/usr/bin/env python3
"""Validate AI-DEV-122 prediction data foundation V1 artifacts."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from app.evaluation.actual_outcome import pending_actual_outcome
from app.evaluation.evaluator import evaluate_prediction_snapshot
from app.prediction.missing_data_policy import validate_missing_data_policies
from app.prediction.schemas import PREDICTION_TARGETS
from app.prediction.snapshot_builder import build_prediction_snapshot
from app.prediction.source_coverage import READINESS_LEVELS, build_source_coverage_matrix, validate_source_coverage_matrix
from app.prediction.source_inventory import CANDIDATE_SOURCE_IDS, CURRENT_SOURCE_IDS, SOURCE_PRIORITIES, build_data_source_inventory, validate_inventory
REQUIRED_FILES = ["app/prediction/__init__.py", "app/prediction/schemas.py", "app/prediction/snapshot_builder.py", "app/prediction/source_inventory.py", "app/prediction/source_coverage.py", "app/prediction/missing_data_policy.py", "app/evaluation/__init__.py", "app/evaluation/schemas.py", "app/evaluation/actual_outcome.py", "app/evaluation/evaluator.py", "scripts/orchestrator/build_prediction_data_foundation_artifact.py", "scripts/orchestrator/validate_prediction_data_foundation_v1.py", "templates/data_source_inventory.example.json", "templates/source_coverage_matrix.example.json", "templates/prediction_data_foundation_artifact.example.json", "docs/ai_dev_122_prediction_data_foundation_source_coverage_v1.md"]
FORBIDDEN_FALSE = {"broker_login", "simulation_order", "production_order", "line_send", "email_send", "scheduler_change", "production_db_write", "secrets_read", "production_forecast_weight_change", "large_ai_or_gemini_batch_call", "dashboard_production_publish", "nginx_systemd_cron_mutation"}
def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict): raise ValueError(f"JSON root must be object: {path}")
    return data
def run_builder() -> tuple[dict[str, Any] | None, str | None]:
    proc = subprocess.run([sys.executable, "scripts/orchestrator/build_prediction_data_foundation_artifact.py"], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0: return None, proc.stderr.strip() or proc.stdout.strip()
    try: data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc: return None, str(exc)
    return data if isinstance(data, dict) else None, None if isinstance(data, dict) else "builder root must be object"
def validate_artifact(artifact: dict[str, Any], reasons: list[str]) -> None:
    for field in ["schema_version", "generated_at", "prediction_snapshots", "actual_outcomes", "evaluations", "data_source_inventory", "source_coverage_matrix", "missing_data_policy_summary", "backtest_integration_readiness", "safety_summary"]:
        if field not in artifact: reasons.append(f"artifact missing field: {field}")
    inventory = artifact.get("data_source_inventory", []); matrix = artifact.get("source_coverage_matrix", [])
    reasons.extend(validate_inventory(inventory) if isinstance(inventory, list) else ["artifact data_source_inventory must be list"])
    reasons.extend(validate_source_coverage_matrix(matrix) if isinstance(matrix, list) else ["artifact source_coverage_matrix must be list"])
    reasons.extend(validate_missing_data_policies(artifact.get("missing_data_policy_summary")) if isinstance(artifact.get("missing_data_policy_summary"), dict) else ["artifact missing_data_policy_summary must be object"])
    safety = artifact.get("safety_summary")
    if not isinstance(safety, dict): reasons.append("safety_summary must be object")
    else:
        for key in FORBIDDEN_FALSE:
            if safety.get(key) is not False: reasons.append(f"safety_summary must confirm {key}=false")
    readiness = artifact.get("backtest_integration_readiness")
    if not isinstance(readiness, dict): reasons.append("backtest_integration_readiness must be object")
    elif readiness.get("runtime_integration") != "not_in_scope" or len(readiness.get("future_strategy_use_cases", [])) < 8: reasons.append("backtest integration readiness incomplete")
    snapshots = artifact.get("prediction_snapshots", []); outcomes = artifact.get("actual_outcomes", []); evaluations = artifact.get("evaluations", [])
    if isinstance(snapshots, list):
        if not any(isinstance(item, dict) and item.get("stock_id") == "2330" for item in snapshots): reasons.append("artifact must include 2330-like stock snapshot")
        if not any(isinstance(item, dict) and isinstance(item.get("predicted_high"), dict) and item["predicted_high"].get("status") == "not_applicable" for item in snapshots): reasons.append("artifact must include not_available predicted high/low case")
    if isinstance(outcomes, list) and not any(isinstance(item, dict) and item.get("outcome_status") == "pending" for item in outcomes): reasons.append("artifact must include pending actual outcome case")
    if isinstance(evaluations, list):
        if not any(isinstance(item, dict) and item.get("evaluation_status") == "pending_actual_outcome" for item in evaluations): reasons.append("artifact must include pending_actual_outcome evaluation")
        if not any(isinstance(item, dict) and item.get("high_error_pct") == "not_available" for item in evaluations): reasons.append("artifact must include unavailable high/low evaluation metric")
def validate_templates(reasons: list[str]) -> None:
    inventory_template = load_json(ROOT / "templates" / "data_source_inventory.example.json"); matrix_template = load_json(ROOT / "templates" / "source_coverage_matrix.example.json"); artifact_template = load_json(ROOT / "templates" / "prediction_data_foundation_artifact.example.json")
    reasons.extend(validate_inventory(inventory_template.get("data_source_inventory", [])) if isinstance(inventory_template.get("data_source_inventory"), list) else ["data_source_inventory.example.json missing data_source_inventory list"])
    reasons.extend(validate_source_coverage_matrix(matrix_template.get("source_coverage_matrix", [])) if isinstance(matrix_template.get("source_coverage_matrix"), list) else ["source_coverage_matrix.example.json missing source_coverage_matrix list"])
    validate_artifact(artifact_template, reasons)
def validate_docs(reasons: list[str]) -> None:
    text = (ROOT / "docs" / "ai_dev_122_prediction_data_foundation_source_coverage_v1.md").read_text(encoding="utf-8")
    for phrase in ["No trading execution", "No production order", "No simulation order", "No scheduler mutation", "No LINE/Email delivery", "No production dashboard publish", "No production DB write", "No production weight mutation", "No backtesting.py runtime integration yet", "yfinance formal source policy", "AI-DEV-123 Explainability", "AI-DEV-124 Confidence Calibration", "AI-DEV-125 Adaptive Weight Recommendation", "AI-DEV-126 Dashboard Intelligence"]:
        if phrase not in text: reasons.append(f"doc missing phrase: {phrase}")
def validate_direct_behavior(reasons: list[str]) -> None:
    inventory = build_data_source_inventory(); ids = {item.get("source_id") for item in inventory}
    for source_id in CURRENT_SOURCE_IDS | CANDIDATE_SOURCE_IDS:
        if source_id not in ids: reasons.append(f"direct inventory missing source: {source_id}")
    if "yfinance_external_market" not in ids: reasons.append("direct yfinance source missing")
    matrix = build_source_coverage_matrix(inventory=inventory); targets = {item.get("prediction_target") for item in matrix}
    for target in PREDICTION_TARGETS:
        if target not in targets: reasons.append(f"direct coverage matrix missing target: {target}")
    for item in matrix:
        if item.get("readiness") not in READINESS_LEVELS: reasons.append(f"invalid readiness: {item.get('readiness')}")
    snapshot = build_prediction_snapshot(run_id="validator-missing-high-low", stock_id="2330", stock_name="TSMC", prediction_target="next_day_high_low", predicted_high="unavailable", predicted_low="unavailable", confidence=0.8, source_ids=["historical_csv_fallback"])
    reasons.extend(["snapshot missing high/low behavior failed: " + item for item in snapshot.validate(ids)])
    evaluation = evaluate_prediction_snapshot(snapshot, pending_actual_outcome("2330", "2099-01-03"))
    if evaluation.evaluation_status != "pending_actual_outcome": reasons.append("pending actual outcome did not produce pending_actual_outcome evaluation")
def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-122 prediction data foundation V1."); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args(); reasons: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).exists(): reasons.append(f"required file missing: {relative}")
    for func in [validate_templates, validate_docs, validate_direct_behavior]:
        try: func(reasons)
        except Exception as exc: reasons.append(f"{func.__name__} failed: {exc}")
    artifact, error = run_builder()
    if error: reasons.append(f"artifact builder output invalid: {error}")
    elif artifact is not None: validate_artifact(artifact, reasons)
    output = {"ok": True, "passed": not reasons, "required_file_count": len(REQUIRED_FILES), "prediction_targets": sorted(PREDICTION_TARGETS), "source_priorities": sorted(SOURCE_PRIORITIES), "coverage_readiness": sorted(READINESS_LEVELS), "reasons": reasons, "side_effects": {"files_modified": False, "runtime_queue_modified": False, "database_modified": False, "production_data_modified": False, "external_api_called": False, "notification_sent": False, "trading_execution_run": False, "production_pipeline_run": False, "scheduler_modified": False, "secrets_read_or_modified": False}}
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True); sys.stdout.write("\n")
    return 0 if output["passed"] else 2
if __name__ == "__main__": raise SystemExit(main())
