#!/usr/bin/env python3
"""Validate AI-DEV-142 four-window Decision Intelligence dashboard UI preview."""
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

from app.dashboard.four_window_decision_intelligence import SCHEMA_VERSION, TASK_ID, build_artifact

DEFAULT_ARTIFACT = ROOT / "templates/four_window_decision_intelligence_dashboard_artifact.example.json"
DEFAULT_HTML = ROOT / "templates/four_window_decision_intelligence_dashboard_preview.example.html"
REQUIRED_FILES = [
    "app/dashboard/four_window_decision_intelligence.py",
    "scripts/orchestrator/build_four_window_decision_intelligence_dashboard_preview.py",
    "scripts/orchestrator/validate_four_window_decision_intelligence_dashboard_ui_v1.py",
    "templates/four_window_decision_intelligence_dashboard_input.example.json",
    "templates/four_window_decision_intelligence_dashboard_artifact.example.json",
    "templates/four_window_decision_intelligence_dashboard_preview.example.html",
    "docs/ai_dev_142_four_window_decision_intelligence_dashboard_ui_timing_alignment_v1.md",
    "docs/runbooks/four_window_decision_intelligence_dashboard_ui_runbook.md",
]
REQUIRED_WINDOWS = {
    "pre_open_0700": [
        "today_market_context",
        "same_day_high_low_forecast_context",
        "next_day_high_low_forecast_context",
        "one_month_trend_context",
        "three_month_trend_context",
        "market_regime",
        "official_source_admission_summary",
        "source_credibility_cards",
        "formal_integration_cards",
        "risk_scenario_invalidation_notes",
    ],
    "intraday_1305": [
        "current_price_vs_pre_open_range_placeholder",
        "near_same_day_high_low_status",
        "pre_open_scenario_validity",
        "volume_chip_adr_external_proxy_support",
        "intraday_status_card",
        "invalidation_warning",
    ],
    "pre_close_1335": [
        "actual_high_low_placeholder",
        "close_price_placeholder",
        "same_day_direction_preliminary_hit_status",
        "same_day_range_preliminary_hit_status",
        "abnormal_stock_factor_hint",
        "pre_open_forecast_preliminary_gap",
        "pending_full_review_badge",
    ],
    "post_close_1500": [
        "forecast_vs_actual",
        "high_low_range_hit",
        "direction_hit",
        "major_error_sources",
        "seven_day_rolling_evaluation",
        "factor_effectiveness",
        "confidence_calibration",
        "source_error_attribution",
        "decision_quality_feedback_recommendations",
    ],
}
REQUIRED_COMMON_SECTIONS = [
    "Executive Decision Intelligence Summary",
    "Official Source Admission Summary",
    "Source Credibility Cards",
    "Formal Integration Cards",
    "Evidence Trace Summary",
    "Factor Rationale Cards",
    "Warning / Exclusion Cards",
    "Metadata-only Badges",
    "Advisory-only Badges",
    "Feedback Recommendation Cards",
    "Mutation Policy Summary",
]
REQUIRED_SOURCE_BADGES = [
    "FinMind cannot replace official sources",
    "yfinance/Yahoo cannot replace official sources",
    "Google News RSS cannot be core forecast evidence",
    "broker target / analyst rating metadata-only",
    "Gemini / AI-generated analysis is not original evidence",
]
MUTATION_EXPECTED = {
    "recommendation_only": True,
    "human_review_required_for_any_mutation": True,
    "direct_rating_action_confidence_impact": False,
    "production_weight_changed": False,
    "production_confidence_changed": False,
    "production_rating_action_changed": False,
    "production_pipeline_modified": False,
    "delivery_behavior_modified": False,
}
SAFETY_FALSE = [
    "external_api_called",
    "secrets_read",
    "db_write",
    "scheduler_modified",
    "line_email_notification_sent",
    "production_pipeline_executed",
    "python_main_executed",
    "trading_or_order_executed",
    "dashboard_published",
    "production_dashboard_runtime_modified",
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


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(iter_strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(iter_strings(item))
        return out
    return []


def check_secret_patterns(errors: list[str]) -> int:
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
    windows = artifact.get("four_window_content_contract")
    if not isinstance(windows, list) or len(windows) != 4:
        errors.append("four_window_content_contract must contain 4 windows")
        return
    by_key = {window.get("window_key"): window for window in windows if isinstance(window, dict)}
    for key, sections in REQUIRED_WINDOWS.items():
        if key not in by_key:
            errors.append(f"missing window: {key}")
            continue
        window = by_key[key]
        for field in [
            "window_key",
            "ui_window_id",
            "ui_display_name_zh",
            "ui_display_name_en",
            "scheduled_time_tw",
            "market_phase",
            "primary_purpose",
            "allowed_sections",
            "disallowed_sections",
            "source_policy",
            "decision_intelligence_artifact_refs",
            "delivery_channel_policy",
            "timing_alignment_notes",
            "dashboard_cards",
        ]:
            if field not in window:
                errors.append(f"{key} missing {field}")
        allowed = window.get("allowed_sections", [])
        for section in sections:
            if section not in allowed:
                errors.append(f"{key} missing required section: {section}")
        if "external_notification_send" not in window.get("disallowed_sections", []):
            errors.append(f"{key} must disallow external notification send")
        if "production_mutation" not in window.get("disallowed_sections", []):
            errors.append(f"{key} must disallow production mutation")
    close = by_key.get("pre_close_1335", {})
    if close.get("ui_window_id") != "close_snapshot_1335":
        errors.append("13:35 ui_window_id must be close_snapshot_1335")
    if close.get("ui_display_name_zh") != "收盤快照":
        errors.append("13:35 zh label must be 收盤快照")
    if "Close Snapshot" not in str(close.get("ui_display_name_en")):
        errors.append("13:35 en label must include Close Snapshot")
    close_main_text = " ".join(
        str(close.get(key, ""))
        for key in ["ui_window_id", "ui_display_name_zh", "ui_display_name_en", "market_phase", "primary_purpose"]
    ).lower()
    if "pre-close" in close_main_text or "收盤前" in close_main_text:
        errors.append("13:35 UI main semantics must not be pre-close / 收盤前")
    common = artifact.get("common_decision_intelligence_sections", [])
    for section in REQUIRED_COMMON_SECTIONS:
        if section not in common:
            errors.append(f"missing common UI section: {section}")
    badges = artifact.get("source_policy", {}).get("policy_badges", [])
    for badge in REQUIRED_SOURCE_BADGES:
        if badge not in badges:
            errors.append(f"missing source policy badge: {badge}")
    mutation = artifact.get("mutation_policy", {})
    for key, expected in MUTATION_EXPECTED.items():
        if mutation.get(key) is not expected:
            errors.append(f"mutation_policy.{key} must be {expected}")
    safety = artifact.get("safety_policy", {})
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety_policy.{key} must be false")
    if safety.get("dashboard_preview_only") is not True:
        errors.append("safety_policy.dashboard_preview_only must be true")
    delivery = artifact.get("delivery_policy", {})
    for key in ["delivery_executed", "dashboard_published", "external_notification_sent"]:
        if delivery.get(key) is not False:
            errors.append(f"delivery_policy.{key} must be false")
    preview = artifact.get("preview_outputs", {})
    if preview.get("published_preview") is not False:
        errors.append("preview_outputs.published_preview must be false")
    if "收盤快照" not in html or "Close Snapshot" not in html:
        errors.append("HTML preview must show 13:35 close snapshot labels")
    if "pre-close risk reminder" in html.lower() or "收盤前風險提醒" in html:
        errors.append("HTML preview must not show pre-close risk reminder semantics")
    full_text = "\n".join(iter_strings(artifact)) + "\n" + html
    for phrase in ["send LINE", "send Email", "place order", "execute order", "production DB write"]:
        if phrase.lower() in full_text.lower():
            errors.append(f"forbidden live action text found: {phrase}")


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
        if artifact != build_artifact():
            errors.append("artifact does not match deterministic rebuild")
    secret_hits = check_secret_patterns(errors) if not any(e.startswith("missing required file") for e in errors) else 0
    result = {
        "ok": not errors,
        "task_id": TASK_ID,
        "errors": errors,
        "summary": {
            "window_count": len(artifact.get("four_window_content_contract", [])) if artifact else 0,
            "common_section_count": len(artifact.get("common_decision_intelligence_sections", [])) if artifact else 0,
            "close_snapshot_label_ok": "收盤快照" in html and "Close Snapshot" in html,
            "secret_pattern_hits": secret_hits,
            "dashboard_published": artifact.get("delivery_policy", {}).get("dashboard_published") if artifact else None,
            "external_notification_sent": artifact.get("delivery_policy", {}).get("external_notification_sent") if artifact else None,
            "production_pipeline_executed": artifact.get("safety_policy", {}).get("production_pipeline_executed") if artifact else None,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
