#!/usr/bin/env python3
"""Validate AI-DEV-143 four-window dashboard preview review package."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard_review.four_window_preview_review import (
    MUTATION_POLICY_REQUIREMENTS,
    REQUIRED_COMMON_SECTIONS,
    SCHEMA_VERSION,
    SOURCE_POLICY_REQUIREMENTS,
    TASK_ID,
    build_review_artifact,
)

DEFAULT_ARTIFACT = ROOT / "templates/four_window_dashboard_preview_review_artifact.example.json"
REQUIRED_FILES = [
    "app/dashboard_review/__init__.py",
    "app/dashboard_review/four_window_preview_review.py",
    "scripts/orchestrator/build_four_window_dashboard_preview_review.py",
    "scripts/orchestrator/validate_four_window_dashboard_preview_review_v1.py",
    "templates/four_window_dashboard_preview_review_input.example.json",
    "templates/four_window_dashboard_preview_review_artifact.example.json",
    "docs/ai_dev_143_four_window_dashboard_preview_review_production_integration_plan_v1.md",
    "docs/runbooks/four_window_dashboard_preview_review_runbook.md",
]
REQUIRED_WINDOWS = {
    "pre_open_0700": "盤前預測",
    "intraday_1305": "盤中追蹤",
    "pre_close_1335": "收盤快照",
    "post_close_1500": "盤後檢討",
}
SAFETY_FALSE = [
    "external_api_called",
    "secrets_read",
    "db_write",
    "scheduler_modified",
    "external_notification_sent",
    "line_email_notification_sent",
    "production_pipeline_executed",
    "python_main_executed",
    "trading_or_order_executed",
    "production_publish_executed",
    "dashboard_published",
    "formal_delivery_behavior_changed",
    "direct_rating_action_confidence_impact",
]
SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I),
    re.compile(r"BEGIN (RSA|OPENSSH) PRIVATE KEY", re.I),
    re.compile(r"api[_-]?key\s*[:=]", re.I),
    re.compile(r"access[_-]?token\s*[:=]", re.I),
    re.compile(r"password\s*[:=]", re.I),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def secret_scan(errors: list[str]) -> int:
    hits = 0
    for rel in REQUIRED_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits += 1
                errors.append(f"secret-like pattern in {rel}: {pattern.pattern}")
    return hits


def validate_artifact(artifact: dict[str, Any], errors: list[str]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if artifact.get("task_id") != TASK_ID:
        errors.append("task_id mismatch")
    for key in [
        "generated_at",
        "preview_artifact_ref",
        "preview_html_ref",
        "windows_review",
        "timing_alignment_review",
        "readability_review",
        "mobile_readability_review",
        "decision_intelligence_coverage_review",
        "source_policy_visibility_review",
        "warning_badge_review",
        "mutation_policy_visibility_review",
        "production_integration_plan",
        "blockers",
        "recommended_next_actions",
        "safety_policy",
    ]:
        if key not in artifact:
            errors.append(f"missing required field: {key}")
    windows = artifact.get("windows_review", [])
    if not isinstance(windows, list) or len(windows) != 4:
        errors.append("windows_review must contain four windows")
    by_key = {window.get("window_key"): window for window in windows if isinstance(window, dict)}
    for key, zh in REQUIRED_WINDOWS.items():
        if key not in by_key:
            errors.append(f"missing window review: {key}")
            continue
        row = by_key[key]
        if row.get("ui_display_name_zh") != zh:
            errors.append(f"{key} zh label mismatch")
        if row.get("review_status") != "passed":
            errors.append(f"{key} review_status must be passed")
        if row.get("visible_in_preview_html") is not True:
            errors.append(f"{key} must be visible in preview html")
    close = by_key.get("pre_close_1335", {})
    if close.get("ui_window_id") != "close_snapshot_1335":
        errors.append("13:35 UI id must remain close_snapshot_1335")
    timing = artifact.get("timing_alignment_review", {})
    for key in [
        "pre_open_0700_is_pre_open_forecast",
        "intraday_1305_is_intraday_tracking",
        "close_1335_runtime_key_compatible",
        "close_1335_ui_label_corrected",
        "close_1335_avoids_pre_close_main_semantics",
        "close_1335_full_review_deferred_to_1500",
        "post_close_1500_is_prediction_review",
    ]:
        if timing.get(key) is not True:
            errors.append(f"timing_alignment_review.{key} must be true")
    if timing.get("status") != "passed":
        errors.append("timing_alignment_review.status must be passed")
    readability = artifact.get("readability_review", {})
    for key in [
        "cards_first_layout",
        "short_clear_headings",
        "warnings_badges_readable",
        "official_source_policy_understandable",
        "recommendation_mutation_policy_clear",
        "four_windows_visually_distinguishable",
    ]:
        if readability.get(key) is not True:
            errors.append(f"readability_review.{key} must be true")
    if readability.get("raw_json_blob_in_main_view") is not False:
        errors.append("readability_review.raw_json_blob_in_main_view must be false")
    mobile = artifact.get("mobile_readability_review", {})
    for key in ["card_count_reasonable", "section_order_mobile_friendly", "long_paragraphs_avoided", "details_debug_layering_available", "technical_logs_absent_from_main_view"]:
        if mobile.get(key) is not True:
            errors.append(f"mobile_readability_review.{key} must be true")
    coverage = artifact.get("decision_intelligence_coverage_review", {})
    if coverage.get("all_required_sections_visible") is not True:
        errors.append("decision intelligence coverage must be complete")
    for section in REQUIRED_COMMON_SECTIONS:
        if section not in coverage.get("covered_sections", []):
            errors.append(f"missing covered section: {section}")
    source = artifact.get("source_policy_visibility_review", {})
    for req in SOURCE_POLICY_REQUIREMENTS:
        if req not in source.get("requirements", []):
            errors.append(f"missing source policy requirement: {req}")
    for key in ["core_evidence_family_visible", "contextual_evidence_family_visible", "external_replacement_warnings_visible", "metadata_only_policy_visible", "ai_generated_analysis_not_original_evidence_visible"]:
        if source.get(key) is not True:
            errors.append(f"source_policy_visibility_review.{key} must be true")
    mutation = artifact.get("mutation_policy_visibility_review", {})
    if mutation.get("all_flags_correct") is not True:
        errors.append("mutation policy flags must be correct")
    displayed = mutation.get("displayed_policy", {})
    for key, expected in MUTATION_POLICY_REQUIREMENTS.items():
        if displayed.get(key) is not expected:
            errors.append(f"displayed mutation policy {key} must be {expected}")
    plan = artifact.get("production_integration_plan", {})
    if plan.get("production_publish_executed") is not False:
        errors.append("production_integration_plan.production_publish_executed must be false")
    for key in ["static_preview_to_controlled_route_path", "suggested_dashboard_route", "renderer_integration_points", "validation_gates", "rollback_plan", "recommended_ai_dev_144_scope"]:
        if key not in plan:
            errors.append(f"production_integration_plan missing {key}")
    if plan.get("no_notification_rule") is not True or plan.get("no_scheduler_change_rule") is not True or plan.get("human_review_gate") is not True:
        errors.append("production integration plan must preserve no-notification, no-scheduler, human-review gates")
    safety = artifact.get("safety_policy", {})
    if safety.get("read_only_review") is not True:
        errors.append("safety_policy.read_only_review must be true")
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety_policy.{key} must be false")
    if artifact.get("blockers") != []:
        errors.append("blockers must be empty for this deterministic review")
    if artifact != build_review_artifact(repo_root=ROOT):
        errors.append("artifact does not match deterministic rebuild")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")
    artifact = load_json(args.artifact) if args.artifact.exists() else {}
    if artifact:
        validate_artifact(artifact, errors)
    secret_hits = secret_scan(errors) if not any(e.startswith("missing required file") for e in errors) else 0
    result = {
        "ok": not errors,
        "task_id": TASK_ID,
        "errors": errors,
        "summary": {
            "window_review_count": len(artifact.get("windows_review", [])) if artifact else 0,
            "readability_status": artifact.get("readability_review", {}).get("status") if artifact else None,
            "mobile_readability_status": artifact.get("mobile_readability_review", {}).get("status") if artifact else None,
            "production_publish_executed": artifact.get("production_integration_plan", {}).get("production_publish_executed") if artifact else None,
            "dashboard_published": artifact.get("safety_policy", {}).get("dashboard_published") if artifact else None,
            "external_notification_sent": artifact.get("safety_policy", {}).get("external_notification_sent") if artifact else None,
            "secret_pattern_hits": secret_hits,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
