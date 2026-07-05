#!/usr/bin/env python3
"""Validate AI-DEV-144 controlled four-window dashboard route integration."""
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

from app.dashboard.four_window_route_integration import ROUTE_PATH, SCHEMA_VERSION, TASK_ID, build_artifact

DEFAULT_ARTIFACT = ROOT / "templates/four_window_dashboard_route_integration.example.json"
DEFAULT_HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
REQUIRED_FILES = [
    "app/dashboard/four_window_route_integration.py",
    "scripts/orchestrator/build_four_window_dashboard_route_preview.py",
    "scripts/orchestrator/validate_four_window_dashboard_route_integration_v1.py",
    "templates/four_window_dashboard_route_integration_input.example.json",
    "templates/four_window_dashboard_route_integration.example.json",
    "templates/four_window_dashboard_route_preview.example.html",
    "docs/four_window_dashboard_route_integration_v1.md",
    "docs/runbooks/four_window_dashboard_route_integration_runbook.md",
]
REQUIRED_WINDOWS = {
    "pre_open_0700": ("pre_open_0700", "盤前預測", "Pre-open Forecast"),
    "intraday_1305": ("intraday_1305", "盤中追蹤", "Intraday Tracking"),
    "pre_close_1335": ("close_snapshot_1335", "收盤快照", "Close Snapshot"),
    "post_close_1500": ("prediction_review_1500", "盤後檢討", "Prediction Review"),
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
    "production_dashboard_publish_executed",
    "dashboard_published",
    "formal_delivery_behavior_changed",
    "direct_rating_action_confidence_impact",
    "production_rating_action_confidence_weight_mutated",
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


def validate_artifact(artifact: dict[str, Any], html: str, errors: list[str]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if artifact.get("task_id") != TASK_ID:
        errors.append("task_id mismatch")
    if artifact.get("route_path") != ROUTE_PATH:
        errors.append("route_path mismatch")
    if artifact.get("route_kind") != "controlled_static_dashboard_preview":
        errors.append("route_kind must be controlled_static_dashboard_preview")
    for key in ["source_preview_artifact", "source_preview_html", "route_preview_html", "four_window_mapping", "semantic_rules", "route_integration_status", "validation_gates", "rollback_instructions", "safety_policy"]:
        if key not in artifact:
            errors.append(f"missing required field: {key}")
    mapping = artifact.get("four_window_mapping", [])
    if not isinstance(mapping, list) or len(mapping) != 4:
        errors.append("four_window_mapping must contain four windows")
        return
    by_key = {row.get("window_key"): row for row in mapping if isinstance(row, dict)}
    for key, (ui_id, zh, en) in REQUIRED_WINDOWS.items():
        if key not in by_key:
            errors.append(f"missing window mapping: {key}")
            continue
        row = by_key[key]
        if row.get("ui_window_id") != ui_id:
            errors.append(f"{key} ui_window_id must be {ui_id}")
        if row.get("ui_display_name_zh") != zh:
            errors.append(f"{key} zh label must be {zh}")
        if row.get("ui_display_name_en") != en:
            errors.append(f"{key} en label must be {en}")
    if by_key.get("pre_close_1335", {}).get("full_prediction_review_assigned") is not False:
        errors.append("full prediction review must not be assigned to 13:35")
    if by_key.get("post_close_1500", {}).get("full_prediction_review_assigned") is not True:
        errors.append("full prediction review must be assigned to 15:00")
    rules = artifact.get("semantic_rules", {})
    expected_rules = {
        "pre_open_0700_is_pre_open_forecast": True,
        "intraday_1305_is_intraday_tracking": True,
        "pre_close_1335_runtime_key_compatible": True,
        "pre_close_1335_ui_id": "close_snapshot_1335",
        "pre_close_1335_ui_label_zh": "收盤快照",
        "pre_close_1335_ui_label_en": "Close Snapshot",
        "pre_close_1335_primary_ui_must_not_be_pre_close": True,
        "full_prediction_review_window_key": "post_close_1500",
        "full_prediction_review_ui_id": "prediction_review_1500",
    }
    for key, expected in expected_rules.items():
        if rules.get(key) != expected:
            errors.append(f"semantic_rules.{key} must be {expected}")
    status = artifact.get("route_integration_status", {})
    for key in ["production_dashboard_publish_executed", "dashboard_published", "external_notification_sent", "scheduler_modified", "production_pipeline_executed", "db_write"]:
        if status.get(key) is not False:
            errors.append(f"route_integration_status.{key} must be false")
    if status.get("static_controlled_route_artifact_created") is not True:
        errors.append("controlled route artifact must be created")
    safety = artifact.get("safety_policy", {})
    if safety.get("controlled_static_route") is not True or safety.get("repo_side_preview_only") is not True:
        errors.append("safety policy must mark controlled static repo-side preview")
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety_policy.{key} must be false")
    if not artifact.get("rollback_instructions"):
        errors.append("rollback_instructions must exist")
    for gate in ["validate_four_window_decision_intelligence_dashboard_ui_v1", "validate_four_window_dashboard_preview_review_v1", "validate_four_window_dashboard_route_integration_v1"]:
        if gate not in artifact.get("validation_gates", []):
            errors.append(f"missing validation gate: {gate}")
    if ROUTE_PATH not in html:
        errors.append("route html must include route path")
    if "close_snapshot_1335" not in html or "收盤快照" not in html or "Close Snapshot" not in html:
        errors.append("route html must include 13:35 close snapshot mapping")
    if "pre-close risk" in html.lower() or "收盤前風險" in html:
        errors.append("route html must not use pre-close risk primary semantics")
    if "production_dashboard_publish_executed=false" not in html:
        errors.append("route html must show production publish false")
    if artifact != build_artifact(repo_root=ROOT):
        errors.append("artifact does not match deterministic rebuild")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")
    artifact = load_json(args.artifact) if args.artifact.exists() else {}
    html = args.html.read_text(encoding="utf-8") if args.html.exists() else ""
    if artifact:
        validate_artifact(artifact, html, errors)
    secret_hits = secret_scan(errors) if not any(e.startswith("missing required file") for e in errors) else 0
    result = {
        "ok": not errors,
        "task_id": TASK_ID,
        "errors": errors,
        "summary": {
            "route_path": artifact.get("route_path") if artifact else None,
            "window_count": len(artifact.get("four_window_mapping", [])) if artifact else 0,
            "production_dashboard_publish_executed": artifact.get("route_integration_status", {}).get("production_dashboard_publish_executed") if artifact else None,
            "dashboard_published": artifact.get("route_integration_status", {}).get("dashboard_published") if artifact else None,
            "external_notification_sent": artifact.get("route_integration_status", {}).get("external_notification_sent") if artifact else None,
            "secret_pattern_hits": secret_hits,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
