#!/usr/bin/env python3
"""Validate AI-DEV-124 confidence calibration V1."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from app.calibration.action_effectiveness import analyze_action_effectiveness
from app.calibration.calibration_builder import build_confidence_calibration_artifact, build_offline_sample_input
from app.calibration.confidence_buckets import analyze_confidence_buckets
from app.calibration.high_low_error import analyze_high_low_error
from app.calibration.rating_effectiveness import analyze_rating_effectiveness
from app.calibration.recommendation_policy import build_recommendations
from app.calibration.schemas import CalibrationFinding, PLATFORM_ACTIONS, RATINGS, READINESS_GROUPS, input_from_dict
from app.calibration.source_coverage_accuracy import analyze_source_coverage_accuracy
REQUIRED_FILES = ["app/calibration/__init__.py", "app/calibration/schemas.py", "app/calibration/confidence_buckets.py", "app/calibration/calibration_metrics.py", "app/calibration/rating_effectiveness.py", "app/calibration/action_effectiveness.py", "app/calibration/high_low_error.py", "app/calibration/source_coverage_accuracy.py", "app/calibration/recommendation_policy.py", "app/calibration/calibration_builder.py", "scripts/orchestrator/build_confidence_calibration_artifact.py", "scripts/orchestrator/validate_confidence_calibration_v1.py", "templates/confidence_calibration_input.example.json", "templates/confidence_calibration_artifact.example.json", "docs/ai_dev_124_confidence_calibration_v1.md"]
FORBIDDEN_FALSE = {"broker_login", "simulation_order", "production_order", "line_send", "email_send", "scheduler_change", "production_db_write", "secrets_read", "production_forecast_weight_change", "production_confidence_mutation", "production_rating_action_rule_mutation", "dashboard_production_publish", "trading_execution_run"}
def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict): raise ValueError(f"JSON root must be object: {path}")
    return data
def run_builder() -> tuple[dict[str, Any] | None, str | None]:
    proc = subprocess.run([sys.executable, "scripts/orchestrator/build_confidence_calibration_artifact.py"], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0: return None, proc.stderr.strip() or proc.stdout.strip()
    try: data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc: return None, str(exc)
    return data if isinstance(data, dict) else None, None if isinstance(data, dict) else "builder root must be object"
def validate_artifact(artifact: dict[str, Any], reasons: list[str]) -> None:
    for field in ["schema_version", "generated_at", "input_summary", "sample_window", "sample_size_summary", "confidence_bucket_analysis", "overall_calibration_metrics", "rating_effectiveness", "action_effectiveness", "high_low_error_analysis", "source_coverage_accuracy", "calibration_findings", "recommendations", "safety_summary", "future_integration"]:
        if field not in artifact: reasons.append(f"artifact missing field: {field}")
    buckets = artifact.get("confidence_bucket_analysis", [])
    if isinstance(buckets, list):
        for finding in ["over_confident", "under_confident", "well_calibrated", "insufficient_sample"]:
            if not any(isinstance(b, dict) and b.get("finding") == finding for b in buckets): reasons.append(f"bucket analysis missing {finding} case")
    metrics = artifact.get("overall_calibration_metrics", {})
    if not isinstance(metrics, dict) or "weighted_expected_calibration_error" not in metrics: reasons.append("overall metrics missing weighted_expected_calibration_error")
    ratings = {r.get("rating") for r in artifact.get("rating_effectiveness", []) if isinstance(r, dict)}
    for rating in RATINGS:
        if rating not in ratings: reasons.append(f"rating effectiveness missing {rating}")
    actions = {r.get("action") for r in artifact.get("action_effectiveness", []) if isinstance(r, dict)}
    for action in PLATFORM_ACTIONS:
        if action not in actions: reasons.append(f"action effectiveness missing {action}")
    coverage = {r.get("source_coverage_readiness") for r in artifact.get("source_coverage_accuracy", []) if isinstance(r, dict)}
    for readiness in READINESS_GROUPS:
        if readiness not in coverage: reasons.append(f"source coverage accuracy missing {readiness}")
    high_low = artifact.get("high_low_error_analysis", {})
    if not isinstance(high_low, dict) or "finding" not in high_low: reasons.append("high/low analysis missing finding")
    safety = artifact.get("safety_summary", {})
    if not isinstance(safety, dict): reasons.append("safety_summary must be object")
    else:
        for key in FORBIDDEN_FALSE:
            if safety.get(key) is not False: reasons.append(f"safety_summary must confirm {key}=false")
        if safety.get("production_mutation_allowed") is not False: reasons.append("production_mutation_allowed must be false")
    for rec in artifact.get("recommendations", []):
        if not isinstance(rec, dict): continue
        if rec.get("production_mutation_allowed") is not False: reasons.append("recommendation allows production mutation")
        if rec.get("requires_human_review") is not True: reasons.append("recommendation must require human review")
    future = artifact.get("future_integration", {})
    for key in ["ai_dev_122", "ai_dev_123", "ai_dev_125", "ai_dev_126", "backtesting_py"]:
        if not isinstance(future, dict) or key not in future: reasons.append(f"future integration missing {key}")
def validate_direct_behavior(reasons: list[str]) -> None:
    samples = build_offline_sample_input().samples
    for sample in samples:
        reasons.extend(sample.validate())
    buckets = analyze_confidence_buckets(samples)
    for finding in ["over_confident", "under_confident", "well_calibrated", "insufficient_sample"]:
        if not any(b.finding == finding for b in buckets): reasons.append(f"direct bucket missing {finding}")
    ratings = {r.rating for r in analyze_rating_effectiveness(samples)}
    if set(RATINGS) - ratings: reasons.append("direct rating groups incomplete")
    actions = {r.action for r in analyze_action_effectiveness(samples)}
    if set(PLATFORM_ACTIONS) - actions: reasons.append("direct action groups incomplete")
    missing = [s for s in samples if s.predicted_high is None and s.predicted_low is None]
    if not missing: reasons.append("offline sample missing high/low not_available case")
    try: analyze_high_low_error(missing)
    except Exception as exc: reasons.append(f"high/low missing case failed: {exc}")
    readiness = {r.source_coverage_readiness for r in analyze_source_coverage_accuracy(samples)}
    if set(READINESS_GROUPS) - readiness: reasons.append("direct source coverage groups incomplete")
    recs = build_recommendations([CalibrationFinding("test", "confidence_formula", "over_confident", "medium", "evidence", 20, [])])
    if any(r.production_mutation_allowed for r in recs): reasons.append("recommendation policy allowed production mutation")
def validate_templates(reasons: list[str]) -> None:
    inp = load_json(ROOT / "templates/confidence_calibration_input.example.json"); art = load_json(ROOT / "templates/confidence_calibration_artifact.example.json")
    cal_input = input_from_dict(inp); reasons.extend(cal_input.validate())
    if not cal_input.samples: reasons.append("input example has no samples")
    validate_artifact(art, reasons)
def validate_docs(reasons: list[str]) -> None:
    text = (ROOT / "docs/ai_dev_124_confidence_calibration_v1.md").read_text(encoding="utf-8")
    for phrase in ["Purpose", "Scope", "Non-goals", "Architecture", "Calibration sample schema", "Confidence bucket analysis", "Overall calibration metrics", "Rating effectiveness", "Action effectiveness", "High / low forecast error analysis", "Source coverage vs accuracy", "Recommendation policy", "Safety boundary", "Validation commands", "AI-DEV-122", "AI-DEV-123", "AI-DEV-125", "AI-DEV-126", "backtesting.py", "No production trading", "No simulation order", "No production order", "No scheduler mutation", "No LINE/Email delivery", "No production DB write", "No production confidence mutation", "No production forecast weight mutation", "No production rating/action mutation", "No production dashboard publish", "No automatic strategy change"]:
        if phrase not in text: reasons.append(f"doc missing phrase: {phrase}")
def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-124 confidence calibration V1."); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args(); reasons: list[str] = []
    for path in REQUIRED_FILES:
        if not (ROOT / path).exists(): reasons.append(f"required file missing: {path}")
    for func in [validate_templates, validate_direct_behavior, validate_docs]:
        try: func(reasons)
        except Exception as exc: reasons.append(f"{func.__name__} failed: {exc}")
    artifact, error = run_builder()
    if error: reasons.append(f"artifact builder output invalid: {error}")
    elif artifact: validate_artifact(artifact, reasons)
    output = {"ok": True, "passed": not reasons, "required_file_count": len(REQUIRED_FILES), "reasons": reasons, "side_effects": {"files_modified": False, "runtime_queue_modified": False, "database_modified": False, "production_data_modified": False, "external_api_called": False, "notification_sent": False, "trading_execution_run": False, "production_pipeline_run": False, "scheduler_modified": False, "secrets_read_or_modified": False}}
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True); sys.stdout.write("\n")
    return 0 if output["passed"] else 2
if __name__ == "__main__": raise SystemExit(main())
