#!/usr/bin/env python3
"""Validate Evidence Trace Graph V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_NAME = "evidence_trace_graph"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "evidence_trace_graph_v1"
SUMMARY_SCHEMA_VERSION = "evidence_trace_graph_summary_v1"
DECISIONS = {
    "evidence_trace_graph_completed",
    "evidence_trace_graph_completed_with_warnings",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "evidence_trace_graph",
    "graph_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
GRAPH_FIELDS = [
    "graph_id",
    "forecast_nodes",
    "evidence_nodes",
    "source_nodes",
    "credibility_nodes",
    "review_nodes",
    "edges",
    "graph_summary",
]
REQUIRED_EDGE_TYPES = {
    "forecast_uses_evidence",
    "evidence_refs_source",
    "source_has_credibility",
    "evidence_requires_review",
    "evidence_supports_forecast",
    "evidence_is_sentiment_metadata",
}
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


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


def validate_node(name: str, node: Any, node_type: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(node, dict):
        return [f"{name} must be an object"]
    for key in ["node_id", "node_type", "advisory_only"]:
        if key not in node:
            errors.append(f"{name} missing {key}")
    if node.get("node_type") != node_type:
        errors.append(f"{name}.node_type must be {node_type}")
    if not str(node.get("node_id", "")).strip():
        errors.append(f"{name}.node_id is required")
    if node.get("advisory_only") is not True:
        errors.append(f"{name}.advisory_only must be true")
    return errors


def validate_evidence_node(name: str, node: Any) -> list[str]:
    errors = validate_node(name, node, "evidence")
    if not isinstance(node, dict):
        return errors
    for key in ["forecast_id", "ref_type", "ref_id", "evidence_role", "matched_source_ids", "sentiment_metadata", "requires_human_review"]:
        if key not in node:
            errors.append(f"{name} missing {key}")
    if not isinstance(node.get("matched_source_ids"), list) or not node.get("matched_source_ids"):
        errors.append(f"{name}.matched_source_ids must be a non-empty list")
    if node.get("score") is not None and not is_score(node.get("score")):
        errors.append(f"{name}.score must be 0.0-1.0 or null")
    if not isinstance(node.get("sentiment_metadata"), bool):
        errors.append(f"{name}.sentiment_metadata must be boolean")
    if not isinstance(node.get("requires_human_review"), bool):
        errors.append(f"{name}.requires_human_review must be boolean")
    return errors


def validate_edge(edge: Any, index: int, node_ids: set[str]) -> list[str]:
    name = f"edges[{index}]"
    errors: list[str] = []
    if not isinstance(edge, dict):
        return [f"{name} must be an object"]
    for key in ["edge_id", "edge_type", "from_node_id", "to_node_id", "forecast_id", "advisory_only"]:
        if key not in edge:
            errors.append(f"{name} missing {key}")
    if edge.get("edge_type") not in REQUIRED_EDGE_TYPES:
        errors.append(f"{name}.edge_type is invalid")
    if edge.get("from_node_id") not in node_ids:
        errors.append(f"{name}.from_node_id must reference an existing node")
    if edge.get("to_node_id") not in node_ids:
        errors.append(f"{name}.to_node_id must reference an existing node")
    if edge.get("advisory_only") is not True:
        errors.append(f"{name}.advisory_only must be true")
    return errors


def validate_summary(summary: Any, graph: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(summary, dict):
        return ["graph_summary must be an object"]
    for key in [
        "schema_version",
        "graph_id",
        "forecast_node_count",
        "evidence_node_count",
        "source_node_count",
        "credibility_node_count",
        "review_node_count",
        "edge_count",
        "edge_types",
        "human_review_required_count",
        "advisory_only",
        "deterministic_output",
    ]:
        if key not in summary:
            errors.append(f"graph_summary missing {key}")
    if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append("graph_summary.schema_version is invalid")
    expected_counts = {
        "forecast_node_count": len(as_list(graph.get("forecast_nodes"))),
        "evidence_node_count": len(as_list(graph.get("evidence_nodes"))),
        "source_node_count": len(as_list(graph.get("source_nodes"))),
        "credibility_node_count": len(as_list(graph.get("credibility_nodes"))),
        "review_node_count": len(as_list(graph.get("review_nodes"))),
        "edge_count": len(as_list(graph.get("edges"))),
    }
    for key, value in expected_counts.items():
        if summary.get(key) != value:
            errors.append(f"graph_summary.{key} must match graph")
    edge_types = set(as_list(summary.get("edge_types")))
    missing_edge_types = sorted(REQUIRED_EDGE_TYPES - edge_types)
    for edge_type in missing_edge_types:
        errors.append(f"graph_summary.edge_types missing {edge_type}")
    if summary.get("advisory_only") is not True:
        errors.append("graph_summary.advisory_only must be true")
    if summary.get("deterministic_output") is not True:
        errors.append("graph_summary.deterministic_output must be true")
    return errors


def validate_graph(graph: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(graph, dict):
        return ["evidence_trace_graph must be an object"]
    for key in missing(graph, GRAPH_FIELDS):
        errors.append(f"evidence_trace_graph missing {key}")
    if not str(graph.get("graph_id", "")).strip():
        errors.append("evidence_trace_graph.graph_id is required")
    node_ids: set[str] = set()
    for collection in ["forecast_nodes", "evidence_nodes", "source_nodes", "credibility_nodes", "review_nodes"]:
        if not isinstance(graph.get(collection), list):
            errors.append(f"evidence_trace_graph.{collection} must be a list")
        for index, node in enumerate(as_list(graph.get(collection))):
            if isinstance(node, dict) and node.get("node_id"):
                node_id = str(node["node_id"])
                if node_id in node_ids:
                    errors.append(f"duplicate node_id: {node_id}")
                node_ids.add(node_id)
            expected_type = {
                "forecast_nodes": "forecast",
                "source_nodes": "source",
                "credibility_nodes": "credibility",
                "review_nodes": "human_review",
            }.get(collection)
            if collection == "evidence_nodes":
                errors.extend(validate_evidence_node(f"{collection}[{index}]", node))
            elif expected_type:
                errors.extend(validate_node(f"{collection}[{index}]", node, expected_type))
    if not as_list(graph.get("forecast_nodes")):
        errors.append("evidence_trace_graph.forecast_nodes must be non-empty")
    if not as_list(graph.get("evidence_nodes")):
        errors.append("evidence_trace_graph.evidence_nodes must be non-empty")
    edge_types: set[str] = set()
    edge_ids: set[str] = set()
    for index, edge in enumerate(as_list(graph.get("edges"))):
        errors.extend(validate_edge(edge, index, node_ids))
        if isinstance(edge, dict):
            edge_type = edge.get("edge_type")
            if isinstance(edge_type, str):
                edge_types.add(edge_type)
            edge_identifier = str(edge.get("edge_id", ""))
            if edge_identifier in edge_ids:
                errors.append(f"duplicate edge_id: {edge_identifier}")
            edge_ids.add(edge_identifier)
    for edge_type in sorted(REQUIRED_EDGE_TYPES - edge_types):
        errors.append(f"missing required edge type: {edge_type}")
    errors.extend(validate_summary(graph.get("graph_summary"), graph))
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
    graph_summary = payload.get("graph_summary") if isinstance(payload.get("graph_summary"), dict) else {}
    for key in ["forecast_node_count", "evidence_node_count", "edge_count"]:
        if summary.get(key) != graph_summary.get(key):
            errors.append(f"validation_summary.{key} must match graph_summary")
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
    errors.extend(validate_graph(payload.get("evidence_trace_graph")))
    if payload.get("graph_summary") != as_dict(payload.get("evidence_trace_graph")).get("graph_summary"):
        errors.append("top-level graph_summary must match evidence_trace_graph.graph_summary")
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
        "decision": "evidence_trace_graph_completed" if not errors else "validation_failed",
        "validated_schema_version": SCHEMA_VERSION,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Evidence Trace Graph V1 fixture result.")
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
