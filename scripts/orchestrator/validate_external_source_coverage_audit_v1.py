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

from app.source_audit.audit_builder import build_external_source_coverage_audit
from app.source_audit.schemas import GAP_CLASSES, READINESS, SCHEMA_VERSION, SOURCE_PRIORITIES, STATUSES

REQUIRED_FILES = [
    "app/source_audit/__init__.py",
    "app/source_audit/schemas.py",
    "app/source_audit/repo_scanner.py",
    "app/source_audit/source_catalog.py",
    "app/source_audit/audit_builder.py",
    "scripts/orchestrator/build_external_source_coverage_audit.py",
    "scripts/orchestrator/validate_external_source_coverage_audit_v1.py",
    "templates/external_source_coverage_audit.example.json",
    "docs/ai_dev_131_external_source_coverage_connector_completion_audit_v1.md",
    "docs/runbooks/external_source_coverage_audit_runbook.md",
]
REQUIRED_SOURCE_IDS = {
    "google_sheet",
    "shioaji_sinopac",
    "twse_openapi",
    "google_news_rss",
    "yfinance_yahoo",
    "gemini_google_generative_ai",
    "sqlite_historical_csv",
    "mops_public_information_observatory",
    "company_announcements",
    "financial_statements",
    "investor_conference",
    "management_interviews",
    "industry_supply_chain",
    "etf_index_sector_proxy",
    "analyst_target_broker_opinion",
}
REQUIRED_FIELDS = {
    "source_id", "source_name", "source_type", "provider", "current_status", "connector_exists",
    "runtime_used", "artifact_used", "report_used", "dashboard_used", "prediction_used", "evaluation_used",
    "credential_required", "freshness_policy", "failure_mode", "source_priority", "explainability_support",
    "production_readiness", "gaps", "recommended_next_action",
}

def expect(condition: bool, reasons: list[str], message: str) -> None:
    if not condition:
        reasons.append(message)

def run_builder() -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, "scripts/orchestrator/build_external_source_coverage_audit.py"], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except Exception:
        return proc.returncode, {"parse_error": proc.stderr or proc.stdout}

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-131 external source coverage audit V1")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    reasons: list[str] = []

    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    expect(not missing, reasons, f"missing required files: {missing}")

    artifact = build_external_source_coverage_audit(ROOT)
    expect(artifact.get("schema_version") == SCHEMA_VERSION, reasons, "schema_version mismatch")
    records = artifact.get("source_records", [])
    ids = {r.get("source_id") for r in records}
    expect(REQUIRED_SOURCE_IDS <= ids, reasons, f"missing required source ids: {sorted(REQUIRED_SOURCE_IDS - ids)}")

    for idx, record in enumerate(records):
        label = f"source_records[{idx}]"
        missing_fields = sorted(REQUIRED_FIELDS - set(record))
        expect(not missing_fields, reasons, f"{label} missing fields: {missing_fields}")
        expect(record.get("current_status") in STATUSES, reasons, f"{label} invalid current_status")
        expect(record.get("production_readiness") in READINESS, reasons, f"{label} invalid production_readiness")
        expect(record.get("source_priority") in SOURCE_PRIORITIES, reasons, f"{label} invalid source_priority")
        expect(isinstance(record.get("gaps"), list) and record.get("gaps"), reasons, f"{label} gaps must be non-empty list")
        for gap in record.get("gaps", []):
            expect(gap in GAP_CLASSES, reasons, f"{label} invalid gap class {gap}")
        for field in ["connector_exists", "runtime_used", "artifact_used", "report_used", "dashboard_used", "prediction_used", "evaluation_used", "credential_required"]:
            expect(isinstance(record.get(field), bool), reasons, f"{label} {field} must be boolean")

    status_set = {r["current_status"] for r in records}
    for required_status in ["production_used", "connector_exists_not_in_formal_report", "inventory_only_not_connectorized", "needs_connector", "low_priority_metadata_only"]:
        expect(required_status in status_set, reasons, f"missing status classification: {required_status}")

    by_id = {r["source_id"]: r for r in records}
    expect(by_id["google_sheet"]["runtime_used"] is True, reasons, "Google Sheet should be production/runtime used")
    expect(by_id["twse_openapi"]["connector_exists"] is True and by_id["twse_openapi"]["report_used"] is False, reasons, "TWSE should be connector exists but not formal report")
    expect(by_id["mops_public_information_observatory"]["current_status"] == "inventory_only_not_connectorized", reasons, "MOPS should be inventory only")
    expect(by_id["analyst_target_broker_opinion"]["current_status"] in {"needs_connector", "low_priority_metadata_only"}, reasons, "analyst target should be low priority or needs connector")
    expect(by_id["google_news_rss"]["production_readiness"] == "not_recommended_primary", reasons, "Google News must not be primary")
    expect(by_id["management_interviews"]["production_readiness"] == "not_recommended_primary", reasons, "management interviews must not be primary")

    example = json.loads((ROOT / "templates/external_source_coverage_audit.example.json").read_text(encoding="utf-8")) if (ROOT / "templates/external_source_coverage_audit.example.json").exists() else {}
    expect(example.get("schema_version") == SCHEMA_VERSION, reasons, "example artifact schema mismatch")
    rc, built = run_builder()
    expect(rc == 0 and built.get("schema_version") == SCHEMA_VERSION, reasons, "builder must print valid JSON artifact")

    safety = artifact.get("safety_summary", {})
    for key in ["external_api_called", "secrets_read", "production_scheduler_modified", "line_sent", "email_sent", "dashboard_published", "production_db_write", "broker_login", "simulation_order", "production_order", "trading_execution", "production_rating_action_confidence_weight_changed"]:
        expect(safety.get(key) is False, reasons, f"safety flag must be false: {key}")

    result = {
        "ok": not reasons,
        "passed": not reasons,
        "reasons": reasons,
        "checks": {
            "required_files": len(REQUIRED_FILES) - len(missing),
            "source_count": len(records),
            "required_sources_present": sorted(REQUIRED_SOURCE_IDS & ids),
            "status_counts": artifact.get("coverage_summary", {}).get("status_counts", {}),
            "readiness_counts": artifact.get("coverage_summary", {}).get("readiness_counts", {}),
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
