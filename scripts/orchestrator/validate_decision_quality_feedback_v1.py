#!/usr/bin/env python3
"""Validate AI-DEV-140 Decision Quality Feedback foundation."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.decision_feedback.builder import build_decision_quality_feedback_artifact
from app.decision_feedback.schemas import (
    CONFIDENCE_CALIBRATION_FIELDS,
    DASHBOARD_FEEDBACK_BLOCK_IDS,
    FACTOR_EFFECTIVENESS_FIELDS,
    MARKET_REGIME_QUALITY_FIELDS,
    MUTATION_FALSE_FLAGS,
    PREDICTION_REVIEW_FIELDS,
    RECOMMENDATION_FIELDS,
    REPORT_FEEDBACK_BLOCK_IDS,
    REQUIRED_FIELDS,
    ROLLING_EVALUATION_FIELDS,
    SAFETY_FALSE_FLAGS,
    SCHEMA_VERSION,
    SOURCE_ERROR_ATTRIBUTION_FIELDS,
    TASK_ID,
    WARNING_SOURCE_IDS,
)

REQUIRED_FILES = [
    "app/decision_feedback/__init__.py",
    "app/decision_feedback/schemas.py",
    "app/decision_feedback/builder.py",
    "scripts/orchestrator/build_decision_quality_feedback_artifact.py",
    "scripts/orchestrator/validate_decision_quality_feedback_v1.py",
    "templates/decision_quality_feedback_input.example.json",
    "templates/decision_quality_feedback_artifact.example.json",
    "docs/ai_dev_140_decision_quality_feedback_loop_foundation_v1.md",
    "docs/runbooks/decision_quality_feedback_loop_runbook.md",
]
SECRET_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"ghp_[A-Za-z0-9]+",
        r"github_pat_[A-Za-z0-9_]+",
        r"sk-[A-Za-z0-9]+",
        r"BEGIN (RSA|OPENSSH) PRIVATE KEY",
        r"api[_-]?key\s*[:=]",
        r"access[_-]?token\s*[:=]",
        r"password\s*[:=]",
    ]
]


def read_json(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def check_secret_patterns(errors: list[str]) -> None:
    for rel in REQUIRED_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
        if hits:
            errors.append(f"secret-like pattern in {rel}: {hits}")


def require_keys(obj: dict[str, Any], keys: list[str], label: str, errors: list[str]) -> None:
    for key in keys:
        if key not in obj:
            errors.append(f"{label} missing required key: {key}")


def validate_artifact(input_payload: dict[str, Any], artifact: dict[str, Any], errors: list[str]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if artifact.get("task_id") != TASK_ID:
        errors.append("task_id mismatch")
    for field in REQUIRED_FIELDS:
        if field not in artifact:
            errors.append(f"missing required field: {field}")
    refs = {
        "prediction_context_ref": "prediction_context_v1",
        "explainability_ref": "unified_explainability_evidence_trace_v1",
        "report_assembly_ref": "context_based_report_assembly_v1",
        "dashboard_intelligence_ref": "dashboard_decision_intelligence_v1",
    }
    for key, schema in refs.items():
        if artifact.get(key, {}).get("schema_version") != schema:
            errors.append(f"{key} must point to {schema}")

    require_keys(artifact.get("rolling_evaluation_summary", {}), ROLLING_EVALUATION_FIELDS, "rolling_evaluation_summary", errors)
    require_keys(artifact.get("prediction_review_summary", {}), PREDICTION_REVIEW_FIELDS, "prediction_review_summary", errors)
    require_keys(artifact.get("confidence_calibration_summary", {}), CONFIDENCE_CALIBRATION_FIELDS, "confidence_calibration_summary", errors)
    require_keys(artifact.get("market_regime_quality_summary", {}), MARKET_REGIME_QUALITY_FIELDS, "market_regime_quality_summary", errors)
    if artifact.get("rolling_evaluation_summary", {}).get("insufficient_data_flag") not in [True, False]:
        errors.append("insufficient_data_flag must be boolean")
    if artifact.get("confidence_calibration_summary", {}).get("production_confidence_changed") is not False:
        errors.append("production_confidence_changed must be false")

    factors = artifact.get("factor_effectiveness_summary", [])
    if not factors:
        errors.append("factor_effectiveness_summary must not be empty")
    for row in factors:
        require_keys(row, FACTOR_EFFECTIVENESS_FIELDS, f"factor_effectiveness_summary[{row.get('factor_id')} ]", errors)
        if row.get("production_weight_changed") is not False:
            errors.append(f"production_weight_changed must be false: {row.get('factor_id')}")
    attribution = artifact.get("source_error_attribution", [])
    if not attribution:
        errors.append("source_error_attribution must not be empty")
    for row in attribution:
        require_keys(row, SOURCE_ERROR_ATTRIBUTION_FIELDS, f"source_error_attribution[{row.get('source_id')} ]", errors)
        if row.get("recommendation_only") is not True:
            errors.append(f"source attribution must be recommendation_only: {row.get('source_id')}")

    for block_name in ["factor_feedback_blocks", "confidence_feedback_blocks", "regime_feedback_blocks", "source_reliability_feedback_blocks"]:
        rows = artifact.get(block_name, [])
        if not rows:
            errors.append(f"{block_name} must not be empty")
        for row in rows:
            if row.get("recommendation_only") is not True:
                errors.append(f"{block_name} must be recommendation_only: {row.get('block_id')}")

    report_ids = [row.get("block_id") for row in artifact.get("report_feedback_blocks", [])]
    for block_id in REPORT_FEEDBACK_BLOCK_IDS:
        if block_id not in report_ids:
            errors.append(f"missing report feedback block: {block_id}")
    dashboard_ids = [row.get("card_id") for row in artifact.get("dashboard_feedback_blocks", [])]
    for card_id in DASHBOARD_FEEDBACK_BLOCK_IDS:
        if card_id not in dashboard_ids:
            errors.append(f"missing dashboard feedback block: {card_id}")

    recommendations = artifact.get("recommendation_blocks", [])
    if not recommendations:
        errors.append("recommendation_blocks must not be empty")
    for row in recommendations:
        require_keys(row, RECOMMENDATION_FIELDS, f"recommendation_blocks[{row.get('recommendation_id')} ]", errors)
        if row.get("requires_human_review") is not True:
            errors.append(f"recommendation requires human review: {row.get('recommendation_id')}")
        if row.get("production_mutation_allowed") is not False or row.get("production_mutation_executed") is not False:
            errors.append(f"recommendation cannot allow/execute mutation: {row.get('recommendation_id')}")
    warning_sources = {row.get("source_id") for row in artifact.get("warning_blocks", [])}
    for source_id in WARNING_SOURCE_IDS:
        if source_id not in warning_sources:
            errors.append(f"missing warning block source: {source_id}")

    mutation = artifact.get("mutation_policy", {})
    if mutation.get("recommendation_only") is not True:
        errors.append("mutation_policy.recommendation_only must be true")
    if mutation.get("human_review_required_for_any_mutation") is not True:
        errors.append("mutation policy must require human review")
    for key in MUTATION_FALSE_FLAGS:
        if mutation.get(key) is not False:
            errors.append(f"mutation policy flag must be false: {key}")
    safety = artifact.get("safety_policy", {})
    for key in ["read_only", "offline_sample_only", "feedback_loop_artifact_only", "recommendation_review_attribution_only", "not_adaptive_strategy_engine", "not_production_mutation_engine", "no_direct_rating_action_confidence_change"]:
        if safety.get(key) is not True:
            errors.append(f"safety flag must be true: {key}")
    for key in SAFETY_FALSE_FLAGS:
        if safety.get(key) is not False:
            errors.append(f"safety flag must be false: {key}")

    rebuilt = build_decision_quality_feedback_artifact(input_payload)
    if rebuilt != artifact:
        errors.append("artifact template does not match deterministic builder output")


def validate_docs(errors: list[str]) -> None:
    doc = (ROOT / "docs/ai_dev_140_decision_quality_feedback_loop_foundation_v1.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/runbooks/decision_quality_feedback_loop_runbook.md").read_text(encoding="utf-8")
    phrases = [
        "V10 Unified Decision Intelligence",
        "reads AI-DEV-136",
        "reads AI-DEV-137",
        "reads AI-DEV-138",
        "reads AI-DEV-139",
        "recommendation / review / attribution",
        "not an adaptive strategy engine",
        "not a production mutation engine",
        "does not change factor weights",
        "does not change confidence",
        "does not change rating/action",
        "does not connect to production pipeline",
        "does not send LINE / Email",
        "does not publish dashboard",
        "human review gate",
    ]
    for phrase in phrases:
        if phrase not in doc:
            errors.append(f"doc missing required phrase: {phrase}")
    for phrase in ["offline", "build_decision_quality_feedback_artifact.py", "validate_decision_quality_feedback_v1.py", "no production pipeline", "human review gate"]:
        if phrase not in runbook:
            errors.append(f"runbook missing required phrase: {phrase}")


def validate() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")
    if errors:
        return {"ok": False, "task_id": TASK_ID, "errors": errors, "warnings": warnings}
    check_secret_patterns(errors)
    input_payload = read_json("templates/decision_quality_feedback_input.example.json")
    artifact = read_json("templates/decision_quality_feedback_artifact.example.json")
    validate_artifact(input_payload, artifact, errors)
    validate_docs(errors)
    proc = subprocess.run([str(ROOT / "venv/bin/python"), "scripts/orchestrator/build_decision_quality_feedback_artifact.py", "--pretty"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        errors.append(f"builder failed: {proc.stderr.strip()}")
    else:
        json.loads(proc.stdout)
    return {
        "ok": not errors,
        "task_id": TASK_ID,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "schema_version": artifact.get("schema_version"),
            "symbol": artifact.get("symbol"),
            "market": artifact.get("market"),
            "factor_effectiveness_count": len(artifact.get("factor_effectiveness_summary", [])),
            "source_error_attribution_count": len(artifact.get("source_error_attribution", [])),
            "recommendation_count": len(artifact.get("recommendation_blocks", [])),
            "warning_count": len(artifact.get("warning_blocks", [])),
            "report_feedback_block_count": len(artifact.get("report_feedback_blocks", [])),
            "dashboard_feedback_block_count": len(artifact.get("dashboard_feedback_blocks", [])),
            "recommendation_only": artifact.get("mutation_policy", {}).get("recommendation_only"),
            "production_weight_changed": artifact.get("mutation_policy", {}).get("production_weight_changed"),
            "production_confidence_changed": artifact.get("mutation_policy", {}).get("production_confidence_changed"),
            "production_rating_action_changed": artifact.get("mutation_policy", {}).get("production_rating_action_changed"),
            "secret_pattern_hits": 0 if not errors else "see_errors",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
