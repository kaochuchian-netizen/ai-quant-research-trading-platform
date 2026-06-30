#!/usr/bin/env python3
"""Validate Forecast Explainability Layer V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_NAME = "forecast_explainability_layer"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "forecast_explainability_layer_v1"
SUMMARY_SCHEMA_VERSION = "forecast_explainability_summary_v1"
DECISIONS = {
    "forecast_explainability_layer_completed",
    "forecast_explainability_layer_completed_with_warnings",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "forecast_explanations",
    "explainability_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
EXPLANATION_FIELDS = [
    "explanation_id",
    "forecast_id",
    "stock_id",
    "horizon",
    "explanation_summary",
    "primary_reasoning",
    "supporting_reasoning",
    "official_evidence_summary",
    "industry_context_summary",
    "sentiment_metadata_summary",
    "credibility_risk_summary",
    "human_review_summary",
    "advisory_disclaimer",
    "source_trace_refs",
    "advisory_only",
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
    "dashboard_deployed",
    "api_server_created",
]
SAFETY_TRUE = [
    "repo_only",
    "fixture_only",
    "advisory_only",
    "preview_only",
    "no_external_model_calls",
    "no_market_data_calls",
    "no_delivery_actions",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_schedule_service_changes",
]
SAFETY_FALSE = ["dashboard_deploy", "api_server_created", "trading_instruction"]
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


def validate_explanation(item: Any, index: int) -> list[str]:
    name = f"forecast_explanations[{index}]"
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"{name} must be an object"]
    for key in missing(item, EXPLANATION_FIELDS):
        errors.append(f"{name} missing {key}")
    for key in [
        "explanation_id",
        "forecast_id",
        "stock_id",
        "horizon",
        "explanation_summary",
        "primary_reasoning",
        "supporting_reasoning",
        "official_evidence_summary",
        "industry_context_summary",
        "sentiment_metadata_summary",
        "credibility_risk_summary",
        "human_review_summary",
        "advisory_disclaimer",
    ]:
        if not str(item.get(key, "")).strip():
            errors.append(f"{name}.{key} is required")
    if not isinstance(item.get("source_trace_refs"), list) or not item.get("source_trace_refs"):
        errors.append(f"{name}.source_trace_refs must be a non-empty list")
    if item.get("advisory_only") is not True:
        errors.append(f"{name}.advisory_only must be true")
    for key in [
        "primary_reason_count",
        "supporting_reason_count",
        "official_evidence_count",
        "industry_context_count",
        "sentiment_metadata_count",
        "credibility_risk_count",
    ]:
        if key in item and (not isinstance(item.get(key), int) or item.get(key, -1) < 0):
            errors.append(f"{name}.{key} must be a non-negative integer")
    if "requires_human_review" in item and not isinstance(item.get("requires_human_review"), bool):
        errors.append(f"{name}.requires_human_review must be boolean")
    return errors


def validate_summary(summary: Any, explanations: list[Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(summary, dict):
        return ["explainability_summary must be an object"]
    for key in [
        "schema_version",
        "explanation_count",
        "forecast_count",
        "stock_count",
        "human_review_required_count",
        "credibility_risk_forecast_count",
        "sentiment_metadata_forecast_count",
        "source_trace_ref_count",
        "source_graph_id",
        "advisory_only",
        "deterministic_output",
    ]:
        if key not in summary:
            errors.append(f"explainability_summary missing {key}")
    if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append("explainability_summary.schema_version is invalid")
    if summary.get("explanation_count") != len(explanations):
        errors.append("explainability_summary.explanation_count must match forecast_explanations")
    if summary.get("advisory_only") is not True:
        errors.append("explainability_summary.advisory_only must be true")
    if summary.get("deterministic_output") is not True:
        errors.append("explainability_summary.deterministic_output must be true")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    expected = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    explainability = as_dict(payload.get("explainability_summary"))
    for key in ["explanation_count", "human_review_required_count"]:
        if summary.get(key) != explainability.get(key):
            errors.append(f"validation_summary.{key} must match explainability_summary")
    if not isinstance(summary.get("warning_count"), int) or summary.get("warning_count", -1) < 0:
        errors.append("validation_summary.warning_count must be a non-negative integer")
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
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True:
        errors.append("ok must be true")
    explanations = as_list(payload.get("forecast_explanations"))
    if not explanations:
        errors.append("forecast_explanations must be non-empty")
    seen: set[str] = set()
    for index, item in enumerate(explanations):
        errors.extend(validate_explanation(item, index))
        if isinstance(item, dict):
            explanation_id = str(item.get("explanation_id", ""))
            if explanation_id in seen:
                errors.append(f"duplicate explanation_id: {explanation_id}")
            seen.add(explanation_id)
    errors.extend(validate_summary(payload.get("explainability_summary"), explanations))
    errors.extend(validate_validation_summary(payload))
    errors.extend(validate_side_effects(payload))
    errors.extend(validate_safety(payload))
    for text in iter_strings(payload):
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append("payload contains secret-like text")
                break
        lowered = text.lower()
        for term in FORBIDDEN_RUNTIME_TERMS:
            if term in lowered:
                errors.append(f"payload contains forbidden runtime term: {term}")
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append("payload contains forbidden trading/order instruction text")
    return {
        "ok": not errors,
        "errors": errors,
        "decision": "forecast_explainability_layer_completed" if not errors else "validation_failed",
        "validated_schema_version": SCHEMA_VERSION,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Forecast Explainability Layer V1 fixture result.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload, load_errors = load_json(Path(args.input))
    result = {"ok": False, "errors": load_errors, "decision": "validation_failed"} if load_errors else validate_payload(payload)
    rendered = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write(rendered)
    sys.stdout.write("\n")
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
