#!/usr/bin/env python3
"""Validate AI-DEV-139 Dashboard Decision Intelligence foundation."""
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

from app.dashboard_intelligence.builder import build_dashboard_decision_intelligence_artifact
from app.dashboard_intelligence.schemas import (
    ADVISORY_ONLY_BADGE_IDS,
    DASHBOARD_PAGE_IDS,
    FORMAL_INTEGRATION_IDS,
    METADATA_ONLY_BADGE_IDS,
    REQUIRED_FIELDS,
    SAFETY_FALSE_FLAGS,
    SCHEMA_VERSION,
    SOURCE_CATEGORIES,
    SUMMARY_CARD_IDS,
    TASK_ID,
)

REQUIRED_FILES = [
    "app/dashboard_intelligence/__init__.py",
    "app/dashboard_intelligence/schemas.py",
    "app/dashboard_intelligence/builder.py",
    "scripts/orchestrator/build_dashboard_decision_intelligence_artifact.py",
    "scripts/orchestrator/validate_dashboard_decision_intelligence_v1.py",
    "templates/dashboard_decision_intelligence_input.example.json",
    "templates/dashboard_decision_intelligence_artifact.example.json",
    "docs/ai_dev_139_dashboard_decision_intelligence_drilldown_foundation_v1.md",
    "docs/runbooks/dashboard_decision_intelligence_drilldown_runbook.md",
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


def _ids(rows: list[dict[str, Any]], key: str) -> list[str]:
    return [row.get(key) for row in rows]


def validate_artifact(input_payload: dict[str, Any], artifact: dict[str, Any], errors: list[str]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if artifact.get("task_id") != TASK_ID:
        errors.append("task_id mismatch")
    for field in REQUIRED_FIELDS:
        if field not in artifact:
            errors.append(f"missing required field: {field}")
    if artifact.get("prediction_context_ref", {}).get("schema_version") != "prediction_context_v1":
        errors.append("prediction_context_ref must point to prediction_context_v1")
    if artifact.get("explainability_ref", {}).get("schema_version") != "unified_explainability_evidence_trace_v1":
        errors.append("explainability_ref must point to unified explainability artifact")
    if artifact.get("report_assembly_ref", {}).get("schema_version") != "context_based_report_assembly_v1":
        errors.append("report_assembly_ref must point to context_based_report_assembly_v1")

    for page_id in DASHBOARD_PAGE_IDS:
        if page_id not in _ids(artifact.get("dashboard_page_model", []), "page_id"):
            errors.append(f"missing dashboard page: {page_id}")
    for card_id in SUMMARY_CARD_IDS:
        if card_id not in _ids(artifact.get("summary_cards", []), "card_id"):
            errors.append(f"missing summary card: {card_id}")
    for category in SOURCE_CATEGORIES:
        if category not in _ids(artifact.get("source_credibility_cards", []), "category"):
            errors.append(f"missing source credibility card: {category}")
    for integration_id in FORMAL_INTEGRATION_IDS:
        if integration_id not in _ids(artifact.get("formal_integration_cards", []), "integration_id"):
            errors.append(f"missing formal integration card: {integration_id}")
    for badge_id in METADATA_ONLY_BADGE_IDS:
        if badge_id not in _ids(artifact.get("metadata_only_badges", []), "badge_id"):
            errors.append(f"missing metadata-only badge: {badge_id}")
    advisory_badges = {row.get("badge_id"): row for row in artifact.get("advisory_only_badges", [])}
    for badge_id in ADVISORY_ONLY_BADGE_IDS:
        if badge_id not in advisory_badges:
            errors.append(f"missing advisory-only badge: {badge_id}")
    advisory_checks = {
        "advisory_only": "advisory_only",
        "not_trading_advice": "not_trading_advice",
        "no_order_execution": "no_order_execution",
        "no_direct_rating_action_confidence_mutation": "no_direct_rating_action_confidence_mutation",
    }
    for badge_id, flag in advisory_checks.items():
        if advisory_badges.get(badge_id, {}).get(flag) is not True:
            errors.append(f"advisory badge flag missing: {badge_id}.{flag}")

    if not artifact.get("factor_rationale_cards"):
        errors.append("factor_rationale_cards must not be empty")
    for row in artifact.get("factor_rationale_cards", []):
        for key in ["factor_id", "factor_name", "factor_category", "rationale_summary", "supporting_sources", "allowed_usage", "disallowed_usage", "direct_rating_action_confidence_impact"]:
            if key not in row:
                errors.append(f"factor rationale card missing {key}: {row.get('card_id')}")
        if row.get("direct_rating_action_confidence_impact") is not False:
            errors.append(f"factor rationale direct impact must be false: {row.get('card_id')}")
    if not artifact.get("evidence_trace_cards"):
        errors.append("evidence_trace_cards must not be empty")
    for row in artifact.get("evidence_trace_cards", []):
        for key in ["source_id", "context_section", "factor_id", "explanation_id", "report_block_id", "dashboard_block_id", "trace_summary", "node_count", "edge_count"]:
            if key not in row:
                errors.append(f"evidence trace card missing {key}: {row.get('card_id')}")
        if row.get("direct_rating_action_confidence_impact") is not False:
            errors.append(f"evidence trace direct impact must be false: {row.get('card_id')}")
    if not artifact.get("warning_cards"):
        errors.append("warning_cards must not be empty")
    warning_sources = {row.get("source_id") for row in artifact.get("warning_cards", [])}
    for expected in ["broker_target_price_metadata", "google_news_rss", "yfinance_yahoo", "finmind", "gemini_google_generative_ai"]:
        if expected not in warning_sources:
            errors.append(f"missing warning source: {expected}")
    exclusion_sources = {row.get("source_id") for row in artifact.get("exclusion_cards", [])}
    for expected in ["broker_target_price_metadata", "google_news_rss", "yfinance_yahoo", "finmind", "gemini_google_generative_ai"]:
        if expected not in exclusion_sources:
            errors.append(f"missing exclusion source: {expected}")

    for link in artifact.get("drilldown_links", []):
        href = link.get("href", "")
        if not href.startswith(f"dashboard://symbol/{artifact.get('symbol')}/"):
            errors.append(f"drilldown link must use deterministic dashboard placeholder: {href}")
        if link.get("published") is not False or link.get("placeholder_only") is not True:
            errors.append(f"drilldown link must be unpublished placeholder: {href}")
    if len(artifact.get("drilldown_links", [])) != len(DASHBOARD_PAGE_IDS):
        errors.append("drilldown_links count mismatch")

    publish = artifact.get("publish_policy", {})
    for key in ["dashboard_ui_modified", "dashboard_published", "dashboard_runtime_modified", "external_notification_sent", "delivery_executed", "production_delivery_behavior_modified"]:
        if publish.get(key) is not False:
            errors.append(f"publish flag must be false: {key}")
    safety = artifact.get("safety_policy", {})
    for key in ["read_only", "offline_sample_only", "dashboard_drilldown_artifact_only", "not_dashboard_ui_implementation", "not_production_dashboard_runtime", "not_production_decision_engine", "no_direct_rating_action_confidence_change"]:
        if safety.get(key) is not True:
            errors.append(f"safety flag must be true: {key}")
    for key in SAFETY_FALSE_FLAGS:
        if safety.get(key) is not False:
            errors.append(f"safety flag must be false: {key}")

    rebuilt = build_dashboard_decision_intelligence_artifact(
        input_payload["prediction_context"],
        input_payload["unified_explainability"],
        input_payload["context_based_report_assembly"],
    )
    if rebuilt != artifact:
        errors.append("artifact template does not match deterministic builder output")


def validate_docs(errors: list[str]) -> None:
    doc = (ROOT / "docs/ai_dev_139_dashboard_decision_intelligence_drilldown_foundation_v1.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/runbooks/dashboard_decision_intelligence_drilldown_runbook.md").read_text(encoding="utf-8")
    phrases = [
        "V10 Unified Decision Intelligence",
        "reads AI-DEV-136 Prediction Context",
        "reads AI-DEV-137 Explainability / Evidence Trace",
        "reads AI-DEV-138 Report Assembly",
        "not a Dashboard UI implementation",
        "does not publish dashboard",
        "does not modify production dashboard runtime",
        "does not send LINE / Email",
        "source credibility",
        "metadata-only",
        "advisory-only",
        "official-source replacement policy",
    ]
    for phrase in phrases:
        if phrase not in doc:
            errors.append(f"doc missing required phrase: {phrase}")
    for phrase in ["offline", "build_dashboard_decision_intelligence_artifact.py", "validate_dashboard_decision_intelligence_v1.py", "no production pipeline", "Dashboard renderer"]:
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
    input_payload = read_json("templates/dashboard_decision_intelligence_input.example.json")
    artifact = read_json("templates/dashboard_decision_intelligence_artifact.example.json")
    validate_artifact(input_payload, artifact, errors)
    validate_docs(errors)
    proc = subprocess.run([str(ROOT / "venv/bin/python"), "scripts/orchestrator/build_dashboard_decision_intelligence_artifact.py", "--pretty"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
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
            "dashboard_page_count": len(artifact.get("dashboard_page_model", [])),
            "summary_card_count": len(artifact.get("summary_cards", [])),
            "source_credibility_card_count": len(artifact.get("source_credibility_cards", [])),
            "factor_rationale_card_count": len(artifact.get("factor_rationale_cards", [])),
            "evidence_trace_card_count": len(artifact.get("evidence_trace_cards", [])),
            "formal_integration_card_count": len(artifact.get("formal_integration_cards", [])),
            "warning_card_count": len(artifact.get("warning_cards", [])),
            "exclusion_card_count": len(artifact.get("exclusion_cards", [])),
            "metadata_only_badge_count": len(artifact.get("metadata_only_badges", [])),
            "advisory_only_badge_count": len(artifact.get("advisory_only_badges", [])),
            "drilldown_link_count": len(artifact.get("drilldown_links", [])),
            "dashboard_published": artifact.get("publish_policy", {}).get("dashboard_published"),
            "dashboard_ui_modified": artifact.get("publish_policy", {}).get("dashboard_ui_modified"),
            "delivery_executed": artifact.get("publish_policy", {}).get("delivery_executed"),
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
