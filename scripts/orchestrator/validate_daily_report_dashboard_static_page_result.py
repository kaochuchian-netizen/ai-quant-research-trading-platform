#!/usr/bin/env python3
"""Validate Daily Report Dashboard Static Page V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "daily_report_dashboard_static_page_v1"
SOURCE_SCHEMA_VERSION = "daily_report_dashboard_preview_feed_v1"
DECISIONS = {
    "daily_report_dashboard_static_page_completed",
    "daily_report_dashboard_static_page_completed_with_warnings",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "dashboard_page",
    "latest_preview_card",
    "preview_cards",
    "overview_metrics",
    "filter_facets",
    "sort_options",
    "warning_badges",
    "advisory_only_badges",
    "preview_only_badges",
    "requires_human_review_badges",
    "drilldown_placeholders",
    "source_dashboard_preview_feed_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
SIDE_EFFECTS_FALSE = [
    "read_secrets",
    "called_external_model_runtime",
    "called_market_data_runtime",
    "sent_notification",
    "placed_trade_order",
    "modified_portfolio",
    "wrote_persistent_store",
    "modified_schedule_or_service",
    "modified_github_remote",
    "sent_daily_report",
    "wrote_production_db",
    "deployed_dashboard",
    "created_api_server",
]
SAFETY_TRUE = [
    "repo_only",
    "fixture_only",
    "preview_only",
    "advisory_only",
    "requires_human_review",
    "no_external_model_calls",
    "no_market_data_calls",
    "no_delivery_actions",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_schedule_service_changes",
]
SAFETY_FALSE = ["dashboard_deploy", "api_server_created"]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\.env", re.IGNORECASE),
]
FORBIDDEN_LIVE_TERMS = ["shioaji", "production_db", "webhook", "broker"]
FORBIDDEN_TRADING_TEXT = [
    re.compile(r"\b(buy|sell|short|long)\s+(now|today|at market|at open|at close)\b", re.IGNORECASE),
    re.compile(r"\b(place|submit|route|execute)\s+(an?\s+)?order\b", re.IGNORECASE),
    re.compile(r"\border\s+(now|immediately|ticket|instruction)\b", re.IGNORECASE),
]


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except Exception as exc:
        return None, [f"failed to read JSON: {exc}"]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def missing(data: Any, keys: list[str]) -> list[str]:
    if not isinstance(data, dict):
        return keys
    return [key for key in keys if key not in data]


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(iter_strings(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(iter_strings(item))
        return result
    return []


def validate_dashboard_page(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    page = payload.get("dashboard_page")
    latest = as_dict(payload.get("latest_preview_card"))
    if not isinstance(page, dict):
        return ["dashboard_page must be an object"]
    for key in [
        "page_id",
        "page_title",
        "generated_at",
        "latest_preview_card_ref",
        "preview_cards_ref",
        "overview_metrics_ref",
        "filter_facets_ref",
        "sort_options_ref",
        "warning_badges_ref",
        "drilldown_placeholders_ref",
        "manifest_ref",
        "markdown_ref",
        "renderer_source_ref",
    ]:
        if key not in page:
            errors.append(f"dashboard_page missing {key}")
    for key in ["page_id", "page_title", "generated_at", "manifest_ref", "markdown_ref", "renderer_source_ref"]:
        if not isinstance(page.get(key), str) or not page.get(key):
            errors.append(f"dashboard_page.{key} must be a non-empty string")
    if page.get("latest_preview_card_ref") != latest.get("card_id"):
        errors.append("dashboard_page.latest_preview_card_ref must match latest_preview_card.card_id")
    expected_refs = {
        "preview_cards_ref": "embedded:preview_cards",
        "overview_metrics_ref": "embedded:overview_metrics",
        "filter_facets_ref": "embedded:filter_facets",
        "sort_options_ref": "embedded:sort_options",
        "warning_badges_ref": "embedded:warning_badges",
        "drilldown_placeholders_ref": "embedded:drilldown_placeholders",
    }
    for key, value in expected_refs.items():
        if page.get(key) != value:
            errors.append(f"dashboard_page.{key} is invalid")
    return errors


def validate_cards(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    latest = payload.get("latest_preview_card")
    cards = payload.get("preview_cards")
    if not isinstance(latest, dict):
        errors.append("latest_preview_card must be an object")
    if not isinstance(cards, list) or not cards:
        return errors + ["preview_cards must be a non-empty list"]
    if isinstance(latest, dict) and latest != cards[0]:
        errors.append("latest_preview_card must equal preview_cards[0]")
    for index, card in enumerate(cards):
        prefix = f"preview_cards[{index}]"
        if not isinstance(card, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in ["card_id", "preview_id", "card_title", "report_date", "status", "manifest_ref", "markdown_ref", "renderer_source_ref", "sort_key"]:
            if not isinstance(card.get(key), str) or not card.get(key):
                errors.append(f"{prefix}.{key} must be a non-empty string")
        if card.get("status") not in {"ready", "warning", "requires_human_review"}:
            errors.append(f"{prefix}.status is invalid")
        if not isinstance(card.get("warning_badges"), list):
            errors.append(f"{prefix}.warning_badges must be a list")
        for badge_key in ["advisory_only_badge", "preview_only_badge", "requires_human_review_badge"]:
            badge = card.get(badge_key)
            if not isinstance(badge, dict) or badge.get("enabled") is not True:
                errors.append(f"{prefix}.{badge_key} must be enabled")
    return errors


def validate_metrics(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metrics = payload.get("overview_metrics")
    cards = as_list(payload.get("preview_cards"))
    warnings = as_list(payload.get("warning_badges"))
    if not isinstance(metrics, dict):
        return ["overview_metrics must be an object"]
    expected = {
        "preview_card_count": len(cards),
        "warning_badge_count": len(warnings),
        "advisory_only_count": len(as_list(payload.get("advisory_only_badges"))),
        "preview_only_count": len(as_list(payload.get("preview_only_badges"))),
        "requires_human_review_count": len(as_list(payload.get("requires_human_review_badges"))),
    }
    for key, value in expected.items():
        if metrics.get(key) != value:
            errors.append(f"overview_metrics.{key} must be {value}")
    if not isinstance(metrics.get("status_counts"), dict):
        errors.append("overview_metrics.status_counts must be an object")
    return errors


def validate_collections(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload.get("filter_facets"), dict):
        errors.append("filter_facets must be an object")
    if not isinstance(payload.get("sort_options"), list) or not payload.get("sort_options"):
        errors.append("sort_options must be a non-empty list")
    for key in ["warning_badges", "advisory_only_badges", "preview_only_badges", "requires_human_review_badges"]:
        if not isinstance(payload.get(key), list):
            errors.append(f"{key} must be a list")
    placeholders = payload.get("drilldown_placeholders")
    cards = as_list(payload.get("preview_cards"))
    if not isinstance(placeholders, list) or len(placeholders) != len(cards):
        errors.append("drilldown_placeholders must match preview_cards length")
    else:
        for index, placeholder in enumerate(placeholders):
            if not isinstance(placeholder, dict):
                errors.append(f"drilldown_placeholders[{index}] must be an object")
                continue
            if placeholder.get("enabled") is not False or placeholder.get("status") != "placeholder_only":
                errors.append(f"drilldown_placeholders[{index}] must be disabled placeholder_only")
    return errors


def validate_source_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("source_dashboard_preview_feed_summary")
    if not isinstance(summary, dict):
        return ["source_dashboard_preview_feed_summary must be an object"]
    expected = {
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "source_ok": True,
        "source_mode": "fixture_dry_run",
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"source_dashboard_preview_feed_summary.{key} is invalid")
    for key in ["source_path", "source_feed_id", "source_run_id"]:
        if not isinstance(summary.get(key), str) or not summary.get(key):
            errors.append(f"source_dashboard_preview_feed_summary.{key} must be a non-empty string")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    cards = as_list(payload.get("preview_cards"))
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    expected = {
        "source_schema_expected": SOURCE_SCHEMA_VERSION,
        "source_schema_matched": True,
        "source_ok": True,
        "source_mode_fixture_dry_run": True,
        "dashboard_page_included": True,
        "latest_preview_card_included": True,
        "preview_cards_included": True,
        "preview_card_count": len(cards),
        "overview_metrics_included": True,
        "filter_facets_included": True,
        "sort_options_included": True,
        "warning_badges_included": True,
        "drilldown_placeholders_included": True,
        "manifest_ref_present": True,
        "markdown_ref_present": True,
        "renderer_source_ref_present": True,
        "deterministic_output": True,
        "fixture_only": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    if not isinstance(summary.get("warnings"), list):
        errors.append("validation_summary.warnings must be a list")
    return errors


def validate_side_effects(payload: dict[str, Any]) -> list[str]:
    side_effects = payload.get("side_effects")
    if not isinstance(side_effects, dict):
        return ["side_effects must be an object"]
    return [
        f"side_effects.{key} must be false"
        for key in SIDE_EFFECTS_FALSE
        if side_effects.get(key) is not False
    ]


def validate_safety(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        return ["safety must be an object"]
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety.{key} must be false")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != "AI-DEV-088":
        errors.append("task_id must be AI-DEV-088")
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true for completed decisions")
    errors.extend(validate_dashboard_page(payload))
    errors.extend(validate_cards(payload))
    errors.extend(validate_metrics(payload))
    errors.extend(validate_collections(payload))
    errors.extend(validate_source_summary(payload))
    errors.extend(validate_validation_summary(payload))
    errors.extend(validate_side_effects(payload))
    errors.extend(validate_safety(payload))
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like or private config text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        lowered = text.lower()
        for term in FORBIDDEN_LIVE_TERMS:
            if term in lowered:
                errors.append(f"forbidden live runtime source detected: {term}")
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
    validation = as_dict(payload.get("validation_summary"))
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "preview_card_count": validation.get("preview_card_count"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Daily Report Dashboard Static Page V1 result JSON.")
    parser.add_argument("path", nargs="?")
    parser.add_argument("--input", dest="input_path")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_path or args.path
    if not input_path:
        raise SystemExit("input path is required")
    payload, load_errors = load_json(Path(input_path))
    result = {"ok": False, "errors": load_errors} if payload is None else validate_payload(payload)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
