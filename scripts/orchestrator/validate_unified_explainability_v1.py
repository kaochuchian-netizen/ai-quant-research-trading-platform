#!/usr/bin/env python3
"""Validate AI-DEV-137 Unified Explainability & Evidence Trace foundation."""
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

from app.explainability.unified_trace_builder import EXCLUSION_REASONS, build_unified_explainability_artifact
from app.explainability.unified_trace_schema import REQUIRED_FIELDS, SAFETY_FALSE_FLAGS, SCHEMA_VERSION, SOURCE_CATEGORIES, TASK_ID, TRACE_REQUIRED_FIELDS

REQUIRED_FILES = [
    "app/explainability/__init__.py",
    "app/explainability/unified_trace_schema.py",
    "app/explainability/unified_trace_builder.py",
    "scripts/orchestrator/build_unified_explainability_artifact.py",
    "scripts/orchestrator/validate_unified_explainability_v1.py",
    "templates/unified_explainability_input.example.json",
    "templates/unified_explainability_artifact.example.json",
    "docs/ai_dev_137_unified_explainability_evidence_trace_foundation_v1.md",
    "docs/runbooks/unified_explainability_evidence_trace_runbook.md",
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
    context_ref = artifact.get("context_ref", {})
    if context_ref.get("schema_version") != "prediction_context_v1":
        errors.append("context_ref must point to prediction_context_v1")
    source_explanations = artifact.get("source_explanations", {})
    for category in SOURCE_CATEGORIES:
        if category not in source_explanations:
            errors.append(f"missing source explanation category: {category}")
    trace_rows = artifact.get("evidence_links", [])
    if not isinstance(trace_rows, list) or not trace_rows:
        errors.append("evidence_links must be a non-empty list")
    for row in trace_rows:
        for field in TRACE_REQUIRED_FIELDS:
            if field not in row:
                errors.append(f"trace row missing field {field}: {row.get('source_id')}")
        if row.get("direct_rating_action_confidence_impact") is not False:
            errors.append(f"trace row direct impact must be false: {row.get('source_id')}")
    graph = artifact.get("evidence_trace_graph", {})
    if not graph.get("nodes") or not graph.get("edges"):
        errors.append("evidence_trace_graph nodes/edges required")
    for edge in graph.get("edges", []):
        if edge.get("direct_rating_action_confidence_impact") is not False:
            errors.append("trace graph edge direct impact must be false")
    exclusions = artifact.get("exclusion_reasons", {})
    for source_id in EXCLUSION_REASONS:
        if source_id not in exclusions:
            errors.append(f"missing exclusion reason: {source_id}")
    if "directly affect rating/action/confidence" not in exclusions.get("broker_target_price_metadata", ""):
        errors.append("broker target exclusion must block rating/action/confidence impact")
    if "cannot be core forecast evidence" not in exclusions.get("google_news_rss", ""):
        errors.append("Google News RSS must not be core forecast evidence")
    if "cannot replace official sources" not in exclusions.get("yfinance_yahoo", ""):
        errors.append("yfinance must not replace official sources")
    if "cannot replace MOPS / TWSE / company official information" not in exclusions.get("finmind", ""):
        errors.append("FinMind must not replace official sources")
    if "not original evidence" not in exclusions.get("gemini_google_generative_ai", ""):
        errors.append("Gemini must not be original evidence")
    confidence = artifact.get("confidence_rationale", {})
    if confidence.get("direct_rating_action_confidence_impact") is not False:
        errors.append("confidence rationale direct impact must be false")
    if "does not rewrite production confidence" not in confidence.get("summary", ""):
        errors.append("confidence rationale must state no production confidence rewrite")
    if not artifact.get("report_explanation_blocks"):
        errors.append("report_explanation_blocks required")
    if not artifact.get("dashboard_explanation_blocks"):
        errors.append("dashboard_explanation_blocks required")
    for block in artifact.get("report_explanation_blocks", []) + artifact.get("dashboard_explanation_blocks", []):
        if block.get("deterministic") is not True:
            errors.append(f"block must be deterministic: {block.get('block_id')}")
    safety = artifact.get("safety_policy", {})
    for key in ["read_only", "offline_sample_only", "explainability_artifact_only", "not_production_decision_engine", "no_direct_rating_action_confidence_change"]:
        if safety.get(key) is not True:
            errors.append(f"safety flag must be true: {key}")
    for key in SAFETY_FALSE_FLAGS:
        if safety.get(key) is not False:
            errors.append(f"safety flag must be false: {key}")
    rebuilt = build_unified_explainability_artifact(input_payload["prediction_context"])
    if rebuilt != artifact:
        errors.append("artifact template does not match deterministic builder output")


def validate_docs(errors: list[str]) -> None:
    doc = (ROOT / "docs/ai_dev_137_unified_explainability_evidence_trace_foundation_v1.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/runbooks/unified_explainability_evidence_trace_runbook.md").read_text(encoding="utf-8")
    phrases = [
        "V10 Unified Decision Intelligence",
        "reads AI-DEV-136 Prediction Context",
        "not a production decision engine",
        "does not modify rating/action/confidence",
        "does not trigger report delivery",
        "does not modify Dashboard UI",
        "AI-DEV-138",
        "AI-DEV-139",
        "AI-DEV-140",
        "source credibility",
        "metadata-only",
        "official-source replacement policy",
        "No external API calls",
        "No secrets",
        "No broker / order / trading",
    ]
    for phrase in phrases:
        if phrase not in doc:
            errors.append(f"doc missing required phrase: {phrase}")
    for phrase in ["offline", "build_unified_explainability_artifact.py", "validate_unified_explainability_v1.py", "no production pipeline"]:
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
    input_payload = read_json("templates/unified_explainability_input.example.json")
    artifact = read_json("templates/unified_explainability_artifact.example.json")
    validate_artifact(input_payload, artifact, errors)
    validate_docs(errors)
    proc = subprocess.run([str(ROOT / "venv/bin/python"), "scripts/orchestrator/build_unified_explainability_artifact.py", "--pretty"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
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
            "source_explanation_categories": len(artifact.get("source_explanations", {})),
            "evidence_link_count": len(artifact.get("evidence_links", [])),
            "trace_node_count": len(artifact.get("evidence_trace_graph", {}).get("nodes", [])),
            "trace_edge_count": len(artifact.get("evidence_trace_graph", {}).get("edges", [])),
            "exclusion_count": len(artifact.get("exclusion_reasons", {})),
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
