#!/usr/bin/env python3
"""Validate AI-DEV-136 Prediction Context Assembly foundation."""
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

from app.prediction_context.builder import build_prediction_context_artifact
from app.prediction_context.schemas import (
    CREDIBILITY_REQUIRED_FIELDS,
    FORMAL_REPORT_INTEGRATION_IDS,
    REQUIRED_CONTEXT_FIELDS,
    SAFETY_FALSE_FLAGS,
    SCHEMA_VERSION,
    SOURCE_SUMMARY_CATEGORIES,
    TASK_ID,
)

REQUIRED_FILES = [
    "app/prediction_context/__init__.py",
    "app/prediction_context/schemas.py",
    "app/prediction_context/sample_data.py",
    "app/prediction_context/builder.py",
    "scripts/orchestrator/build_prediction_context_artifact.py",
    "scripts/orchestrator/validate_prediction_context_v1.py",
    "templates/prediction_context_input.example.json",
    "templates/prediction_context_artifact.example.json",
    "docs/ai_dev_136_prediction_context_unified_decision_context_v1.md",
    "docs/runbooks/prediction_context_unified_decision_context_runbook.md",
]

SECRET_PATTERNS = [
    re.compile(pattern, re.I)
    for pattern in [
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


def validate_artifact(input_payload: dict[str, Any], artifact: dict[str, Any], errors: list[str]) -> None:
    if input_payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("input schema_version mismatch")
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("artifact schema_version mismatch")
    if artifact.get("task_id") != TASK_ID:
        errors.append("artifact task_id mismatch")
    for field in REQUIRED_CONTEXT_FIELDS:
        if field not in artifact:
            errors.append(f"missing required context field: {field}")
    if sorted(artifact.keys()) != sorted(artifact.keys()):
        errors.append("artifact key ordering check failed")
    source_summary = artifact.get("source_summary", {})
    for category in SOURCE_SUMMARY_CATEGORIES:
        if category not in source_summary:
            errors.append(f"missing source_summary category: {category}")
    rows = artifact.get("source_credibility_summary", [])
    if not isinstance(rows, list) or not rows:
        errors.append("source_credibility_summary must be a non-empty list")
    source_ids = {row.get("source_id") for row in rows if isinstance(row, dict)}
    for row in rows:
        for field in CREDIBILITY_REQUIRED_FIELDS:
            if field not in row:
                errors.append(f"credibility row missing {field}: {row.get('source_id')}")
        if row.get("direct_rating_action_confidence_impact") is not False:
            errors.append(f"source direct impact must be false: {row.get('source_id')}")
        if row.get("source_category") in {"external_reference_proxy", "normalized_external_data_provider", "ai_generated_analysis", "low_priority_metadata"} and row.get("official_source_replacement_allowed") is not False:
            errors.append(f"non-official source cannot replace official source: {row.get('source_id')}")
    integrations = artifact.get("formal_report_integrations", {})
    for integration_id in FORMAL_REPORT_INTEGRATION_IDS:
        if integration_id not in integrations:
            errors.append(f"missing formal report integration: {integration_id}")
    for context_key in [
        "technical_context", "chip_context", "adr_context", "news_context", "finmind_context", "twse_context", "yfinance_context",
        "historical_context", "rolling_evaluation_context", "market_regime_context", "confidence_calibration_context", "factor_effectiveness_context", "explainability_context",
    ]:
        context = artifact.get(context_key, {})
        if isinstance(context, dict) and context.get("direct_rating_action_confidence_impact") is not False:
            errors.append(f"context direct impact must be false: {context_key}")
    exclusions = artifact.get("exclusions", {})
    for key in ["metadata_only_sources", "no_direct_rating_action_confidence_impact_sources", "official_source_replacement_disallowed_sources"]:
        if not isinstance(exclusions.get(key), list):
            errors.append(f"exclusions missing list: {key}")
    for expected_source in ["broker_target_price_metadata", "google_news_rss"]:
        if expected_source not in exclusions.get("metadata_only_sources", []):
            errors.append(f"metadata-only source missing from exclusions: {expected_source}")
    for expected_source in ["finmind", "yfinance_yahoo", "broker_target_price_metadata", "google_news_rss"]:
        if expected_source not in exclusions.get("official_source_replacement_disallowed_sources", []):
            errors.append(f"official replacement exclusion missing: {expected_source}")
    safety = artifact.get("safety_policy", {})
    for key in ["read_only", "offline_sample_only", "context_artifact_only", "not_production_decision_engine", "no_direct_rating_action_confidence_change"]:
        if safety.get(key) is not True:
            errors.append(f"safety flag must be true: {key}")
    for key in SAFETY_FALSE_FLAGS:
        if safety.get(key) is not False:
            errors.append(f"safety flag must be false: {key}")
    rebuilt = build_prediction_context_artifact(input_payload)
    if rebuilt != artifact:
        errors.append("artifact template does not match deterministic builder output")
    for required_source in ["company_filing", "twse_openapi", "finmind", "yfinance_yahoo", "gemini_google_generative_ai"]:
        if required_source not in source_ids:
            errors.append(f"missing source credibility reference: {required_source}")


def validate_docs(errors: list[str]) -> None:
    doc = (ROOT / "docs/ai_dev_136_prediction_context_unified_decision_context_v1.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/runbooks/prediction_context_unified_decision_context_runbook.md").read_text(encoding="utf-8")
    phrases = [
        "V10 Unified Decision Intelligence",
        "context artifact, not a production decision engine",
        "does not directly modify rating/action/confidence",
        "does not trigger report delivery",
        "AI-DEV-137",
        "AI-DEV-138",
        "AI-DEV-139",
        "AI-DEV-140",
        "No external API calls",
        "No secrets",
        "No DB writes",
        "No broker / order / trading",
    ]
    for phrase in phrases:
        if phrase not in doc:
            errors.append(f"doc missing required phrase: {phrase}")
    for phrase in ["offline", "build_prediction_context_artifact.py", "validate_prediction_context_v1.py", "no production pipeline"]:
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
    input_payload = read_json("templates/prediction_context_input.example.json")
    artifact = read_json("templates/prediction_context_artifact.example.json")
    validate_artifact(input_payload, artifact, errors)
    validate_docs(errors)
    proc = subprocess.run([str(ROOT / "venv/bin/python"), "scripts/orchestrator/build_prediction_context_artifact.py", "--pretty"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        errors.append(f"builder failed: {proc.stderr.strip()}")
    else:
        try:
            json.loads(proc.stdout)
        except Exception as exc:
            errors.append(f"builder output is not valid JSON: {exc}")
    return {
        "ok": not errors,
        "task_id": TASK_ID,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "schema_version": artifact.get("schema_version"),
            "symbol": artifact.get("symbol"),
            "market": artifact.get("market"),
            "source_count": len(artifact.get("source_credibility_summary", [])),
            "formal_report_integration_count": len(artifact.get("formal_report_integrations", {})),
            "metadata_only_sources": artifact.get("exclusions", {}).get("metadata_only_sources"),
            "direct_rating_action_confidence_impact": False,
            "external_api_called": False,
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
