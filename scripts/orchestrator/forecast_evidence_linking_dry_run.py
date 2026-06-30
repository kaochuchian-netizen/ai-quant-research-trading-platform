#!/usr/bin/env python3
"""Build a deterministic Forecast Evidence Linking V1 fixture result."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/forecast_evidence_linking_input.example.json")
CONTRACT_NAME = "forecast_evidence_linking"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "forecast_evidence_linking_v1"
DECISION_COMPLETED = "forecast_evidence_linking_completed"
DECISION_WARNINGS = "forecast_evidence_linking_completed_with_warnings"
SIDE_EFFECTS = {
    "read_secrets": False,
    "called_external_model_runtime": False,
    "called_market_data_runtime": False,
    "sent_notification": False,
    "placed_trade_order": False,
    "modified_portfolio": False,
    "wrote_persistent_store": False,
    "modified_schedule_or_service": False,
    "modified_github_remote": False,
    "dashboard_deployed": False,
    "api_server_created": False,
}
SAFETY = {
    "repo_only": True,
    "fixture_only": True,
    "advisory_only": True,
    "preview_only": True,
    "no_external_model_calls": True,
    "no_market_data_calls": True,
    "no_delivery_actions": True,
    "no_persistent_store_writes": True,
    "no_portfolio_actions": True,
    "no_schedule_service_changes": True,
    "dashboard_deploy": False,
    "api_server_created": False,
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


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def repo_path(raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SystemExit("referenced fixture path must be a non-empty string")
    path = Path(raw_path)
    if path.is_absolute():
        raise SystemExit("referenced fixture path must be repo-relative")
    return path


def source_paths(data: dict[str, Any]) -> tuple[Path, Path]:
    sources = as_dict(data.get("input_sources"))
    return (
        repo_path(sources.get("company_intelligence_result_path")),
        repo_path(sources.get("industry_peer_context_result_path")),
    )


def source_score_index(*payloads: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        for item in as_list(payload.get("source_credibility_scores")):
            if isinstance(item, dict) and item.get("source_id"):
                index[str(item["source_id"])] = deepcopy(item)
    return index


def company_refs(company_result: dict[str, Any], forecast: dict[str, Any]) -> list[dict[str, Any]]:
    forecast_sources = set(str(item) for item in as_list(forecast.get("source_ids")))
    result: list[dict[str, Any]] = []
    intelligence = as_dict(company_result.get("company_intelligence"))
    for item in as_list(intelligence.get("items")):
        if not isinstance(item, dict):
            continue
        evidence_ids = [str(source_id) for source_id in as_list(item.get("evidence_source_ids"))]
        matched = sorted(forecast_sources.intersection(evidence_ids))
        if not matched:
            continue
        result.append({
            "ref_type": "company_intelligence",
            "ref_id": item.get("topic_id"),
            "topic": item.get("topic"),
            "summary": item.get("summary"),
            "matched_source_ids": matched,
            "source_credibility_score": item.get("source_credibility_score"),
            "confidence": item.get("confidence"),
            "official_or_company_linked": any("company" in str(source_id) or "2330" in str(source_id) for source_id in matched),
            "requires_human_review": item.get("requires_human_review") is True,
            "advisory_only": True,
        })
    return result


def industry_refs(industry_result: dict[str, Any], forecast: dict[str, Any]) -> list[dict[str, Any]]:
    forecast_sources = set(str(item) for item in as_list(forecast.get("source_ids")))
    result: list[dict[str, Any]] = []
    groups = [
        ("industry_intelligence", as_list(as_dict(industry_result.get("industry_intelligence")).get("items")), "industry_intel_id"),
        ("peer_context", as_list(as_dict(industry_result.get("peer_context")).get("items")), "peer_context_id"),
    ]
    for ref_type, items, id_key in groups:
        for item in items:
            if not isinstance(item, dict):
                continue
            evidence_ids = [str(source_id) for source_id in as_list(item.get("evidence_source_ids"))]
            matched = sorted(forecast_sources.intersection(evidence_ids))
            if not matched:
                continue
            result.append({
                "ref_type": ref_type,
                "ref_id": item.get(id_key),
                "topic": item.get("topic"),
                "summary": item.get("summary"),
                "matched_source_ids": matched,
                "confidence": item.get("confidence"),
                "risk_flags": deepcopy(item.get("risk_flags", [])),
                "industry_context": True,
                "requires_human_review": item.get("requires_human_review") is True,
                "advisory_only": True,
            })
    return result


def credibility_summary(source_ids: list[str], score_index: dict[str, dict[str, Any]], low_threshold: float) -> dict[str, Any]:
    scores = [score_index[source_id] for source_id in source_ids if source_id in score_index]
    missing = [source_id for source_id in source_ids if source_id not in score_index]
    values = [float(item["credibility_score"]) for item in scores if isinstance(item.get("credibility_score"), (int, float))]
    low_ids = sorted(
        str(item.get("source_id"))
        for item in scores
        if isinstance(item.get("credibility_score"), (int, float)) and float(item["credibility_score"]) < low_threshold
    )
    review_ids = sorted(str(item.get("source_id")) for item in scores if item.get("requires_human_review") is True)
    return {
        "source_count": len(source_ids),
        "scored_source_count": len(scores),
        "missing_source_ids": missing,
        "average_credibility_score": round(sum(values) / len(values), 3) if values else None,
        "low_credibility_source_ids": low_ids,
        "review_required_source_ids": review_ids,
        "source_credibility_scores": deepcopy(scores),
        "advisory_only": True,
    }


def evidence_from_refs(refs: list[dict[str, Any]], min_score: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    primary: list[dict[str, Any]] = []
    supporting: list[dict[str, Any]] = []
    for ref in refs:
        score = ref.get("source_credibility_score", ref.get("confidence"))
        target = primary if isinstance(score, (int, float)) and float(score) >= min_score else supporting
        target.append({
            "ref_type": ref.get("ref_type"),
            "ref_id": ref.get("ref_id"),
            "topic": ref.get("topic"),
            "matched_source_ids": deepcopy(ref.get("matched_source_ids", [])),
            "score": score,
            "summary": ref.get("summary"),
        })
    return primary, supporting


def sentiment_metadata(
    forecast: dict[str, Any],
    source_ids: list[str],
    score_index: dict[str, dict[str, Any]],
    sentiment_usage_values: set[str],
) -> dict[str, Any]:
    explicit_ids = set(str(item) for item in as_list(forecast.get("sentiment_source_ids")))
    usage_ids = {
        source_id
        for source_id in source_ids
        if str(as_dict(score_index.get(source_id)).get("usage_policy")) in sentiment_usage_values
    }
    ids = sorted(explicit_ids.union(usage_ids))
    return {
        "sentiment_source_ids": ids,
        "sentiment_source_count": len(ids),
        "usage": "metadata_only_not_core_forecast_evidence",
        "requires_human_review": bool(ids),
        "advisory_only": True,
    }


def build_link(
    forecast: dict[str, Any],
    company_result: dict[str, Any],
    industry_result: dict[str, Any],
    score_index: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    source_ids = sorted(str(item) for item in as_list(forecast.get("source_ids")) if str(item).strip())
    low_threshold = float(policy.get("low_credibility_threshold", 0.5))
    min_primary = float(policy.get("primary_evidence_min_credibility", 0.8))
    company = company_refs(company_result, forecast)
    industry = industry_refs(industry_result, forecast)
    credibility = credibility_summary(source_ids, score_index, low_threshold)
    sentiment = sentiment_metadata(
        forecast,
        source_ids,
        score_index,
        set(str(item) for item in as_list(policy.get("sentiment_usage_policy_values"))),
    )
    primary, supporting = evidence_from_refs(company + industry, min_primary)
    human_review_required = (
        bool(credibility["low_credibility_source_ids"])
        or bool(credibility["review_required_source_ids"])
        or bool(credibility["missing_source_ids"])
        or sentiment["requires_human_review"] is True
        or any(ref.get("requires_human_review") is True for ref in company + industry)
    )
    return {
        "forecast_id": forecast.get("forecast_id"),
        "stock_id": forecast.get("stock_id"),
        "horizon": forecast.get("horizon"),
        "source_ids": source_ids,
        "company_intelligence_refs": company,
        "industry_intelligence_refs": industry,
        "credibility_summary": credibility,
        "primary_evidence": primary,
        "supporting_evidence": supporting,
        "sentiment_metadata": sentiment,
        "human_review_required": human_review_required,
        "advisory_only": True,
    }


def evidence_summary(links: list[dict[str, Any]]) -> dict[str, Any]:
    all_sources = sorted({source_id for link in links for source_id in as_list(link.get("source_ids"))})
    low_ids = sorted({
        source_id
        for link in links
        for source_id in as_list(as_dict(link.get("credibility_summary")).get("low_credibility_source_ids"))
    })
    return {
        "schema_version": "forecast_evidence_summary_v1",
        "forecast_count": len(links),
        "linked_forecast_count": sum(1 for link in links if link.get("primary_evidence") or link.get("supporting_evidence")),
        "source_count": len(all_sources),
        "company_intelligence_ref_count": sum(len(as_list(link.get("company_intelligence_refs"))) for link in links),
        "industry_intelligence_ref_count": sum(len(as_list(link.get("industry_intelligence_refs"))) for link in links),
        "low_credibility_source_ids": low_ids,
        "human_review_required_count": sum(1 for link in links if link.get("human_review_required") is True),
        "advisory_only": True,
        "deterministic_output": True,
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    company_path, industry_path = source_paths(data)
    company_result = load_json(company_path)
    industry_result = load_json(industry_path)
    score_index = source_score_index(company_result, industry_result)
    policy = as_dict(data.get("linking_policy"))
    links = [
        build_link(forecast, company_result, industry_result, score_index, policy)
        for forecast in as_list(data.get("forecasts"))
        if isinstance(forecast, dict)
    ]
    summary = evidence_summary(links)
    warnings = [
        "human_review_required_for_low_credibility_or_sentiment_metadata"
    ] if summary["human_review_required_count"] else []
    decision = DECISION_WARNINGS if warnings else DECISION_COMPLETED
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-090"),
        "run_id": data.get("run_id", "forecast-evidence-linking-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "forecast_evidence_links": links,
        "evidence_summary": summary,
        "validation_summary": {
            "contract_name": CONTRACT_NAME,
            "contract_version": CONTRACT_VERSION,
            "deterministic_output": True,
            "fixture_only": True,
            "forecast_count": len(links),
            "warning_count": len(warnings),
            "warnings": warnings,
        },
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": True,
        "decision": decision,
        "next_recommendation": "Review linked evidence before connecting this advisory fixture to any runtime report or dashboard preview.",
    }


def write_json(payload: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if pretty:
        rendered += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic Forecast Evidence Linking V1 fixture result.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["evidence_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
