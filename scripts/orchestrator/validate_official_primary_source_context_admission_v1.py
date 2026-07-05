#!/usr/bin/env python3
"""Validate AI-DEV-141 Official Primary Source Context Admission foundation."""
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

from app.official_sources.builder import build_official_primary_source_context_admission_artifact
from app.official_sources.schemas import (
    ADMISSION_FIELDS,
    EXISTING_SOURCE_POLICIES,
    INTEGRATION_TARGETS,
    MUTATION_FALSE_FLAGS,
    REQUIRED_FIELDS,
    SAFETY_FALSE_FLAGS,
    SCHEMA_VERSION,
    SOURCE_FAMILIES,
    SOURCE_FAMILY_FIELDS,
    TASK_ID,
)

REQUIRED_FILES = [
    "app/official_sources/__init__.py",
    "app/official_sources/schemas.py",
    "app/official_sources/builder.py",
    "scripts/orchestrator/build_official_primary_source_context_admission_artifact.py",
    "scripts/orchestrator/validate_official_primary_source_context_admission_v1.py",
    "templates/official_primary_source_context_admission_input.example.json",
    "templates/official_primary_source_context_admission_artifact.example.json",
    "docs/ai_dev_141_official_primary_source_connector_context_admission_foundation_v1.md",
    "docs/runbooks/official_primary_source_context_admission_runbook.md",
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


def require_keys(obj: dict[str, Any], keys: list[str], label: str, errors: list[str]) -> None:
    for key in keys:
        if key not in obj:
            errors.append(f"{label} missing key: {key}")


def check_secret_patterns(errors: list[str]) -> None:
    for rel in REQUIRED_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
        if hits:
            errors.append(f"secret-like pattern in {rel}: {hits}")


def validate_artifact(input_payload: dict[str, Any], artifact: dict[str, Any], errors: list[str]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if artifact.get("task_id") != TASK_ID:
        errors.append("task_id mismatch")
    for field in REQUIRED_FIELDS:
        if field not in artifact:
            errors.append(f"missing required field: {field}")

    families = artifact.get("source_families", [])
    family_by_id = {row.get("source_id"): row for row in families}
    for family in SOURCE_FAMILIES:
        if family not in family_by_id:
            errors.append(f"missing source family: {family}")
        else:
            require_keys(family_by_id[family], SOURCE_FAMILY_FIELDS, f"source_family[{family}]", errors)
            row = family_by_id[family]
            for key in ["credential_required", "external_api_required", "production_connector_exists", "direct_rating_action_confidence_impact", "official_source_replacement_allowed"]:
                if row.get(key) is not False:
                    errors.append(f"{family}.{key} must be false")
            if row.get("deterministic_sample_available") is not True:
                errors.append(f"{family}.deterministic_sample_available must be true")

    official_core = {
        "mops_public_information_observatory",
        "company_announcements",
        "financial_statements",
        "monthly_revenue",
        "investor_conference",
        "company_ir_materials",
    }
    industry_context = {"industry_supply_chain", "peer_company_context"}
    matrix = {row.get("source_id"): row for row in artifact.get("admission_matrix", [])}
    for family in SOURCE_FAMILIES:
        if family not in matrix:
            errors.append(f"missing admission matrix row: {family}")
            continue
        row = matrix[family]
        require_keys(row, ADMISSION_FIELDS, f"admission_matrix[{family}]", errors)
        for key in ["prediction_context_allowed", "report_assembly_allowed", "dashboard_drilldown_allowed", "decision_feedback_allowed"]:
            if row.get(key) is not True:
                errors.append(f"{family}.{key} must be true")
        if row.get("production_decision_mutation_allowed") is not False:
            errors.append(f"{family}.production_decision_mutation_allowed must be false")
        if row.get("direct_rating_action_confidence_impact") is not False:
            errors.append(f"{family}.direct_rating_action_confidence_impact must be false")
        if family in official_core:
            if row.get("core_forecast_evidence_allowed") is not True or row.get("explainability_evidence_allowed") is not True:
                errors.append(f"official source must be core evidence: {family}")
        if family in industry_context and row.get("core_forecast_evidence_allowed") is not False:
            errors.append(f"context-only source must not be core evidence: {family}")

    priority = artifact.get("source_priority_policy", {})
    expected_priority = {
        "mops_and_company_announcements": "official_primary_source",
        "financial_statements_and_monthly_revenue": "official_financial_source",
        "investor_conference_and_company_ir_materials": "official_ir_source",
        "industry_supply_chain": "industry_context_source",
        "peer_company_context": "peer_context_source",
        "finmind": "normalized_external_data_provider_assist_only_not_replacement",
        "twse": "official_market_chip_source",
        "yfinance_yahoo": "external_reference_proxy_not_official",
        "google_news_rss": "event_sentiment_support_only_not_core_forecast_evidence",
        "broker_target_analyst_opinion": "metadata_only_no_rating_action_confidence_impact",
    }
    for key, value in expected_priority.items():
        if priority.get(key) != value:
            errors.append(f"source priority mismatch: {key}")

    replacement = artifact.get("official_source_replacement_policy", {})
    for key in ["official_source_replacement_allowed", "finmind_can_replace_official_source", "yfinance_can_replace_official_source", "google_news_can_be_core_forecast_evidence", "broker_target_can_affect_rating_action_confidence", "gemini_ai_generated_analysis_is_original_evidence"]:
        if replacement.get(key) is not False:
            errors.append(f"replacement policy flag must be false: {key}")

    existing = artifact.get("relationship_to_existing_sources", {})
    for source_id, policy in EXISTING_SOURCE_POLICIES.items():
        if source_id not in existing:
            errors.append(f"missing relationship policy: {source_id}")
            continue
        for key, value in policy.items():
            if existing[source_id].get(key) != value:
                errors.append(f"relationship policy mismatch: {source_id}.{key}")

    targets = {(row.get("task_id"), row.get("schema_version")) for row in artifact.get("integration_targets", [])}
    for task_id, schema in INTEGRATION_TARGETS:
        if (task_id, schema) not in targets:
            errors.append(f"missing integration target: {task_id}/{schema}")
    mutation = artifact.get("mutation_policy", {})
    if mutation.get("policy_definition_only") is not True or mutation.get("human_review_required_for_connector_activation") is not True:
        errors.append("mutation policy must be definition-only and human-gated")
    for key in MUTATION_FALSE_FLAGS:
        if mutation.get(key) is not False:
            errors.append(f"mutation flag must be false: {key}")
    safety = artifact.get("safety_policy", {})
    for key in ["read_only", "offline_sample_only", "context_admission_artifact_only", "not_production_crawler", "not_runtime_connector", "no_mops_or_company_api_calls"]:
        if safety.get(key) is not True:
            errors.append(f"safety flag must be true: {key}")
    for key in SAFETY_FALSE_FLAGS:
        if safety.get(key) is not False:
            errors.append(f"safety flag must be false: {key}")

    rebuilt = build_official_primary_source_context_admission_artifact(input_payload)
    if rebuilt != artifact:
        errors.append("artifact template does not match deterministic builder output")


def validate_docs(errors: list[str]) -> None:
    doc = (ROOT / "docs/ai_dev_141_official_primary_source_connector_context_admission_foundation_v1.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/runbooks/official_primary_source_context_admission_runbook.md").read_text(encoding="utf-8")
    phrases = [
        "V10 official source admission foundation",
        "not a production crawler",
        "does not call MOPS / company websites / external APIs",
        "does not modify production connector",
        "does not change rating/action/confidence",
        "AI-DEV-136",
        "AI-DEV-137",
        "AI-DEV-138",
        "AI-DEV-139",
        "AI-DEV-140",
        "FinMind can assist but cannot replace official sources",
        "broker target price / analyst rating is metadata only",
    ]
    for phrase in phrases:
        if phrase not in doc:
            errors.append(f"doc missing required phrase: {phrase}")
    for phrase in ["offline", "build_official_primary_source_context_admission_artifact.py", "validate_official_primary_source_context_admission_v1.py", "no external API", "no production connector"]:
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
    input_payload = read_json("templates/official_primary_source_context_admission_input.example.json")
    artifact = read_json("templates/official_primary_source_context_admission_artifact.example.json")
    validate_artifact(input_payload, artifact, errors)
    validate_docs(errors)
    proc = subprocess.run([str(ROOT / "venv/bin/python"), "scripts/orchestrator/build_official_primary_source_context_admission_artifact.py", "--pretty"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
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
            "source_family_count": len(artifact.get("source_families", [])),
            "admission_matrix_count": len(artifact.get("admission_matrix", [])),
            "integration_target_count": len(artifact.get("integration_targets", [])),
            "official_source_replacement_allowed": artifact.get("official_source_replacement_policy", {}).get("official_source_replacement_allowed"),
            "finmind_can_replace_official_source": artifact.get("official_source_replacement_policy", {}).get("finmind_can_replace_official_source"),
            "yfinance_can_replace_official_source": artifact.get("official_source_replacement_policy", {}).get("yfinance_can_replace_official_source"),
            "external_api_called": artifact.get("safety_policy", {}).get("external_api_called"),
            "secrets_read": artifact.get("safety_policy", {}).get("secrets_read"),
            "production_connector_modified": artifact.get("mutation_policy", {}).get("production_connector_modified"),
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
