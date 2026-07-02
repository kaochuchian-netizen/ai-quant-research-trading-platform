#!/usr/bin/env python3
"""Validate the AI-DEV-125 factor recommendation package."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.recommendation.recommendation_builder import build_artifact, offline_sample_input
from app.recommendation.schemas import EFFECTIVENESS_FINDINGS, HORIZONS, PREDICTION_TARGETS, RECOMMENDATION_DIRECTIONS, SOURCE_PRIORITIES

REQUIRED_FILES = [
    "docs/ai_dev_125_factor_effectiveness_adaptive_recommendation_v1.md",
    "templates/factor_recommendation_input.example.json",
    "templates/factor_recommendation_artifact.example.json",
    "scripts/orchestrator/build_factor_recommendation_artifact.py",
    "scripts/orchestrator/validate_factor_recommendation_v1.py",
]
SECRET_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in [r"ghp_[A-Za-z0-9]+", r"github_pat_[A-Za-z0-9_]+", r"sk-[A-Za-z0-9]+", r"BEGIN (RSA|OPENSSH) PRIVATE KEY", r"api[_-]?key\s*[:=]", r"access[_-]?token\s*[:=]", r"password\s*[:=]"]]


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _contains_secret(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]


def validate() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for rel in REQUIRED_FILES:
        if not (REPO_ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}

    input_template = _read_json(REPO_ROOT / "templates/factor_recommendation_input.example.json")
    artifact_template = _read_json(REPO_ROOT / "templates/factor_recommendation_artifact.example.json")
    rebuilt = build_artifact(input_template)

    for rel in REQUIRED_FILES:
        hits = _contains_secret(REPO_ROOT / rel)
        if hits:
            errors.append(f"secret-like pattern in {rel}: {hits}")

    samples = input_template.get("samples", [])
    if len(samples) < 80:
        errors.append("input template must include enough offline samples for mixed effectiveness cases")
    if {row.get("source_priority") for row in samples} != set(SOURCE_PRIORITIES):
        errors.append("input template must cover all source priorities")

    artifact = artifact_template
    required_top = {"factor_effectiveness", "source_effectiveness", "horizon_effectiveness", "target_effectiveness", "contribution_analysis", "adaptive_recommendations", "safety_summary", "future_integration"}
    missing_top = sorted(required_top - set(artifact))
    if missing_top:
        errors.append(f"artifact missing top-level keys: {missing_top}")

    findings = {row.get("finding") for row in artifact.get("factor_effectiveness", [])}
    for finding in EFFECTIVENESS_FINDINGS:
        if finding not in findings:
            errors.append(f"missing effectiveness finding case: {finding}")
    source_priorities = {row.get("source_priority") for row in artifact.get("source_effectiveness", [])}
    if source_priorities != set(SOURCE_PRIORITIES):
        errors.append(f"source priorities mismatch: {sorted(source_priorities)}")
    horizons = {row.get("horizon") for row in artifact.get("horizon_effectiveness", [])}
    if not set(HORIZONS).issubset(horizons):
        errors.append("horizon effectiveness must include 1D/5D/20D")
    targets = {row.get("prediction_target") for row in artifact.get("target_effectiveness", [])}
    if set(PREDICTION_TARGETS) != targets:
        errors.append(f"prediction target coverage mismatch: {sorted(targets)}")

    recommendations = artifact.get("adaptive_recommendations", [])
    if not recommendations:
        errors.append("adaptive recommendations are required")
    for rec in recommendations:
        if rec.get("direction") not in RECOMMENDATION_DIRECTIONS:
            errors.append(f"unknown recommendation direction: {rec.get('direction')}")
        if rec.get("production_mutation_allowed") is not False:
            errors.append("recommendations must not allow production mutation")
        if rec.get("human_review_required") is not True:
            errors.append("recommendations must require human review")
        if rec.get("evidence_count", 0) < 5 and rec.get("direction") in {"increase", "decrease"}:
            errors.append("increase/decrease recommendations require sufficient evidence count")

    d_sentiment_recs = [rec for rec in recommendations if "D_sentiment_or_noise" in rec.get("target_key", "")]
    if not d_sentiment_recs or any(rec.get("direction") == "increase" for rec in d_sentiment_recs):
        errors.append("sentiment/noise sources must not receive increase recommendations")

    safety = artifact.get("safety_summary", {})
    for key in ["read_only", "dry_run", "no_production_weight_change", "no_confidence_rule_change", "no_rating_or_action_change", "no_order_execution", "no_notification", "no_external_service_call"]:
        if safety.get(key) is not True:
            errors.append(f"safety flag must be true: {key}")
    if safety.get("production_mutation_allowed") is not False:
        errors.append("artifact must disallow production mutation")

    if rebuilt.get("input_summary", {}).get("sample_size") != artifact.get("input_summary", {}).get("sample_size"):
        warnings.append("rebuilt artifact timestamp differs as expected, but sample counts should match")

    doc = (REPO_ROOT / "docs/ai_dev_125_factor_effectiveness_adaptive_recommendation_v1.md").read_text(encoding="utf-8")
    for phrase in ["read-only", "no production forecast weight", "no confidence", "no rating", "no order execution", "human review", "AI-DEV-126"]:
        if phrase.lower() not in doc.lower():
            errors.append(f"doc missing required safety/follow-up phrase: {phrase}")

    return {
        "ok": not errors,
        "task_id": "AI-DEV-125",
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "sample_size": len(samples),
            "factor_groups": sorted({row.get("factor_group") for row in samples}),
            "findings": sorted(findings),
            "recommendation_count": len(recommendations),
            "secret_pattern_hits": 0 if not errors else "see_errors",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
