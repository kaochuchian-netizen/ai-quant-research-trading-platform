#!/usr/bin/env python3
"""Build a deterministic Evidence Trace Graph V1 fixture result."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/evidence_trace_graph_input.example.json")
CONTRACT_NAME = "evidence_trace_graph"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "evidence_trace_graph_v1"
SUMMARY_SCHEMA_VERSION = "evidence_trace_graph_summary_v1"
DECISION_COMPLETED = "evidence_trace_graph_completed"
DECISION_WARNINGS = "evidence_trace_graph_completed_with_warnings"
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


def slug(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return text.strip("-") or "unknown"


def node_id(kind: str, *parts: Any) -> str:
    return ":".join([kind, *(slug(part) for part in parts)])


def edge_id(edge_type: str, from_node: str, to_node: str) -> str:
    return node_id("edge", edge_type, from_node, to_node)


def add_edge(edges: dict[str, dict[str, Any]], edge_type: str, from_node: str, to_node: str, forecast_id: Any) -> None:
    edge = {
        "edge_id": edge_id(edge_type, from_node, to_node),
        "edge_type": edge_type,
        "from_node_id": from_node,
        "to_node_id": to_node,
        "forecast_id": forecast_id,
        "advisory_only": True,
    }
    edges[edge["edge_id"]] = edge


def source_score_index(links: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for link in links:
        credibility = as_dict(link.get("credibility_summary"))
        for item in as_list(credibility.get("source_credibility_scores")):
            if isinstance(item, dict) and item.get("source_id"):
                index[str(item["source_id"])] = deepcopy(item)
    return index


def evidence_item_node(forecast: dict[str, Any], item: dict[str, Any], role: str) -> dict[str, Any]:
    evidence_id = node_id("evidence", forecast.get("forecast_id"), item.get("ref_type"), item.get("ref_id"), role)
    return {
        "node_id": evidence_id,
        "node_type": "evidence",
        "forecast_id": forecast.get("forecast_id"),
        "ref_type": item.get("ref_type"),
        "ref_id": item.get("ref_id"),
        "topic": item.get("topic"),
        "summary": item.get("summary"),
        "evidence_role": role,
        "matched_source_ids": deepcopy(as_list(item.get("matched_source_ids"))),
        "score": item.get("score"),
        "sentiment_metadata": False,
        "requires_human_review": False,
        "advisory_only": True,
    }


def sentiment_evidence_nodes(forecast: dict[str, Any]) -> list[dict[str, Any]]:
    sentiment = as_dict(forecast.get("sentiment_metadata"))
    result: list[dict[str, Any]] = []
    for source_id in sorted(str(item) for item in as_list(sentiment.get("sentiment_source_ids"))):
        result.append({
            "node_id": node_id("evidence", forecast.get("forecast_id"), "sentiment_metadata", source_id),
            "node_type": "evidence",
            "forecast_id": forecast.get("forecast_id"),
            "ref_type": "sentiment_metadata",
            "ref_id": source_id,
            "topic": "sentiment_metadata",
            "summary": "Sentiment or quantitative context retained as metadata only.",
            "evidence_role": "sentiment_metadata",
            "matched_source_ids": [source_id],
            "score": None,
            "sentiment_metadata": True,
            "requires_human_review": sentiment.get("requires_human_review") is True,
            "advisory_only": True,
        })
    return result


def graph_summary(graph: dict[str, Any]) -> dict[str, Any]:
    edge_types = sorted({str(edge.get("edge_type")) for edge in as_list(graph.get("edges"))})
    review_required = sum(1 for node in as_list(graph.get("review_nodes")) if node.get("review_required") is True)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "graph_id": graph["graph_id"],
        "forecast_node_count": len(as_list(graph.get("forecast_nodes"))),
        "evidence_node_count": len(as_list(graph.get("evidence_nodes"))),
        "source_node_count": len(as_list(graph.get("source_nodes"))),
        "credibility_node_count": len(as_list(graph.get("credibility_nodes"))),
        "review_node_count": len(as_list(graph.get("review_nodes"))),
        "edge_count": len(as_list(graph.get("edges"))),
        "edge_types": edge_types,
        "human_review_required_count": review_required,
        "advisory_only": True,
        "deterministic_output": True,
    }


def build_graph(data: dict[str, Any], forecast_result: dict[str, Any]) -> dict[str, Any]:
    links = [item for item in as_list(forecast_result.get("forecast_evidence_links")) if isinstance(item, dict)]
    score_index = source_score_index(links)
    graph_id = node_id("graph", data.get("run_id", "evidence-trace-graph-fixture"))
    forecast_nodes: dict[str, dict[str, Any]] = {}
    evidence_nodes: dict[str, dict[str, Any]] = {}
    source_nodes: dict[str, dict[str, Any]] = {}
    credibility_nodes: dict[str, dict[str, Any]] = {}
    review_nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    for link in sorted(links, key=lambda item: str(item.get("forecast_id"))):
        forecast_id = link.get("forecast_id")
        forecast_node_id = node_id("forecast", forecast_id)
        forecast_nodes[forecast_node_id] = {
            "node_id": forecast_node_id,
            "node_type": "forecast",
            "forecast_id": forecast_id,
            "stock_id": link.get("stock_id"),
            "horizon": link.get("horizon"),
            "human_review_required": link.get("human_review_required") is True,
            "advisory_only": True,
        }
        review_node_id = node_id("review", forecast_id)
        if link.get("human_review_required") is True:
            review_nodes[review_node_id] = {
                "node_id": review_node_id,
                "node_type": "human_review",
                "forecast_id": forecast_id,
                "review_required": True,
                "review_reason": "Forecast evidence includes low credibility, sentiment metadata, or review-required source context.",
                "status": "pending_human_review",
                "advisory_only": True,
            }

        evidence_items: list[dict[str, Any]] = []
        for item in as_list(link.get("primary_evidence")):
            if isinstance(item, dict):
                evidence_items.append(evidence_item_node(link, item, "primary"))
        for item in as_list(link.get("supporting_evidence")):
            if isinstance(item, dict):
                evidence_items.append(evidence_item_node(link, item, "supporting"))
        evidence_items.extend(sentiment_evidence_nodes(link))

        review_source_ids = set(str(item) for item in as_list(as_dict(link.get("credibility_summary")).get("review_required_source_ids")))
        low_source_ids = set(str(item) for item in as_list(as_dict(link.get("credibility_summary")).get("low_credibility_source_ids")))
        for evidence in sorted(evidence_items, key=lambda item: str(item.get("node_id"))):
            evidence_id = str(evidence["node_id"])
            matched_sources = [str(item) for item in as_list(evidence.get("matched_source_ids"))]
            if evidence.get("sentiment_metadata") is not True:
                evidence["requires_human_review"] = any(source_id in review_source_ids or source_id in low_source_ids for source_id in matched_sources)
            evidence_nodes[evidence_id] = evidence
            add_edge(edges, "forecast_uses_evidence", forecast_node_id, evidence_id, forecast_id)
            if evidence.get("sentiment_metadata") is not True:
                add_edge(edges, "evidence_supports_forecast", evidence_id, forecast_node_id, forecast_id)
            for source_id in sorted(matched_sources):
                source_node_id = node_id("source", source_id)
                score = as_dict(score_index.get(source_id))
                source_nodes[source_node_id] = {
                    "node_id": source_node_id,
                    "node_type": "source",
                    "source_id": source_id,
                    "source_type": score.get("source_type"),
                    "source_tier": score.get("source_tier"),
                    "publisher": score.get("publisher"),
                    "usage_policy": score.get("usage_policy"),
                    "advisory_only": True,
                }
                add_edge(edges, "evidence_refs_source", evidence_id, source_node_id, forecast_id)
                if evidence.get("sentiment_metadata") is True:
                    add_edge(edges, "evidence_is_sentiment_metadata", evidence_id, source_node_id, forecast_id)
                if score:
                    credibility_node_id = node_id("credibility", source_id)
                    credibility_nodes[credibility_node_id] = {
                        "node_id": credibility_node_id,
                        "node_type": "credibility",
                        "source_id": source_id,
                        "credibility_score": score.get("credibility_score"),
                        "source_tier": score.get("source_tier"),
                        "core_scoring_allowed": score.get("core_scoring_allowed"),
                        "requires_human_review": score.get("requires_human_review") is True,
                        "usage_policy": score.get("usage_policy"),
                        "advisory_only": True,
                    }
                    add_edge(edges, "source_has_credibility", source_node_id, credibility_node_id, forecast_id)
            if link.get("human_review_required") is True and evidence.get("requires_human_review") is True:
                add_edge(edges, "evidence_requires_review", evidence_id, review_node_id, forecast_id)

    graph = {
        "graph_id": graph_id,
        "forecast_nodes": sorted(forecast_nodes.values(), key=lambda item: item["node_id"]),
        "evidence_nodes": sorted(evidence_nodes.values(), key=lambda item: item["node_id"]),
        "source_nodes": sorted(source_nodes.values(), key=lambda item: item["node_id"]),
        "credibility_nodes": sorted(credibility_nodes.values(), key=lambda item: item["node_id"]),
        "review_nodes": sorted(review_nodes.values(), key=lambda item: item["node_id"]),
        "edges": sorted(edges.values(), key=lambda item: item["edge_id"]),
    }
    graph["graph_summary"] = graph_summary(graph)
    return graph


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source_path = repo_path(as_dict(data.get("input_sources")).get("forecast_evidence_linking_result_path"))
    forecast_result = load_json(source_path)
    graph = build_graph(data, forecast_result)
    summary = deepcopy(graph["graph_summary"])
    warnings = [
        "human_review_required_evidence_present"
    ] if summary["human_review_required_count"] else []
    decision = DECISION_WARNINGS if warnings else DECISION_COMPLETED
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-091"),
        "run_id": data.get("run_id", "evidence-trace-graph-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "evidence_trace_graph": graph,
        "graph_summary": summary,
        "validation_summary": {
            "contract_name": CONTRACT_NAME,
            "contract_version": CONTRACT_VERSION,
            "deterministic_output": True,
            "fixture_only": True,
            "forecast_node_count": summary["forecast_node_count"],
            "evidence_node_count": summary["evidence_node_count"],
            "edge_count": summary["edge_count"],
            "warning_count": len(warnings),
            "warnings": warnings,
        },
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": True,
        "decision": decision,
        "next_recommendation": "Review trace graph warnings before connecting this advisory fixture to any report or dashboard preview.",
    }


def write_json(payload: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if pretty:
        rendered += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic Evidence Trace Graph V1 fixture result.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["graph_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
