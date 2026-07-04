#!/usr/bin/env python3
"""Validate AI-DEV-138 Context-Based Report Assembly foundation."""
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

from app.report_assembly.builder import build_context_based_report_assembly_artifact
from app.report_assembly.schemas import DASHBOARD_BLOCK_IDS, EMAIL_BLOCK_IDS, LINE_BLOCK_IDS, REPORT_SECTION_IDS, REQUIRED_FIELDS, SAFETY_FALSE_FLAGS, SCHEMA_VERSION, SOURCE_CATEGORIES, TASK_ID

REQUIRED_FILES = [
    "app/report_assembly/__init__.py",
    "app/report_assembly/schemas.py",
    "app/report_assembly/builder.py",
    "scripts/orchestrator/build_context_based_report_assembly_artifact.py",
    "scripts/orchestrator/validate_context_based_report_assembly_v1.py",
    "templates/context_based_report_assembly_input.example.json",
    "templates/context_based_report_assembly_artifact.example.json",
    "docs/ai_dev_138_context_based_report_assembly_foundation_v1.md",
    "docs/runbooks/context_based_report_assembly_runbook.md",
]
SECRET_PATTERNS = [re.compile(p, re.I) for p in [r"ghp_[A-Za-z0-9]+", r"github_pat_[A-Za-z0-9_]+", r"sk-[A-Za-z0-9]+", r"BEGIN (RSA|OPENSSH) PRIVATE KEY", r"api[_-]?key\s*[:=]", r"access[_-]?token\s*[:=]", r"password\s*[:=]"]]


