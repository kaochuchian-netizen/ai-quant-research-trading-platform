#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.source_roadmap.roadmap_builder import build_external_source_connector_roadmap
from app.source_roadmap.schemas import COMPLEXITY_LEVELS, DECISION_VALUES, PHASES, RISK_LEVELS, SCHEMA_VERSION, SOURCE_PRIORITIES, STATUSES

REQUIRED_FILES = [
    "app/source_roadmap/__init__.py",
    "app/source_roadmap/schemas.py",
    "app/source_roadmap/policy.py",
    "app/source_roadmap/roadmap_builder.py",
    "scripts/orchestrator/build_external_source_connector_roadmap.py",
    "scripts/orchestrator/validate_external_source_connector_roadmap_v1.py",
    "templates/external_source_connector_roadmap.example.json",
    "docs/ai_dev_132_external_source_connector_roadmap_priority_policy_v1.md",
    "docs/runbooks/external_source_connector_roadmap_runbook.md",
]
REQUIRED_POLICY_FIELDS = {
    "source_id", "source_name", "current_status", "source_priority", "decision_value", "freshness_requirement",
    "reliability_risk", "explainability_value", "credential_requirement", "implementation_complexity", "production_risk",
    "recommended_phase", "prediction_context_candidate", "formal_report_candidate", "low_priority_metadata_only",
    "rating_action_confidence_allowed", "rationale",
}
REQUIRED_ROADMAP_FIELDS = {
    "immediate_candidates", "report_integration_candidates", "connector_build_candidates", "defer_or_metadata_only",
    "blocked_or_requires_manual_review", "prediction_context_first", "formal_report_first", "must_not_affect_rating_action_confidence",
}

def expect(condition: bool, reasons: list[str], message: str) -> None:
    if not condition:
        reasons.append(message)

def run_builder() -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, "scripts/orchestrator/build_external_source_connector_roadmap.py"], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except Exception:
        return proc.returncode, {"parse_error": proc.stderr or proc.stdout}

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-132 external source connector roadmap V1")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    reasons: list[str] = []

    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    expect(not missing, reasons, f"missing required files: {missing}")

    artifact = build_external_source_connector_roadmap(ROOT)
    expect(artifact.get("schema_version") == SCHEMA_VERSION, reasons, "schema_version mismatch")
    policies = artifact.get("priority_policy", [])
    expect(len(policies) == 15, reasons, f"expected 15 source policies, got {len(policies)}")
    source_ids = {row.get("source_id") for row in policies}
    expect(len(source_ids) == len(policies), reasons, "source ids must be unique")

    for idx, row in enumerate(policies):
        label = f"priority_policy[{idx}]"
        expect(REQUIRED_POLICY_FIELDS <= set(row), reasons, f"{label} missing fields: {sorted(REQUIRED_POLICY_FIELDS - set(row))}")
        expect(row.get("current_status") in STATUSES, reasons, f"{label} invalid current_status")
        expect(row.get("source_priority") in SOURCE_PRIORITIES, reasons, f"{label} invalid source_priority")
        expect(row.get("decision_value") in DECISION_VALUES, reasons, f"{label} invalid decision_value")
        expect(row.get("reliability_risk") in RISK_LEVELS, reasons, f"{label} invalid reliability_risk")
        expect(row.get("explainability_value") in DECISION_VALUES, reasons, f"{label} invalid explainability_value")
        expect(row.get("implementation_complexity") in COMPLEXITY_LEVELS, reasons, f"{label} invalid implementation_complexity")
        expect(row.get("production_risk") in RISK_LEVELS, reasons, f"{label} invalid production_risk")
        expect(row.get("recommended_phase") in PHASES, reasons, f"{label} invalid recommended_phase")
        for field in ["prediction_context_candidate", "formal_report_candidate", "low_priority_metadata_only", "rating_action_confidence_allowed"]:
            expect(isinstance(row.get(field), bool), reasons, f"{label} {field} must be boolean")

    roadmap = artifact.get("roadmap", {})
    expect(REQUIRED_ROADMAP_FIELDS <= set(roadmap), reasons, f"roadmap missing fields: {sorted(REQUIRED_ROADMAP_FIELDS - set(roadmap))}")
    for key in REQUIRED_ROADMAP_FIELDS:
        expect(isinstance(roadmap.get(key), list), reasons, f"roadmap {key} must be list")
    expect("twse_openapi" in roadmap.get("report_integration_candidates", []), reasons, "TWSE should be report integration candidate")
    expect("mops_public_information_observatory" in roadmap.get("connector_build_candidates", []), reasons, "MOPS should be connector build candidate")
    expect("google_news_rss" in roadmap.get("defer_or_metadata_only", []), reasons, "Google News should defer/metadata only")
    expect("analyst_target_broker_opinion" in roadmap.get("blocked_or_requires_manual_review", []), reasons, "Analyst/broker opinion requires manual review")
    for source_id in ["google_news_rss", "gemini_google_generative_ai", "management_interviews", "analyst_target_broker_opinion"]:
        expect(source_id in roadmap.get("must_not_affect_rating_action_confidence", []), reasons, f"{source_id} must not affect rating/action/confidence")

    example = json.loads((ROOT / "templates/external_source_connector_roadmap.example.json").read_text(encoding="utf-8")) if (ROOT / "templates/external_source_connector_roadmap.example.json").exists() else {}
    expect(example.get("schema_version") == SCHEMA_VERSION, reasons, "example artifact schema mismatch")
    rc, built = run_builder()
    expect(rc == 0 and built.get("schema_version") == SCHEMA_VERSION, reasons, "builder must print valid roadmap JSON")

    safety = artifact.get("safety_summary", {})
    for key in ["external_api_called", "secrets_read", "production_scheduler_modified", "line_sent", "email_sent", "dashboard_published", "production_db_write", "broker_login", "simulation_order", "production_order", "trading_execution", "production_rating_action_confidence_weight_changed"]:
        expect(safety.get(key) is False, reasons, f"safety flag must be false: {key}")

    result = {
        "ok": not reasons,
        "passed": not reasons,
        "reasons": reasons,
        "checks": {
            "required_files": len(REQUIRED_FILES) - len(missing),
            "policy_count": len(policies),
            "phase_counts": artifact.get("phase_summary", {}).get("phase_counts", {}),
            "immediate_candidates": roadmap.get("immediate_candidates", []),
            "connector_build_candidates": roadmap.get("connector_build_candidates", []),
            "defer_or_metadata_only": roadmap.get("defer_or_metadata_only", []),
        },
        "side_effects": {
            "external_api_called": False,
            "secrets_read": False,
            "line_sent": False,
            "email_sent": False,
            "dashboard_published": False,
            "production_db_write": False,
            "trading_execution_run": False,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if not reasons else 2

if __name__ == "__main__":
    raise SystemExit(main())
