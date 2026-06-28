#!/usr/bin/env python3
"""Validate dashboard-ready prediction review export results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "dashboard_prediction_review_report_export_v1"
DECISIONS = {
    "dashboard_report_export_completed",
    "dashboard_report_export_completed_with_insufficient_data",
    "no_review_records",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "input_summary",
    "dashboard_payload",
    "report_payload",
    "export_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
SIDE_EFFECTS_FALSE = [
    "read_secrets",
    "called_external_ai_runtime",
    "called_market_data_runtime",
    "sent_notification",
    "placed_trade_order",
    "modified_production_db",
    "modified_cron_systemd_timer",
    "modified_n8n",
    "mutated_github_issue",
    "deployed_dashboard",
    "modified_forecast_runtime_weights",
]
FORBIDDEN_SOURCE_TERMS = ["broker", "shioaji", "production_db", "yfinance", "gemini", "openai", "dify"]
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


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except Exception as exc:
        return None, [f"failed to read JSON: {exc}"]


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


def validate_side_effects(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    side_effects = payload.get("side_effects")
    if not isinstance(side_effects, dict):
        return ["side_effects must be an object"]
    for key in SIDE_EFFECTS_FALSE:
        if side_effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")
    return errors


def validate_dashboard(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    dashboard = payload.get("dashboard_payload")
    if not isinstance(dashboard, dict):
        return ["dashboard_payload must be an object"]
    cards = dashboard.get("cards")
    if not isinstance(cards, list):
        errors.append("dashboard_payload.cards must be a list")
        cards = []
    if not cards and payload.get("decision") != "no_review_records":
        errors.append("dashboard cards cannot be empty unless decision=no_review_records")
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            errors.append(f"dashboard_payload.cards[{index}] must be an object")
            continue
        for key in ["card_id", "card_type", "title"]:
            if key not in card:
                errors.append(f"dashboard_payload.cards[{index}] missing {key}")
        if card.get("card_id") == "daily_improvement_card":
            if card.get("safe_to_apply_automatically_count") != 0:
                errors.append("daily_improvement_card.safe_to_apply_automatically_count must be 0")
            for rec in card.get("recommendations", []):
                if isinstance(rec, dict):
                    if rec.get("safe_to_apply_automatically") is not False:
                        errors.append("recommendation safe_to_apply_automatically must be false")
                    if rec.get("requires_human_review") is not True:
                        errors.append("recommendation requires_human_review must be true")
        if card.get("card_id") == "safety_status_card":
            for key in ["advisory_only", "no_trading", "no_notification", "no_production_db_write", "no_runtime_weight_change", "fixture_only"]:
                if card.get(key) is not True:
                    errors.append(f"safety_status_card.{key} must be true")
    return errors


def validate_report(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    report = payload.get("report_payload")
    if not isinstance(report, dict):
        return ["report_payload must be an object"]
    sections = report.get("sections")
    if not isinstance(sections, list):
        errors.append("report_payload.sections must be a list")
        sections = []
    if not sections and payload.get("decision") != "no_review_records":
        errors.append("report sections cannot be empty unless decision=no_review_records")
    for index, section in enumerate(sections):
        name = f"report_payload.sections[{index}]"
        if not isinstance(section, dict):
            errors.append(f"{name} must be an object")
            continue
        for key in ["section_id", "title", "priority", "markdown", "machine_readable", "source_refs", "advisory_only"]:
            if key not in section:
                errors.append(f"{name} missing {key}")
        if section.get("advisory_only") is not True:
            errors.append(f"{name}.advisory_only must be true")
    return errors


def validate_export_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("export_summary")
    if not isinstance(summary, dict):
        return ["export_summary must be an object"]
    for key in [
        "card_count",
        "supported_cards",
        "insufficient_data_cards",
        "advisory_only",
        "section_count",
        "supported_sections",
        "markdown_sections_count",
        "machine_readable_sections_count",
    ]:
        if key not in summary:
            errors.append(f"export_summary missing {key}")
    if summary.get("advisory_only") is not True:
        errors.append("export_summary.advisory_only must be true")
    return errors


def validate_safety(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        return ["safety must be an object"]
    checks = {
        "advisory_only": True,
        "no_notification": True,
        "no_trading": True,
        "no_production_db_write": True,
        "no_runtime_weight_change": True,
        "dashboard_deployed": False,
    }
    for key, expected in checks.items():
        if safety.get(key) is not expected:
            errors.append(f"safety.{key} must be {str(expected).lower()}")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    errors.extend(validate_side_effects(payload))
    errors.extend(validate_dashboard(payload))
    errors.extend(validate_report(payload))
    errors.extend(validate_export_summary(payload))
    errors.extend(validate_safety(payload))
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like or private config text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        lowered = text.lower()
        for term in FORBIDDEN_SOURCE_TERMS:
            if term in lowered:
                errors.append(f"forbidden live runtime source detected: {term}")
    summary = payload.get("export_summary") if isinstance(payload.get("export_summary"), dict) else {}
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "card_count": summary.get("card_count"),
        "section_count": summary.get("section_count"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate dashboard prediction review export result JSON.")
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