def read_json(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


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
    if artifact.get("context_ref", {}).get("schema_version") != "prediction_context_v1":
        errors.append("context_ref must point to prediction_context_v1")
    if artifact.get("explainability_ref", {}).get("schema_version") != "unified_explainability_evidence_trace_v1":
        errors.append("explainability_ref must point to unified explainability artifact")
    section_ids = [section.get("section_id") for section in artifact.get("report_sections", [])]
    for section_id in REPORT_SECTION_IDS:
        if section_id not in section_ids:
            errors.append(f"missing report section: {section_id}")
    for section in artifact.get("report_sections", []):
        if section.get("deterministic") is not True:
            errors.append(f"report section must be deterministic: {section.get('section_id')}")
        if section.get("direct_rating_action_confidence_impact") is not False:
            errors.append(f"report section direct impact must be false: {section.get('section_id')}")
    category_ids = [row.get("category") for row in artifact.get("source_credibility_section", {}).get("categories", [])]
    for category in SOURCE_CATEGORIES:
        if category not in category_ids:
            errors.append(f"missing source credibility category: {category}")
    integrations = artifact.get("formal_report_integration_section", {}).get("integrations", [])
    integration_ids = [row.get("integration_id") for row in integrations]
    for expected in ["finmind_report_integration", "twse_report_integration", "yfinance_yahoo_report_integration"]:
        if expected not in integration_ids:
            errors.append(f"missing formal report integration: {expected}")
    warnings = artifact.get("warning_section", {}).get("warnings", [])
    warning_sources = {row.get("source_id") for row in warnings}
    for expected in ["broker_target_price_metadata", "google_news_rss", "yfinance_yahoo", "finmind", "gemini_google_generative_ai"]:
        if expected not in warning_sources:
            errors.append(f"missing warning source: {expected}")
    exclusions = artifact.get("exclusion_section", {}).get("exclusion_reasons", {})
    checks = {
        "broker_target_price_metadata": "metadata only",
        "google_news_rss": "cannot be core forecast evidence",
        "yfinance_yahoo": "cannot replace official sources",
        "finmind": "cannot replace MOPS / TWSE / company official information",
        "gemini_google_generative_ai": "not original evidence",
    }
    for source_id, phrase in checks.items():
        if phrase not in exclusions.get(source_id, ""):
            errors.append(f"exclusion missing phrase for {source_id}: {phrase}")
    for field in ["market_regime_section", "rolling_evaluation_section", "warning_section", "exclusion_section", "evidence_trace_section", "factor_rationale_section", "formal_report_integration_section"]:
        if artifact.get(field, {}).get("direct_rating_action_confidence_impact") is not False:
            errors.append(f"section direct impact must be false: {field}")
    dashboard_ids = [row.get("block_id") for row in artifact.get("dashboard_ready_blocks", [])]
    email_ids = [row.get("block_id") for row in artifact.get("email_ready_blocks", [])]
    line_ids = [row.get("block_id") for row in artifact.get("line_summary_blocks", [])]
    for block_id in DASHBOARD_BLOCK_IDS:
        if block_id not in dashboard_ids:
            errors.append(f"missing dashboard block: {block_id}")
    for block_id in EMAIL_BLOCK_IDS:
        if block_id not in email_ids:
            errors.append(f"missing email block: {block_id}")
    for block_id in LINE_BLOCK_IDS:
        if block_id not in line_ids:
            errors.append(f"missing LINE summary block: {block_id}")
    for row in artifact.get("dashboard_ready_blocks", []) + artifact.get("email_ready_blocks", []) + artifact.get("line_summary_blocks", []):
        if row.get("deterministic") is not True:
            errors.append(f"block must be deterministic: {row.get('block_id')}")
    delivery = artifact.get("delivery_policy", {})
    if delivery.get("line_allowed_for_summary_only") is not True:
        errors.append("LINE must be summary-only")
    if delivery.get("email_allowed_for_full_report") is not True:
        errors.append("email full report policy missing")
    if delivery.get("dashboard_allowed_for_full_report_and_drilldown") is not True:
        errors.append("dashboard full report/drilldown policy missing")
    for key in ["delivery_executed", "dashboard_published", "external_notification_sent", "production_delivery_behavior_modified"]:
        if delivery.get(key) is not False:
            errors.append(f"delivery flag must be false: {key}")
    safety = artifact.get("safety_policy", {})
    for key in ["read_only", "offline_sample_only", "report_assembly_artifact_only", "not_production_renderer", "not_production_decision_engine", "no_direct_rating_action_confidence_change"]:
        if safety.get(key) is not True:
            errors.append(f"safety flag must be true: {key}")
    for key in SAFETY_FALSE_FLAGS:
        if safety.get(key) is not False:
            errors.append(f"safety flag must be false: {key}")
    rebuilt = build_context_based_report_assembly_artifact(input_payload["prediction_context"], input_payload["unified_explainability"])
    if rebuilt != artifact:
        errors.append("artifact template does not match deterministic builder output")


def validate_docs(errors: list[str]) -> None:
    doc = (ROOT / "docs/ai_dev_138_context_based_report_assembly_foundation_v1.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/runbooks/context_based_report_assembly_runbook.md").read_text(encoding="utf-8")
    phrases = [
        "V10 Unified Decision Intelligence",
        "reads AI-DEV-136 Prediction Context",
        "reads AI-DEV-137 Explainability / Evidence Trace",
        "not a production renderer",
        "does not send LINE / Email",
        "does not publish dashboard",
        "does not modify production report delivery",
        "AI-DEV-139",
        "AI-DEV-140",
        "No external API calls",
        "No secrets",
        "No broker / order / trading",
    ]
    for phrase in phrases:
        if phrase not in doc:
            errors.append(f"doc missing required phrase: {phrase}")
    for phrase in ["offline", "build_context_based_report_assembly_artifact.py", "validate_context_based_report_assembly_v1.py", "no production pipeline"]:
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
    input_payload = read_json("templates/context_based_report_assembly_input.example.json")
    artifact = read_json("templates/context_based_report_assembly_artifact.example.json")
    validate_artifact(input_payload, artifact, errors)
    validate_docs(errors)
    proc = subprocess.run([str(ROOT / "venv/bin/python"), "scripts/orchestrator/build_context_based_report_assembly_artifact.py", "--pretty"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        errors.append(f"builder failed: {proc.stderr.strip()}")
    else:
        json.loads(proc.stdout)
    return {"ok": not errors, "task_id": TASK_ID, "errors": errors, "warnings": warnings, "summary": {"schema_version": artifact.get("schema_version"), "symbol": artifact.get("symbol"), "market": artifact.get("market"), "report_section_count": len(artifact.get("report_sections", [])), "dashboard_block_count": len(artifact.get("dashboard_ready_blocks", [])), "email_block_count": len(artifact.get("email_ready_blocks", [])), "line_summary_block_count": len(artifact.get("line_summary_blocks", [])), "warning_count": len(artifact.get("warning_section", {}).get("warnings", [])), "delivery_executed": artifact.get("delivery_policy", {}).get("delivery_executed"), "dashboard_published": artifact.get("delivery_policy", {}).get("dashboard_published"), "external_notification_sent": artifact.get("delivery_policy", {}).get("external_notification_sent"), "direct_rating_action_confidence_impact": False, "secret_pattern_hits": 0 if not errors else "see_errors"}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("ok") else 1

if __name__ == "__main__":
    raise SystemExit(main())
