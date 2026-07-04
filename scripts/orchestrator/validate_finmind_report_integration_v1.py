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

from app.finmind_report.artifact_builder import build_finmind_report_integration_artifact
from app.finmind_report.sample_data import offline_sample_input
from app.finmind_report.schemas import SCHEMA_VERSION, SUPPORTED_SECTION_TYPES

REQUIRED_FILES = [
    "app/sources/finmind_connector.py",
    "app/finmind_report/__init__.py",
    "app/finmind_report/schemas.py",
    "app/finmind_report/sample_data.py",
    "app/finmind_report/artifact_builder.py",
    "scripts/orchestrator/build_finmind_report_integration_artifact.py",
    "scripts/orchestrator/validate_finmind_report_integration_v1.py",
    "templates/finmind_report_integration_input.example.json",
    "templates/finmind_report_integration_artifact.example.json",
    "docs/ai_dev_133_finmind_formal_report_integration_foundation_v1.md",
    "docs/runbooks/finmind_report_integration_runbook.md",
]
REQUIRED_ARTIFACT_FIELDS = {"schema_version", "generated_at", "input_summary", "source_attribution", "freshness_policy", "report_sections", "explainability_notes", "integration_policy", "safety_summary", "advisory_only"}
REQUIRED_SECTION_FIELDS = {"section_id", "section_type", "title", "summary", "metrics", "source_ids", "freshness_policy", "explainability_notes", "limitations"}

def expect(condition: bool, reasons: list[str], message: str) -> None:
    if not condition:
        reasons.append(message)

def run_builder() -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, "scripts/orchestrator/build_finmind_report_integration_artifact.py"], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except Exception:
        return proc.returncode, {"parse_error": proc.stderr or proc.stdout}

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-133 FinMind report integration V1")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    reasons: list[str] = []

    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    expect(not missing, reasons, f"missing required files: {missing}")

    connector_text = (ROOT / "app/sources/finmind_connector.py").read_text(encoding="utf-8")
    expect("allow_network" in connector_text and "_offline" in connector_text, reasons, "FinMind connector must expose offline/no-network behavior")

    artifact = build_finmind_report_integration_artifact(offline_sample_input())
    expect(REQUIRED_ARTIFACT_FIELDS <= set(artifact), reasons, f"artifact missing fields: {sorted(REQUIRED_ARTIFACT_FIELDS - set(artifact))}")
    expect(artifact.get("schema_version") == SCHEMA_VERSION, reasons, "schema_version mismatch")
    expect(artifact.get("source_attribution", {}).get("provider") == "FinMind", reasons, "source attribution provider must be FinMind")
    expect(artifact.get("source_attribution", {}).get("external_api_called") is False, reasons, "builder must not call external API")
    expect(artifact.get("source_attribution", {}).get("api_token_required_for_builder") is False, reasons, "builder must not require API token")
    expect(artifact.get("source_attribution", {}).get("official_source_replacement_allowed") is False, reasons, "FinMind must not replace official governance")
    expect(artifact.get("integration_policy", {}).get("direct_rating_action_confidence_impact") is False, reasons, "direct rating/action/confidence impact must be false")
    expect(artifact.get("integration_policy", {}).get("production_weight_mutation_allowed") is False, reasons, "production weight mutation must be false")

    sections = artifact.get("report_sections", [])
    section_types = {section.get("section_type") for section in sections}
    expect(section_types == SUPPORTED_SECTION_TYPES, reasons, f"section coverage mismatch: {sorted(SUPPORTED_SECTION_TYPES - section_types)}")
    for index, section in enumerate(sections):
        label = f"report_sections[{index}]"
        expect(REQUIRED_SECTION_FIELDS <= set(section), reasons, f"{label} missing fields")
        expect(section.get("section_type") in SUPPORTED_SECTION_TYPES, reasons, f"{label} invalid section_type")
        expect(section.get("source_ids") and all(str(s).startswith("finmind_") for s in section.get("source_ids", [])), reasons, f"{label} source attribution invalid")
        expect(section.get("freshness_policy"), reasons, f"{label} freshness_policy required")
        expect(section.get("explainability_notes"), reasons, f"{label} explainability_notes required")

    example_input = json.loads((ROOT / "templates/finmind_report_integration_input.example.json").read_text(encoding="utf-8")) if (ROOT / "templates/finmind_report_integration_input.example.json").exists() else {}
    example_artifact = json.loads((ROOT / "templates/finmind_report_integration_artifact.example.json").read_text(encoding="utf-8")) if (ROOT / "templates/finmind_report_integration_artifact.example.json").exists() else {}
    expect(example_input.get("schema_version") == "finmind_report_integration_input_v1", reasons, "input example schema mismatch")
    expect(example_artifact.get("schema_version") == SCHEMA_VERSION, reasons, "artifact example schema mismatch")

    rc, built = run_builder()
    expect(rc == 0 and built.get("schema_version") == SCHEMA_VERSION, reasons, "builder must print valid JSON")

    safety = artifact.get("safety_summary", {})
    for key in ["external_api_called", "finmind_api_token_required", "secrets_read", "production_scheduler_modified", "line_sent", "email_sent", "dashboard_published", "production_db_write", "broker_login", "simulation_order", "production_order", "trading_execution", "production_rating_action_confidence_weight_changed"]:
        expect(safety.get(key) is False, reasons, f"safety flag must be false: {key}")

    result = {
        "ok": not reasons,
        "passed": not reasons,
        "reasons": reasons,
        "checks": {
            "required_files": len(REQUIRED_FILES) - len(missing),
            "section_count": len(sections),
            "section_types": sorted(section_types),
            "provider": artifact.get("source_attribution", {}).get("provider"),
            "direct_rating_action_confidence_impact": artifact.get("integration_policy", {}).get("direct_rating_action_confidence_impact"),
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
