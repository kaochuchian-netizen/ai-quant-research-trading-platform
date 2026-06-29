#!/usr/bin/env python3
"""Build a deterministic Company Intelligence + Source Credibility V1 fixture."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/company_intelligence_input.example.json")
CONTRACT_NAME = "company_intelligence_source_credibility"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "company_intelligence_source_credibility_v1"
SIDE_EFFECTS = {
    "read_secrets": False,
    "called_external_ai_runtime": False,
    "called_market_data_runtime": False,
    "sent_notification": False,
    "placed_trade_order": False,
    "modified_production_db": False,
    "modified_cron_systemd_timer": False,
    "modified_n8n": False,
    "mutated_github_issue": False,
    "modified_github_remote": False,
    "modified_forecast_runtime_weights": False,
}

BASE_TIER_SCORES = {
    "tier_1_official_filing": 0.95,
    "tier_1_company_official": 0.90,
    "tier_2_peer_and_industry_primary": 0.80,
    "tier_2_management_interview": 0.70,
    "tier_3_reputable_media": 0.65,
    "tier_3_market_data": 0.60,
    "tier_4_consensus_and_analyst": 0.35,
    "tier_5_unverified_or_social": 0.10,
}
CORE_ALLOWED_TIERS = {
    "tier_1_official_filing",
    "tier_1_company_official",
    "tier_2_peer_and_industry_primary",
    "tier_2_management_interview",
    "tier_3_reputable_media",
    "tier_3_market_data",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("input JSON root must be an object")
    return data


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def credibility_score(source: dict[str, Any]) -> dict[str, Any]:
    tier = str(source.get("source_tier", "tier_5_unverified_or_social"))
    score = BASE_TIER_SCORES.get(tier, 0.10)
    adjustments: list[dict[str, Any]] = []
    if source.get("recency") == "current":
        score += 0.03
        adjustments.append({"factor": "current_source", "delta": 0.03})
    elif source.get("recency") == "stale":
        score -= 0.15
        adjustments.append({"factor": "stale_source", "delta": -0.15})
    if source.get("conflicting") is True:
        score -= 0.20
        adjustments.append({"factor": "conflicting_source", "delta": -0.20})
    if tier in {"tier_2_management_interview", "tier_3_reputable_media"} and not source.get("attribution"):
        score -= 0.10
        adjustments.append({"factor": "missing_attribution", "delta": -0.10})
    if tier == "tier_5_unverified_or_social":
        score -= 0.05
        adjustments.append({"factor": "unverified_source", "delta": -0.05})
    final_score = clamp(score)
    return {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "source_id": source.get("source_id"),
        "source_tier": tier,
        "source_type": source.get("source_type"),
        "publisher": source.get("publisher"),
        "published_at": source.get("published_at"),
        "retrieved_at": source.get("retrieved_at"),
        "base_score": BASE_TIER_SCORES.get(tier, 0.10),
        "adjustments": adjustments,
        "credibility_score": final_score,
        "core_scoring_allowed": tier in CORE_ALLOWED_TIERS and final_score >= 0.50,
        "conflicting_source": source.get("conflicting") is True,
        "requires_human_review": (
            tier in {"tier_4_consensus_and_analyst", "tier_5_unverified_or_social"}
            or source.get("conflicting") is True
            or final_score < 0.50
        ),
        "usage_policy": source.get("usage_policy", "context_with_source_label"),
        "notes": source.get("notes", ""),
    }


def weighted_average(scores: list[dict[str, Any]]) -> float | None:
    if not scores:
        return None
    values = [float(score.get("credibility_score", 0.0)) for score in scores]
    return round(sum(values) / len(values), 3)


def topic_intelligence(topic: dict[str, Any], scores_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source_ids = [str(item) for item in as_list(topic.get("source_ids"))]
    source_scores = [scores_by_id[source_id] for source_id in source_ids if source_id in scores_by_id]
    score = weighted_average(source_scores)
    requires_review = topic.get("requires_human_review") is True or any(
        item.get("requires_human_review") is True for item in source_scores
    )
    return {
        "topic_id": topic.get("topic_id"),
        "topic": topic.get("topic"),
        "summary": topic.get("summary"),
        "evidence_source_ids": source_ids,
        "source_credibility_score": score,
        "confidence": score,
        "data_quality": {
            "source_count": len(source_scores),
            "missing_sources": len(source_ids) - len(source_scores),
            "conflicting_sources": any(item.get("conflicting_source") is True for item in source_scores),
        },
        "advisory_only": True,
        "requires_human_review": requires_review,
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    sources = [item for item in as_list(data.get("sources")) if isinstance(item, dict)]
    source_scores = [credibility_score(source) for source in sources]
    scores_by_id = {str(score.get("source_id")): score for score in source_scores}
    topics = [item for item in as_list(data.get("intelligence_topics")) if isinstance(item, dict)]
    company = as_dict(data.get("company"))
    intelligence_items = [topic_intelligence(topic, scores_by_id) for topic in topics]
    source_score_values = [
        score.get("credibility_score")
        for score in source_scores
        if isinstance(score.get("credibility_score"), (int, float))
    ]
    average_score = round(sum(source_score_values) / len(source_score_values), 3) if source_score_values else None
    low_score_sources = [
        score.get("source_id")
        for score in source_scores
        if isinstance(score.get("credibility_score"), (int, float)) and score["credibility_score"] < 0.50
    ]
    decision = "company_intelligence_completed" if intelligence_items and source_scores else "insufficient_fixture_data"
    return {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-076"),
        "run_id": data.get("run_id", "company-intelligence-source-credibility-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "company": {
            "stock_id": company.get("stock_id"),
            "stock_name": company.get("stock_name"),
            "market": company.get("market"),
            "industry": company.get("industry"),
        },
        "company_intelligence": {
            "items": intelligence_items,
            "summary": {
                "topic_count": len(intelligence_items),
                "average_source_credibility_score": average_score,
                "low_credibility_source_ids": low_score_sources,
                "requires_human_review": bool(low_score_sources) or any(
                    item.get("requires_human_review") is True for item in intelligence_items
                ),
            },
            "advisory_only": True,
            "requires_human_review": True,
        },
        "source_credibility_scores": source_scores,
        "validation_summary": {
            "contract_name": CONTRACT_NAME,
            "contract_version": CONTRACT_VERSION,
            "source_count": len(source_scores),
            "intelligence_topic_count": len(intelligence_items),
            "deterministic_output": True,
            "fixture_only": True,
            "source_credibility_score_range": "0.0_to_1.0",
        },
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": {
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
        },
        "ok": bool(intelligence_items and source_scores),
        "decision": decision,
        "next_recommendation": "Review source coverage before connecting company intelligence to any runtime report.",
    }


def write_result(result: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(result, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if pretty:
        rendered += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Company Intelligence + Source Credibility V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_result(result, Path(args.output), args.pretty)
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
