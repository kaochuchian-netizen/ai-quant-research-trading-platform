#!/usr/bin/env python3
"""Validate Company Intelligence + Source Credibility V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_NAME = "company_intelligence_source_credibility"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "company_intelligence_source_credibility_v1"
DECISIONS = {"company_intelligence_completed", "insufficient_fixture_data", "validation_failed", "blocked"}
TOP_LEVEL = [
    "contract_name",
    "contract_version",
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "company",
    "company_intelligence",
    "source_credibility_scores",
    "validation_summary",
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
    "modified_github_remote",
    "modified_forecast_runtime_weights",
]
SOURCE_TIERS = {
    "tier_1_official_filing",
    "tier_1_company_official",
    "tier_2_peer_and_industry_primary",
    "tier_2_management_interview",
    "tier_3_reputable_media",
    "tier_3_market_data",
    "tier_4_consensus_and_analyst",
    "tier_5_unverified_or_social",
}
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
FORBIDDEN_RUNTIME_TERMS = ["production_db", "shioaji", "gemini", "openai", "dify", "webhook"]
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


def validate_company(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    company = payload.get("company")
    if not isinstance(company, dict):
        return ["company must be an object"]
    for key in ["stock_id", "stock_name", "market", "industry"]:
        if not company.get(key):
            errors.append(f"company.{key} is required")
    return errors


def validate_source_scores(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scores = payload.get("source_credibility_scores")
    if not isinstance(scores, list):
        return ["source_credibility_scores must be a list"]
    if payload.get("decision") == "company_intelligence_completed" and not scores:
        errors.append("source_credibility_scores cannot be empty")
    seen: set[str] = set()
    for index, item in enumerate(scores):
        if not isinstance(item, dict):
            errors.append(f"source_credibility_scores[{index}] must be an object")
            continue
        for key in [
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
        ]:
            if key not in item:
                errors.append(f"source_credibility_scores[{index}] missing {key}")
        if item.get("contract_name") != CONTRACT_NAME:
            errors.append(f"source_credibility_scores[{index}].contract_name is invalid")
        if item.get("contract_version") != CONTRACT_VERSION:
            errors.append(f"source_credibility_scores[{index}].contract_version is invalid")
        if item.get("source_tier") not in SOURCE_TIERS:
            errors.append(f"source_credibility_scores[{index}].source_tier is invalid")
        if not is_score(item.get("base_score")):
            errors.append(f"source_credibility_scores[{index}].base_score must be 0.0-1.0")
        if not is_score(item.get("credibility_score")):
            errors.append(f"source_credibility_scores[{index}].credibility_score must be 0.0-1.0")
        if not isinstance(item.get("adjustments"), list):
            errors.append(f"source_credibility_scores[{index}].adjustments must be a list")
        if not isinstance(item.get("core_scoring_allowed"), bool):
            errors.append(f"source_credibility_scores[{index}].core_scoring_allowed must be boolean")
        if not isinstance(item.get("conflicting_source"), bool):
            errors.append(f"source_credibility_scores[{index}].conflicting_source must be boolean")
        if not isinstance(item.get("requires_human_review"), bool):
            errors.append(f"source_credibility_scores[{index}].requires_human_review must be boolean")
        source_id = str(item.get("source_id"))
        if source_id in seen:
            errors.append(f"duplicate source_id: {source_id}")
        seen.add(source_id)
    return errors


def validate_company_intelligence(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    intelligence = payload.get("company_intelligence")
    if not isinstance(intelligence, dict):
        return ["company_intelligence must be an object"]
    items = intelligence.get("items")
    if not isinstance(items, list):
        errors.append("company_intelligence.items must be a list")
        items = []
    if payload.get("decision") == "company_intelligence_completed" and not items:
        errors.append("company_intelligence.items cannot be empty")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"company_intelligence.items[{index}] must be an object")
            continue
        for key in [
            "topic_id",
            "topic",
            "summary",
            "evidence_source_ids",
            "source_credibility_score",
            "confidence",
            "data_quality",
            "advisory_only",
            "requires_human_review",
        ]:
            if key not in item:
                errors.append(f"company_intelligence.items[{index}] missing {key}")
        if item.get("source_credibility_score") is not None and not is_score(item.get("source_credibility_score")):
            errors.append(f"company_intelligence.items[{index}].source_credibility_score must be 0.0-1.0 or null")
        if item.get("confidence") is not None and not is_score(item.get("confidence")):
            errors.append(f"company_intelligence.items[{index}].confidence must be 0.0-1.0 or null")
        if not isinstance(item.get("evidence_source_ids"), list):
            errors.append(f"company_intelligence.items[{index}].evidence_source_ids must be a list")
        if item.get("advisory_only") is not True:
            errors.append(f"company_intelligence.items[{index}].advisory_only must be true")
        if not isinstance(item.get("requires_human_review"), bool):
            errors.append(f"company_intelligence.items[{index}].requires_human_review must be boolean")
    if intelligence.get("advisory_only") is not True:
        errors.append("company_intelligence.advisory_only must be true")
    if intelligence.get("requires_human_review") is not True:
        errors.append("company_intelligence.requires_human_review must be true")
    summary = intelligence.get("summary")
    if not isinstance(summary, dict):
        errors.append("company_intelligence.summary must be an object")
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
        "source_credibility_score_range": "0.0_to_1.0",
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    if not isinstance(summary.get("source_count"), int) or summary.get("source_count", -1) < 0:
        errors.append("validation_summary.source_count must be a non-negative integer")
    if not isinstance(summary.get("intelligence_topic_count"), int) or summary.get("intelligence_topic_count", -1) < 0:
        errors.append("validation_summary.intelligence_topic_count must be a non-negative integer")
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
    expected = {
        "fixture_only": True,
        "repo_only": True,
        "advisory_only": True,
        "research_only": True,
        "requires_human_review": True,
        "no_trading": True,
        "no_notification": True,
        "no_external_ai_runtime": True,
        "no_external_market_data": True,
        "no_production_db_write": True,
        "no_runtime_weight_change": True,
    }
    for key, value in expected.items():
        if safety.get(key) is not value:
            errors.append(f"safety.{key} must be {str(value).lower()}")
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
    if payload.get("ok") is not True and payload.get("decision") != "insufficient_fixture_data":
        errors.append("ok must be true for completed decisions")
    errors.extend(validate_company(payload))
    errors.extend(validate_company_intelligence(payload))
    errors.extend(validate_source_scores(payload))
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
                errors.append(f"forbidden runtime term detected: {term}")
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
    validation = payload.get("validation_summary") if isinstance(payload.get("validation_summary"), dict) else {}
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "source_count": validation.get("source_count"),
        "intelligence_topic_count": validation.get("intelligence_topic_count"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Company Intelligence + Source Credibility V1 result JSON.")
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
