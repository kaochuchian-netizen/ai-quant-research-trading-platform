#!/usr/bin/env python3
"""Validate Forecast Evidence Linking V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_NAME = "forecast_evidence_linking"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "forecast_evidence_linking_v1"
DECISIONS = {
    "forecast_evidence_linking_completed",
    "forecast_evidence_linking_completed_with_warnings",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "forecast_evidence_links",
    "evidence_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
LINK_FIELDS = [
    "forecast_id",
    "stock_id",
    "horizon",
    "source_ids",
    "company_intelligence_refs",
    "industry_intelligence_refs",
    "credibility_summary",
    "primary_evidence",
    "supporting_evidence",
    "sentiment_metadata",
    "human_review_required",
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


def validate_ref(name: str, item: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"{name} must be an object"]
    for key in ["ref_type", "ref_id", "topic", "summary", "matched_source_ids", "requires_human_review", "advisory_only"]:
        if key not in item:
            errors.append(f"{name} missing {key}")
    if not isinstance(item.get("matched_source_ids"), list) or not item.get("matched_source_ids"):
        errors.append(f"{name}.matched_source_ids must be a non-empty list")
    if item.get("advisory_only") is not True:
        errors.append(f"{name}.advisory_only must be true")
    if not isinstance(item.get("requires_human_review"), bool):
        errors.append(f"{name}.requires_human_review must be boolean")
    for score_key in ["source_credibility_score", "confidence"]:
        if score_key in item and item.get(score_key) is not None and not is_score(item.get(score_key)):
            errors.append(f"{name}.{score_key} must be 0.0-1.0 or null")
    return errors


def validate_evidence_item(name: str, item: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"{name} must be an object"]
    for key in ["ref_type", "ref_id", "topic", "matched_source_ids", "score", "summary"]:
        if key not in item:
            errors.append(f"{name} missing {key}")
    if not isinstance(item.get("matched_source_ids"), list) or not item.get("matched_source_ids"):
        errors.append(f"{name}.matched_source_ids must be a non-empty list")
    if item.get("score") is not None and not is_score(item.get("score")):
        errors.append(f"{name}.score must be 0.0-1.0 or null")
    return errors


def validate_credibility(name: str, value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{name} must be an object"]
    for key in [
        "source_count",
        "scored_source_count",
        "missing_source_ids",
        "average_credibility_score",
        "low_credibility_source_ids",
        "review_required_source_ids",
        "source_credibility_scores",
        "advisory_only",
    ]:
        if key not in value:
            errors.append(f"{name} missing {key}")
    for key in ["source_count", "scored_source_count"]:
        if not isinstance(value.get(key), int) or value.get(key, -1) < 0:
            errors.append(f"{name}.{key} must be a non-negative integer")
    if value.get("average_credibility_score") is not None and not is_score(value.get("average_credibility_score")):
        errors.append(f"{name}.average_credibility_score must be 0.0-1.0 or null")
    for key in ["missing_source_ids", "low_credibility_source_ids", "review_required_source_ids", "source_credibility_scores"]:
        if not isinstance(value.get(key), list):
            errors.append(f"{name}.{key} must be a list")
    if value.get("advisory_only") is not True:
        errors.append(f"{name}.advisory_only must be true")
    return errors


def validate_link(link: Any, index: int) -> list[str]:
    name = f"forecast_evidence_links[{index}]"
    errors: list[str] = []
    if not isinstance(link, dict):
        return [f"{name} must be an object"]
    for key in missing(link, LINK_FIELDS):
        errors.append(f"{name} missing {key}")
    for key in ["forecast_id", "stock_id", "horizon"]:
        if not str(link.get(key, "")).strip():
            errors.append(f"{name}.{key} is required")
    if not isinstance(link.get("source_ids"), list) or not link.get("source_ids"):
        errors.append(f"{name}.source_ids must be a non-empty list")
    for key in ["company_intelligence_refs", "industry_intelligence_refs", "primary_evidence", "supporting_evidence"]:
        if not isinstance(link.get(key), list):
            errors.append(f"{name}.{key} must be a list")
    for ref_index, ref in enumerate(as_list(link.get("company_intelligence_refs"))):
        errors.extend(validate_ref(f"{name}.company_intelligence_refs[{ref_index}]", ref))
    for ref_index, ref in enumerate(as_list(link.get("industry_intelligence_refs"))):
        errors.extend(validate_ref(f"{name}.industry_intelligence_refs[{ref_index}]", ref))
    for evidence_index, item in enumerate(as_list(link.get("primary_evidence"))):
        errors.extend(validate_evidence_item(f"{name}.primary_evidence[{evidence_index}]", item))
    for evidence_index, item in enumerate(as_list(link.get("supporting_evidence"))):
        errors.extend(validate_evidence_item(f"{name}.supporting_evidence[{evidence_index}]", item))
    errors.extend(validate_credibility(f"{name}.credibility_summary", link.get("credibility_summary")))
    sentiment = link.get("sentiment_metadata")
    if not isinstance(sentiment, dict):
        errors.append(f"{name}.sentiment_metadata must be an object")
    else:
        for key in ["sentiment_source_ids", "sentiment_source_count", "usage", "requires_human_review", "advisory_only"]:
            if key not in sentiment:
                errors.append(f"{name}.sentiment_metadata missing {key}")
        if not isinstance(sentiment.get("sentiment_source_ids"), list):
            errors.append(f"{name}.sentiment_metadata.sentiment_source_ids must be a list")
        elif sentiment.get("sentiment_source_count") != len(sentiment.get("sentiment_source_ids")):
            errors.append(f"{name}.sentiment_metadata.sentiment_source_count must match source id length")
        if sentiment.get("advisory_only") is not True:
            errors.append(f"{name}.sentiment_metadata.advisory_only must be true")
    if not isinstance(link.get("human_review_required"), bool):
        errors.append(f"{name}.human_review_required must be boolean")
    if link.get("advisory_only") is not True:
        errors.append(f"{name}.advisory_only must be true")
    return errors


def validate_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("evidence_summary")
    links = as_list(payload.get("forecast_evidence_links"))
    if not isinstance(summary, dict):
        return ["evidence_summary must be an object"]
    for key in [
        "schema_version",
        "forecast_count",
        "linked_forecast_count",
        "source_count",
        "company_intelligence_ref_count",
        "industry_intelligence_ref_count",
        "low_credibility_source_ids",
        "human_review_required_count",
        "advisory_only",
        "deterministic_output",
    ]:
        if key not in summary:
            errors.append(f"evidence_summary missing {key}")
    if summary.get("schema_version") != "forecast_evidence_summary_v1":
        errors.append("evidence_summary.schema_version is invalid")
    if summary.get("forecast_count") != len(links):
        errors.append("evidence_summary.forecast_count must equal forecast_evidence_links length")
    for key in [
        "linked_forecast_count",
        "source_count",
        "company_intelligence_ref_count",
        "industry_intelligence_ref_count",
        "human_review_required_count",
    ]:
        if not isinstance(summary.get(key), int) or summary.get(key, -1) < 0:
            errors.append(f"evidence_summary.{key} must be a non-negative integer")
    if not isinstance(summary.get("low_credibility_source_ids"), list):
        errors.append("evidence_summary.low_credibility_source_ids must be a list")
    if summary.get("advisory_only") is not True:
        errors.append("evidence_summary.advisory_only must be true")
    if summary.get("deterministic_output") is not True:
        errors.append("evidence_summary.deterministic_output must be true")
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
    if summary.get("forecast_count") != len(as_list(payload.get("forecast_evidence_links"))):
        errors.append("validation_summary.forecast_count must equal forecast_evidence_links length")
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
    links = payload.get("forecast_evidence_links")
    if not isinstance(links, list) or not links:
        errors.append("forecast_evidence_links must be a non-empty list")
        links = []
    seen: set[str] = set()
    for index, link in enumerate(links):
        errors.extend(validate_link(link, index))
        forecast_id = str(link.get("forecast_id")) if isinstance(link, dict) else ""
        if forecast_id in seen:
            errors.append(f"duplicate forecast_id: {forecast_id}")
        seen.add(forecast_id)
    errors.extend(validate_summary(payload))
    errors.extend(validate_validation_summary(payload))
    errors.extend(validate_side_effects(payload))
    errors.extend(validate_safety(payload))
    strings = iter_strings(payload)
    for text in strings:
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
        "decision": "forecast_evidence_linking_completed" if not errors else "validation_failed",
        "validated_schema_version": SCHEMA_VERSION,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Forecast Evidence Linking V1 fixture result.")
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
