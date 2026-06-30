#!/usr/bin/env python3
"""Build a deterministic Industry Intelligence + Peer Context V1 fixture."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/industry_intelligence_peer_context_input.example.json")
CONTRACT_NAME = "industry_intelligence_peer_context"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "industry_intelligence_peer_context_v1"
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


def source_score_values(source_ids: list[str], scores_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [scores_by_id[source_id] for source_id in source_ids if source_id in scores_by_id]


def average_score(scores: list[dict[str, Any]]) -> float | None:
    values = [float(score.get("credibility_score", 0.0)) for score in scores]
    return round(sum(values) / len(values), 3) if values else None


def capped_confidence(raw_score: float | None, cap: Any) -> float | None:
    if raw_score is None:
        return None
    if isinstance(cap, (int, float)) and not isinstance(cap, bool):
        return round(min(raw_score, float(cap)), 3)
    return raw_score


def highest_source_tier(scores: list[dict[str, Any]]) -> str | None:
    if not scores:
        return None
    order = {tier: index for index, tier in enumerate(BASE_TIER_SCORES)}
    return min((str(score.get("source_tier")) for score in scores), key=lambda tier: order.get(tier, 999))


def data_quality(source_ids: list[str], scores: list[dict[str, Any]], requires_review: bool) -> dict[str, Any]:
    return {
        "freshness": "current" if scores else "unknown",
        "completeness": round(len(scores) / len(source_ids), 3) if source_ids else 0.0,
        "source_count": len(scores),
        "missing_sources": len(source_ids) - len(scores),
        "conflicting_sources": any(score.get("conflicting_source") is True for score in scores),
        "conflict_notes": "",
        "requires_human_review": requires_review,
        "legacy_record": False,
    }


def industry_item(topic: dict[str, Any], industry: dict[str, Any], scores_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source_ids = [str(item) for item in as_list(topic.get("source_ids"))]
    scores = source_score_values(source_ids, scores_by_id)
    confidence = capped_confidence(average_score(scores), topic.get("confidence_cap"))
    requires_review = topic.get("requires_human_review") is True or any(
        score.get("requires_human_review") is True for score in scores
    )
    return {
        "industry_intel_id": topic.get("industry_intel_id"),
        "industry_id": industry.get("industry_id"),
        "industry_name": industry.get("industry_name"),
        "as_of_date": industry.get("as_of_date"),
        "topic": topic.get("topic"),
        "summary": topic.get("summary"),
        "metrics": as_dict(topic.get("metrics")),
        "affected_company_ids": [str(item) for item in as_list(topic.get("affected_company_ids"))],
        "peer_references": [str(item) for item in as_list(topic.get("peer_references"))],
        "upstream_downstream_context": as_dict(topic.get("upstream_downstream_context")),
        "evidence_source_ids": source_ids,
        "source_tier": highest_source_tier(scores),
        "confidence": confidence,
        "data_quality": data_quality(source_ids, scores, requires_review),
        "missing_data_policy": topic.get("missing_data_policy", "retain_as_context_with_missing_fields_labeled"),
        "risk_flags": [str(item) for item in as_list(topic.get("risk_flags"))],
        "advisory_only": True,
        "requires_human_review": requires_review,
    }


def peer_item(
    item: dict[str, Any],
    target_company: dict[str, Any],
    scores_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_ids = [str(source_id) for source_id in as_list(item.get("source_ids"))]
    scores = source_score_values(source_ids, scores_by_id)
    score = average_score(scores)
    confidence = capped_confidence(score, item.get("confidence_cap"))
    requires_review = item.get("requires_human_review") is True or any(
        source_score.get("requires_human_review") is True for source_score in scores
    )
    return {
        "peer_context_id": item.get("peer_context_id"),
        "topic": item.get("topic"),
        "summary": item.get("summary"),
        "target_company_id": target_company.get("stock_id"),
        "peer_company_ids": [str(peer_id) for peer_id in as_list(item.get("peer_company_ids"))],
        "comparison_metrics": as_dict(item.get("comparison_metrics")),
        "relative_position": item.get("relative_position"),
        "evidence_source_ids": source_ids,
        "source_credibility_score": score,
        "confidence": confidence,
        "data_quality": data_quality(source_ids, scores, requires_review),
        "advisory_only": True,
        "requires_human_review": requires_review,
    }


def build_summary(
    industry: dict[str, Any],
    target_company: dict[str, Any],
    industry_items: list[dict[str, Any]],
    peer_items: list[dict[str, Any]],
) -> dict[str, Any]:
    confidences = [
        float(item["confidence"])
        for item in [*industry_items, *peer_items]
        if isinstance(item.get("confidence"), (int, float))
    ]
    risk_flags = sorted({flag for item in industry_items for flag in as_list(item.get("risk_flags"))})
    summary_points = [
        item.get("summary")
        for item in [*industry_items, *peer_items]
        if isinstance(item.get("summary"), str) and item.get("summary")
    ][:4]
    return {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "industry_id": industry.get("industry_id"),
        "target_company_id": target_company.get("stock_id"),
        "as_of_date": industry.get("as_of_date"),
        "industry_topic_count": len(industry_items),
        "peer_context_count": len(peer_items),
        "average_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "highest_risk_flags": risk_flags,
        "requires_human_review": True,
        "advisory_only": True,
        "summary_points": summary_points,
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    industry = as_dict(data.get("industry"))
    target_company = as_dict(data.get("target_company"))
    sources = [item for item in as_list(data.get("sources")) if isinstance(item, dict)]
    source_scores = [credibility_score(source) for source in sources]
    scores_by_id = {str(score.get("source_id")): score for score in source_scores}
    industry_items = [
        industry_item(item, industry, scores_by_id)
        for item in as_list(data.get("industry_topics"))
        if isinstance(item, dict)
    ]
    peer_items = [
        peer_item(item, target_company, scores_by_id)
        for item in as_list(data.get("peer_context_items"))
        if isinstance(item, dict)
    ]
    summary = build_summary(industry, target_company, industry_items, peer_items)
    decision = "industry_peer_context_completed" if industry_items and peer_items and source_scores else "insufficient_fixture_data"
    return {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-077"),
        "run_id": data.get("run_id", "industry-intelligence-peer-context-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "industry": {
            "industry_id": industry.get("industry_id"),
            "industry_name": industry.get("industry_name"),
            "as_of_date": industry.get("as_of_date"),
        },
        "target_company": {
            "stock_id": target_company.get("stock_id"),
            "stock_name": target_company.get("stock_name"),
            "market": target_company.get("market"),
            "industry": target_company.get("industry"),
        },
        "industry_intelligence": {
            "items": industry_items,
            "summary": {
                "topic_count": len(industry_items),
                "risk_flags": summary["highest_risk_flags"],
                "requires_human_review": any(item.get("requires_human_review") is True for item in industry_items),
            },
            "advisory_only": True,
            "requires_human_review": True,
        },
        "peer_context": {
            "peer_companies": [item for item in as_list(data.get("peer_companies")) if isinstance(item, dict)],
            "items": peer_items,
            "summary": {
                "peer_company_count": len([item for item in as_list(data.get("peer_companies")) if isinstance(item, dict)]),
                "peer_context_count": len(peer_items),
                "requires_human_review": any(item.get("requires_human_review") is True for item in peer_items),
            },
            "advisory_only": True,
            "requires_human_review": True,
        },
        "industry_peer_context_summary": summary,
        "source_credibility_scores": source_scores,
        "validation_summary": {
            "contract_name": CONTRACT_NAME,
            "contract_version": CONTRACT_VERSION,
            "source_count": len(source_scores),
            "industry_topic_count": len(industry_items),
            "peer_context_count": len(peer_items),
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
        "ok": bool(industry_items and peer_items and source_scores),
        "decision": decision,
        "next_recommendation": "Review source coverage before connecting industry or peer context to any runtime report.",
    }


def write_json(payload: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if pretty:
        rendered += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Industry Intelligence + Peer Context V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    if args.summary_output:
        write_json(result["industry_peer_context_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
