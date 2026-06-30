#!/usr/bin/env python3
"""Validate Daily Report Intelligence Integration V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_NAME = "daily_report_intelligence_integration"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "daily_report_intelligence_integration_v1"
DECISIONS = {
    "daily_report_intelligence_integration_completed",
    "daily_report_intelligence_integration_completed_with_warnings",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "source_summary",
    "daily_report_intelligence_section",
    "company_intelligence_summary",
    "industry_peer_context_summary",
    "source_credibility_summary",
    "risk_and_limitations",
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
    "rendered_runtime_report",
]
SAFETY_TRUE = [
    "repo_only",
    "fixture_only",
    "advisory_only",
    "requires_human_review",
    "no_external_model_calls",
    "no_market_data_calls",
    "no_delivery_actions",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_schedule_service_changes",
]
SOURCE_SCORE_KEYS = [
    "contract_name",
    "contract_version",
    "source_id",
    "source_tier",
    "source_type",
    "publisher",
    "base_score",
    "adjustments",
    "credibility_score",
    "core_scoring_allowed",
    "conflicting_source",
    "requires_human_review",
    "usage_policy",
]
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
FORBIDDEN_RUNTIME_TERMS = ["broker", "shioaji", "production_db", "yfinance", "gemini", "dify", "webhook"]
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


def missing(data: Any, keys: list[str]) -> list[str]:
    if not isinstance(data, dict):
        return keys
    return [key for key in keys if key not in data]


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def is_score(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0


def validate_source_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("source_summary")
    if not isinstance(summary, dict):
        return ["source_summary must be an object"]
    for key in [
        "company_source_schema_version",
        "industry_peer_source_schema_version",
        "company_source_run_id",
        "industry_peer_source_run_id",
        "company_source_decision",
        "industry_peer_source_decision",
        "company_source_ok",
        "industry_peer_source_ok",
        "source_paths",
    ]:
        if key not in summary:
            errors.append(f"source_summary missing {key}")
    if summary.get("company_source_ok") is not True:
        errors.append("source_summary.company_source_ok must be true")
    if summary.get("industry_peer_source_ok") is not True:
        errors.append("source_summary.industry_peer_source_ok must be true")
    if not isinstance(summary.get("source_paths"), dict):
        errors.append("source_summary.source_paths must be an object")
    return errors


def validate_section(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    section = payload.get("daily_report_intelligence_section")
    if not isinstance(section, dict):
        return ["daily_report_intelligence_section must be an object"]
    for key in [
        "section_id",
        "section_type",
        "title",
        "placement",
        "priority",
        "render_mode",
        "markdown",
        "machine_readable",
        "badges",
        "source_refs",
        "advisory_only",
        "requires_human_review",
    ]:
        if key not in section:
            errors.append(f"daily_report_intelligence_section missing {key}")
    if section.get("section_type") != "daily_report_intelligence":
        errors.append("daily_report_intelligence_section.section_type must be daily_report_intelligence")
    if section.get("render_mode") != "static_markdown_with_machine_readable_payload":
        errors.append("daily_report_intelligence_section.render_mode is invalid")
    if not isinstance(section.get("markdown"), str) or not section.get("markdown", "").strip():
        errors.append("daily_report_intelligence_section.markdown must be a non-empty string")
    machine = section.get("machine_readable")
    if not isinstance(machine, dict):
        errors.append("daily_report_intelligence_section.machine_readable must be an object")
    else:
        for key in [
            "company_intelligence_summary",
            "industry_peer_context_summary",
            "source_credibility_summary",
            "risk_and_limitations",
            "advisory_only",
            "requires_human_review",
        ]:
            if key not in machine:
                errors.append(f"daily_report_intelligence_section.machine_readable missing {key}")
        if machine.get("advisory_only") is not True:
            errors.append("daily_report_intelligence_section.machine_readable.advisory_only must be true")
        if machine.get("requires_human_review") is not True:
            errors.append("daily_report_intelligence_section.machine_readable.requires_human_review must be true")
    badges = section.get("badges")
    if not isinstance(badges, dict):
        errors.append("daily_report_intelligence_section.badges must be an object")
    else:
        for key in ["repo_only", "fixture_only", "advisory_only", "requires_human_review"]:
            if badges.get(key) is not True:
                errors.append(f"daily_report_intelligence_section.badges.{key} must be true")
    if section.get("advisory_only") is not True:
        errors.append("daily_report_intelligence_section.advisory_only must be true")
    if section.get("requires_human_review") is not True:
        errors.append("daily_report_intelligence_section.requires_human_review must be true")
    if not isinstance(section.get("source_refs"), list) or not section.get("source_refs"):
        errors.append("daily_report_intelligence_section.source_refs must be a non-empty list")
    return errors


def validate_company_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("company_intelligence_summary")
    if not isinstance(summary, dict):
        return ["company_intelligence_summary must be an object"]
    for key in [
        "source_schema_version",
        "source_task_id",
        "source_run_id",
        "source_decision",
        "company",
        "topic_count",
        "average_source_credibility_score",
        "low_credibility_source_ids",
        "summary_points",
        "advisory_only",
        "requires_human_review",
    ]:
        if key not in summary:
            errors.append(f"company_intelligence_summary missing {key}")
    if summary.get("average_source_credibility_score") is not None and not is_score(summary.get("average_source_credibility_score")):
        errors.append("company_intelligence_summary.average_source_credibility_score must be 0.0-1.0 or null")
    if summary.get("advisory_only") is not True:
        errors.append("company_intelligence_summary.advisory_only must be true")
    if summary.get("requires_human_review") is not True:
        errors.append("company_intelligence_summary.requires_human_review must be true")
    return errors


def validate_industry_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("industry_peer_context_summary")
    if not isinstance(summary, dict):
        return ["industry_peer_context_summary must be an object"]
    for key in [
        "source_schema_version",
        "source_task_id",
        "source_run_id",
        "source_decision",
        "industry",
        "target_company",
        "industry_topic_count",
        "peer_context_count",
        "average_confidence",
        "highest_risk_flags",
        "summary_points",
        "advisory_only",
        "requires_human_review",
    ]:
        if key not in summary:
            errors.append(f"industry_peer_context_summary missing {key}")
    if summary.get("average_confidence") is not None and not is_score(summary.get("average_confidence")):
        errors.append("industry_peer_context_summary.average_confidence must be 0.0-1.0 or null")
    if summary.get("advisory_only") is not True:
        errors.append("industry_peer_context_summary.advisory_only must be true")
    if summary.get("requires_human_review") is not True:
        errors.append("industry_peer_context_summary.requires_human_review must be true")
    return errors


def validate_credibility_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("source_credibility_summary")
    if not isinstance(summary, dict):
        return ["source_credibility_summary must be an object"]
    for key in [
        "company_source_count",
        "industry_peer_source_count",
        "combined_source_count",
        "average_credibility_score",
        "low_credibility_source_ids",
        "review_required_source_ids",
        "core_scoring_allowed_source_ids",
        "metadata_preserved",
        "source_credibility_scores",
        "advisory_only",
        "requires_human_review",
    ]:
        if key not in summary:
            errors.append(f"source_credibility_summary missing {key}")
    if summary.get("metadata_preserved") is not True:
        errors.append("source_credibility_summary.metadata_preserved must be true")
    if summary.get("average_credibility_score") is not None and not is_score(summary.get("average_credibility_score")):
        errors.append("source_credibility_summary.average_credibility_score must be 0.0-1.0 or null")
    scores = summary.get("source_credibility_scores")
    if not isinstance(scores, list):
        errors.append("source_credibility_summary.source_credibility_scores must be a list")
        scores = []
    if summary.get("combined_source_count") != len(scores):
        errors.append("source_credibility_summary.combined_source_count must equal source_credibility_scores length")
    for index, item in enumerate(scores):
        if not isinstance(item, dict):
            errors.append(f"source_credibility_scores[{index}] must be an object")
            continue
        for key in SOURCE_SCORE_KEYS:
            if key not in item:
                errors.append(f"source_credibility_scores[{index}] missing {key}")
        if not is_score(item.get("credibility_score")):
            errors.append(f"source_credibility_scores[{index}].credibility_score must be 0.0-1.0")
    if summary.get("advisory_only") is not True:
        errors.append("source_credibility_summary.advisory_only must be true")
    if summary.get("requires_human_review") is not True:
        errors.append("source_credibility_summary.requires_human_review must be true")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    expected = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "company_schema_matched": True,
        "industry_peer_schema_matched": True,
        "markdown_included": True,
        "machine_readable_included": True,
        "source_credibility_metadata_preserved": True,
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
    errors: list[str] = []
    side_effects = payload.get("side_effects")
    if not isinstance(side_effects, dict):
        return ["side_effects must be an object"]
    for key in SIDE_EFFECTS_FALSE:
        if side_effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")
    return errors


def validate_safety(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        return ["safety must be an object"]
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("contract_name") != CONTRACT_NAME:
        errors.append(f"contract_name must be {CONTRACT_NAME}")
    if payload.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"contract_version must be {CONTRACT_VERSION}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true for completed decisions")
    errors.extend(validate_source_summary(payload))
    errors.extend(validate_section(payload))
    errors.extend(validate_company_summary(payload))
    errors.extend(validate_industry_summary(payload))
    errors.extend(validate_credibility_summary(payload))
    if not isinstance(payload.get("risk_and_limitations"), list) or not payload.get("risk_and_limitations"):
        errors.append("risk_and_limitations must be a non-empty list")
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
        for term in FORBIDDEN_RUNTIME_TERMS:
            if term in lowered:
                errors.append(f"forbidden live runtime source detected: {term}")
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
    credibility = payload.get("source_credibility_summary") if isinstance(payload.get("source_credibility_summary"), dict) else {}
    validation = payload.get("validation_summary") if isinstance(payload.get("validation_summary"), dict) else {}
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "combined_source_count": credibility.get("combined_source_count"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Daily Report Intelligence Integration V1 result JSON.")
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
