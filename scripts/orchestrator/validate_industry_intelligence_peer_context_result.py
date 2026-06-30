#!/usr/bin/env python3
"""Validate Industry Intelligence + Peer Context V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_NAME = "industry_intelligence_peer_context"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "industry_intelligence_peer_context_v1"
DECISIONS = {"industry_peer_context_completed", "insufficient_fixture_data", "validation_failed", "blocked"}
TOP_LEVEL = [
    "contract_name",
    "contract_version",
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "industry",
    "target_company",
    "industry_intelligence",
    "peer_context",
    "industry_peer_context_summary",
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


def validate_industry(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    industry = payload.get("industry")
    if not isinstance(industry, dict):
        return ["industry must be an object"]
    for key in ["industry_id", "industry_name", "as_of_date"]:
        if not industry.get(key):
            errors.append(f"industry.{key} is required")
    return errors


def validate_target_company(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    company = payload.get("target_company")
    if not isinstance(company, dict):
        return ["target_company must be an object"]
    for key in ["stock_id", "stock_name", "market", "industry"]:
        if not company.get(key):
            errors.append(f"target_company.{key} is required")
    return errors


def validate_source_scores(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scores = payload.get("source_credibility_scores")
    if not isinstance(scores, list):
        return ["source_credibility_scores must be a list"]
    if payload.get("decision") == "industry_peer_context_completed" and not scores:
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


def validate_industry_intelligence(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    intelligence = payload.get("industry_intelligence")
    if not isinstance(intelligence, dict):
        return ["industry_intelligence must be an object"]
    items = intelligence.get("items")
    if not isinstance(items, list):
        errors.append("industry_intelligence.items must be a list")
        items = []
    if payload.get("decision") == "industry_peer_context_completed" and not items:
        errors.append("industry_intelligence.items cannot be empty")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"industry_intelligence.items[{index}] must be an object")
            continue
        for key in [
            "industry_intel_id",
            "industry_id",
            "industry_name",
            "as_of_date",
            "topic",
            "summary",
            "metrics",
            "affected_company_ids",
            "peer_references",
            "upstream_downstream_context",
            "evidence_source_ids",
            "source_tier",
            "confidence",
            "data_quality",
            "missing_data_policy",
            "risk_flags",
            "advisory_only",
            "requires_human_review",
        ]:
            if key not in item:
                errors.append(f"industry_intelligence.items[{index}] missing {key}")
        if item.get("confidence") is not None and not is_score(item.get("confidence")):
            errors.append(f"industry_intelligence.items[{index}].confidence must be 0.0-1.0 or null")
        if item.get("source_tier") is not None and item.get("source_tier") not in SOURCE_TIERS:
            errors.append(f"industry_intelligence.items[{index}].source_tier is invalid")
        if not isinstance(item.get("evidence_source_ids"), list):
            errors.append(f"industry_intelligence.items[{index}].evidence_source_ids must be a list")
        if not isinstance(item.get("data_quality"), dict):
            errors.append(f"industry_intelligence.items[{index}].data_quality must be an object")
        if item.get("advisory_only") is not True:
            errors.append(f"industry_intelligence.items[{index}].advisory_only must be true")
        if not isinstance(item.get("requires_human_review"), bool):
            errors.append(f"industry_intelligence.items[{index}].requires_human_review must be boolean")
    if intelligence.get("advisory_only") is not True:
        errors.append("industry_intelligence.advisory_only must be true")
    if intelligence.get("requires_human_review") is not True:
        errors.append("industry_intelligence.requires_human_review must be true")
    if not isinstance(intelligence.get("summary"), dict):
        errors.append("industry_intelligence.summary must be an object")
    return errors


def validate_peer_context(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    peer_context = payload.get("peer_context")
    if not isinstance(peer_context, dict):
        return ["peer_context must be an object"]
    if not isinstance(peer_context.get("peer_companies"), list):
        errors.append("peer_context.peer_companies must be a list")
    items = peer_context.get("items")
    if not isinstance(items, list):
        errors.append("peer_context.items must be a list")
        items = []
    if payload.get("decision") == "industry_peer_context_completed" and not items:
        errors.append("peer_context.items cannot be empty")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"peer_context.items[{index}] must be an object")
            continue
        for key in [
            "peer_context_id",
            "topic",
            "summary",
            "target_company_id",
            "peer_company_ids",
            "comparison_metrics",
            "relative_position",
            "evidence_source_ids",
            "source_credibility_score",
            "confidence",
            "data_quality",
            "advisory_only",
            "requires_human_review",
        ]:
            if key not in item:
                errors.append(f"peer_context.items[{index}] missing {key}")
        if item.get("source_credibility_score") is not None and not is_score(item.get("source_credibility_score")):
            errors.append(f"peer_context.items[{index}].source_credibility_score must be 0.0-1.0 or null")
        if item.get("confidence") is not None and not is_score(item.get("confidence")):
            errors.append(f"peer_context.items[{index}].confidence must be 0.0-1.0 or null")
        if not isinstance(item.get("peer_company_ids"), list):
            errors.append(f"peer_context.items[{index}].peer_company_ids must be a list")
        if not isinstance(item.get("evidence_source_ids"), list):
            errors.append(f"peer_context.items[{index}].evidence_source_ids must be a list")
        if not isinstance(item.get("comparison_metrics"), dict):
            errors.append(f"peer_context.items[{index}].comparison_metrics must be an object")
        if not isinstance(item.get("data_quality"), dict):
            errors.append(f"peer_context.items[{index}].data_quality must be an object")
        if item.get("advisory_only") is not True:
            errors.append(f"peer_context.items[{index}].advisory_only must be true")
        if not isinstance(item.get("requires_human_review"), bool):
            errors.append(f"peer_context.items[{index}].requires_human_review must be boolean")
    if peer_context.get("advisory_only") is not True:
        errors.append("peer_context.advisory_only must be true")
    if peer_context.get("requires_human_review") is not True:
        errors.append("peer_context.requires_human_review must be true")
    if not isinstance(peer_context.get("summary"), dict):
        errors.append("peer_context.summary must be an object")
    return errors


def validate_peer_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("industry_peer_context_summary")
    if not isinstance(summary, dict):
        return ["industry_peer_context_summary must be an object"]
    for key in [
        "contract_name",
        "contract_version",
        "industry_id",
        "target_company_id",
        "as_of_date",
        "industry_topic_count",
        "peer_context_count",
        "average_confidence",
        "highest_risk_flags",
        "requires_human_review",
        "advisory_only",
        "summary_points",
    ]:
        if key not in summary:
            errors.append(f"industry_peer_context_summary missing {key}")
    if summary.get("contract_name") != CONTRACT_NAME:
        errors.append("industry_peer_context_summary.contract_name is invalid")
    if summary.get("contract_version") != CONTRACT_VERSION:
        errors.append("industry_peer_context_summary.contract_version is invalid")
    if summary.get("average_confidence") is not None and not is_score(summary.get("average_confidence")):
        errors.append("industry_peer_context_summary.average_confidence must be 0.0-1.0 or null")
    if not isinstance(summary.get("highest_risk_flags"), list):
        errors.append("industry_peer_context_summary.highest_risk_flags must be a list")
    if summary.get("requires_human_review") is not True:
        errors.append("industry_peer_context_summary.requires_human_review must be true")
    if summary.get("advisory_only") is not True:
        errors.append("industry_peer_context_summary.advisory_only must be true")
    if not isinstance(summary.get("summary_points"), list):
        errors.append("industry_peer_context_summary.summary_points must be a list")
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
    for key in ["source_count", "industry_topic_count", "peer_context_count"]:
        if not isinstance(summary.get(key), int) or summary.get(key, -1) < 0:
            errors.append(f"validation_summary.{key} must be a non-negative integer")
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
    errors.extend(validate_industry(payload))
    errors.extend(validate_target_company(payload))
    errors.extend(validate_industry_intelligence(payload))
    errors.extend(validate_peer_context(payload))
    errors.extend(validate_peer_summary(payload))
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
        "industry_topic_count": validation.get("industry_topic_count"),
        "peer_context_count": validation.get("peer_context_count"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Industry Intelligence + Peer Context V1 result JSON.")
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
