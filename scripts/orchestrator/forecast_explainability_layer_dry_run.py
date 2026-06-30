#!/usr/bin/env python3
"""Build deterministic Forecast Explainability Layer V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/forecast_explainability_layer_input.example.json")
CONTRACT_NAME = "forecast_explainability_layer"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "forecast_explainability_layer_v1"
SUMMARY_SCHEMA_VERSION = "forecast_explainability_summary_v1"
DECISION_COMPLETED = "forecast_explainability_layer_completed"
DECISION_WARNINGS = "forecast_explainability_layer_completed_with_warnings"
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
    "trading_instruction": False,
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


def slug(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return text.strip("-") or "unknown"


def sentence_list(items: list[str], empty: str) -> str:
    cleaned = [item.rstrip(".") for item in items if item and item.strip()]
    if not cleaned:
        return empty
    return "; ".join(cleaned) + "."


def source_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id")): item
        for item in as_list(graph.get("source_nodes"))
        if isinstance(item, dict) and item.get("source_id")
    }


def credibility_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id")): item
        for item in as_list(graph.get("credibility_nodes"))
        if isinstance(item, dict) and item.get("source_id")
    }


def review_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("forecast_id")): item
        for item in as_list(graph.get("review_nodes"))
        if isinstance(item, dict) and item.get("forecast_id")
    }


def evidence_by_forecast(graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in as_list(graph.get("evidence_nodes")):
        if not isinstance(item, dict) or not item.get("forecast_id"):
            continue
        grouped.setdefault(str(item["forecast_id"]), []).append(item)
    for items in grouped.values():
        items.sort(key=lambda item: str(item.get("node_id")))
    return grouped


def source_labels(source_ids: list[Any], sources: dict[str, dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for source_id in sorted(str(item) for item in source_ids):
        source = as_dict(sources.get(source_id))
        publisher = source.get("publisher") or source_id
        tier = source.get("source_tier") or "unknown_tier"
        labels.append(f"{publisher} ({tier})")
    return labels


def evidence_line(evidence: dict[str, Any], sources: dict[str, dict[str, Any]]) -> str:
    topic = evidence.get("topic") or evidence.get("ref_id") or evidence.get("ref_type")
    role = evidence.get("evidence_role")
    score = evidence.get("score")
    score_text = f", score {score:.3f}" if isinstance(score, (int, float)) and not isinstance(score, bool) else ""
    refs = ", ".join(source_labels(as_list(evidence.get("matched_source_ids")), sources))
    return f"{topic} [{role}{score_text}] - {evidence.get('summary')} Sources: {refs}"


def source_is_official(source: dict[str, Any]) -> bool:
    tier = str(source.get("source_tier", "")).lower()
    policy = str(source.get("usage_policy", "")).lower()
    return "tier_1" in tier or "official" in tier or "company" in tier or "company" in policy


def explainability_summary(explanations: list[dict[str, Any]], graph_summary: dict[str, Any]) -> dict[str, Any]:
    review_count = sum(1 for item in explanations if item.get("requires_human_review") is True)
    risk_count = sum(1 for item in explanations if item.get("credibility_risk_count", 0) > 0)
    sentiment_count = sum(1 for item in explanations if item.get("sentiment_metadata_count", 0) > 0)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "explanation_count": len(explanations),
        "forecast_count": len({str(item.get("forecast_id")) for item in explanations}),
        "stock_count": len({str(item.get("stock_id")) for item in explanations}),
        "human_review_required_count": review_count,
        "credibility_risk_forecast_count": risk_count,
        "sentiment_metadata_forecast_count": sentiment_count,
        "source_trace_ref_count": sum(len(as_list(item.get("source_trace_refs"))) for item in explanations),
        "source_graph_id": graph_summary.get("graph_id"),
        "advisory_only": True,
        "deterministic_output": True,
    }


def build_explanation(
    forecast: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    credibility: dict[str, dict[str, Any]],
    reviews: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    forecast_id = str(forecast.get("forecast_id"))
    primary = [item for item in evidence_items if item.get("evidence_role") == "primary"]
    supporting = [item for item in evidence_items if item.get("evidence_role") == "supporting"]
    sentiment = [item for item in evidence_items if item.get("sentiment_metadata") is True]
    official = [
        item
        for item in evidence_items
        if any(source_is_official(as_dict(sources.get(str(source_id)))) for source_id in as_list(item.get("matched_source_ids")))
    ]
    industry = [
        item
        for item in evidence_items
        if item.get("ref_type") in {"industry_intelligence", "peer_context"}
    ]
    risk_source_ids = sorted({
        str(source_id)
        for item in evidence_items
        for source_id in as_list(item.get("matched_source_ids"))
        if as_dict(credibility.get(str(source_id))).get("requires_human_review") is True
        or (
            isinstance(as_dict(credibility.get(str(source_id))).get("credibility_score"), (int, float))
            and float(as_dict(credibility.get(str(source_id))).get("credibility_score")) < 0.5
        )
    })
    review = as_dict(reviews.get(forecast_id))
    requires_review = forecast.get("human_review_required") is True or bool(risk_source_ids)
    primary_topics = [str(item.get("topic") or item.get("ref_id")) for item in primary]
    support_topics = [str(item.get("topic") or item.get("ref_id")) for item in supporting]
    risk_lines = []
    for source_id in risk_source_ids:
        score = as_dict(credibility.get(source_id))
        source = as_dict(sources.get(source_id))
        risk_lines.append(
            f"{source_id} is {source.get('source_tier')} with credibility {score.get('credibility_score')} and review_required={score.get('requires_human_review')}"
        )
    trace_refs = sorted({
        str(forecast.get("node_id")),
        *(str(item.get("node_id")) for item in evidence_items),
        *(f"source:{source_id}" for item in evidence_items for source_id in as_list(item.get("matched_source_ids"))),
        *(f"credibility:{source_id}" for item in evidence_items for source_id in as_list(item.get("matched_source_ids")) if source_id in credibility),
        *(str(review.get("node_id")) for _ in [review] if review.get("node_id")),
    })
    return {
        "explanation_id": f"explain:{slug(forecast_id)}",
        "forecast_id": forecast_id,
        "stock_id": forecast.get("stock_id"),
        "horizon": forecast.get("horizon"),
        "explanation_summary": (
            f"Forecast {forecast_id} for stock {forecast.get('stock_id')} over {forecast.get('horizon')} "
            f"is explained by {len(primary)} primary evidence item(s), {len(supporting)} supporting item(s), "
            f"and {len(sentiment)} sentiment metadata item(s)."
        ),
        "primary_reasoning": sentence_list([evidence_line(item, sources) for item in primary], "No primary evidence was present in the fixture graph."),
        "supporting_reasoning": sentence_list([evidence_line(item, sources) for item in supporting], "No supporting evidence was present in the fixture graph."),
        "official_evidence_summary": sentence_list([evidence_line(item, sources) for item in official], "No official or company-linked evidence was present in the fixture graph."),
        "industry_context_summary": sentence_list([evidence_line(item, sources) for item in industry], "No industry or peer context evidence was present in the fixture graph."),
        "sentiment_metadata_summary": sentence_list([evidence_line(item, sources) for item in sentiment], "No sentiment metadata was present in the fixture graph."),
        "credibility_risk_summary": sentence_list(risk_lines, "No low-credibility or review-required source was present in the fixture graph."),
        "human_review_summary": (
            f"Human review is required: {review.get('review_reason')}"
            if requires_review and review
            else "Human review is not required by this fixture graph."
        ),
        "advisory_disclaimer": "This explanation is advisory-only fixture output for review context; it is not an instruction to transact or manage any portfolio.",
        "source_trace_refs": trace_refs,
        "primary_reason_count": len(primary),
        "supporting_reason_count": len(supporting),
        "official_evidence_count": len(official),
        "industry_context_count": len(industry),
        "sentiment_metadata_count": len(sentiment),
        "credibility_risk_count": len(risk_source_ids),
        "requires_human_review": requires_review,
        "advisory_only": True,
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source_path = repo_path(as_dict(data.get("input_sources")).get("evidence_trace_graph_result_path"))
    trace_result = load_json(source_path)
    graph = as_dict(trace_result.get("evidence_trace_graph"))
    graph_summary = as_dict(trace_result.get("graph_summary"))
    sources = source_index(graph)
    credibility = credibility_index(graph)
    reviews = review_index(graph)
    grouped_evidence = evidence_by_forecast(graph)
    explanations = [
        build_explanation(forecast, grouped_evidence.get(str(forecast.get("forecast_id")), []), sources, credibility, reviews)
        for forecast in sorted(as_list(graph.get("forecast_nodes")), key=lambda item: str(as_dict(item).get("forecast_id")))
        if isinstance(forecast, dict)
    ]
    summary = explainability_summary(explanations, graph_summary)
    warnings = []
    if summary["human_review_required_count"]:
        warnings.append("human_review_required_explanations_present")
    if summary["credibility_risk_forecast_count"]:
        warnings.append("credibility_risk_explanations_present")
    decision = DECISION_WARNINGS if warnings else DECISION_COMPLETED
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-092"),
        "run_id": data.get("run_id", "forecast-explainability-layer-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "forecast_explanations": explanations,
        "explainability_summary": summary,
        "validation_summary": {
            "contract_name": CONTRACT_NAME,
            "contract_version": CONTRACT_VERSION,
            "deterministic_output": True,
            "fixture_only": True,
            "explanation_count": summary["explanation_count"],
            "human_review_required_count": summary["human_review_required_count"],
            "warning_count": len(warnings),
            "warnings": warnings,
        },
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": True,
        "decision": decision,
        "next_recommendation": "Review advisory explanations and human-review warnings before any report or dashboard preview integration.",
    }


def write_json(payload: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if pretty:
        rendered += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic Forecast Explainability Layer V1 fixture result.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["explainability_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
