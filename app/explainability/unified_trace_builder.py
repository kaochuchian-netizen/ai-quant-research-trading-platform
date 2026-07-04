"""Build deterministic Unified Explainability & Evidence Trace artifacts."""
from __future__ import annotations
from typing import Any
from .unified_trace_schema import ARTIFACT_TYPE, SCHEMA_VERSION, SOURCE_CATEGORIES, TASK_ID, safety_policy

CONTEXT_SECTION_BY_SOURCE = {
    "company_filing": "source_summary.official_primary_source",
    "shioaji_sinopac": "source_summary.official_market_source",
    "twse_openapi": "twse_context",
    "finmind": "finmind_context",
    "yfinance_yahoo": "yfinance_context",
    "gemini_google_generative_ai": "explainability_context",
    "broker_target_price_metadata": "news_context",
    "google_news_rss": "news_context",
}

FACTOR_BY_SOURCE = {
    "company_filing": ("factor_company_disclosure", "Company disclosure anchor"),
    "shioaji_sinopac": ("factor_runtime_market_data", "Runtime market data anchor"),
    "twse_openapi": ("factor_twse_chip_flow", "TWSE official market/chip context"),
    "finmind": ("factor_finmind_supplement", "FinMind normalized supplemental context"),
    "yfinance_yahoo": ("factor_external_proxy", "ADR and US market proxy context"),
    "gemini_google_generative_ai": ("factor_ai_generated_summary", "AI generated explanation draft"),
    "broker_target_price_metadata": ("factor_broker_metadata", "Broker target/rating metadata"),
    "google_news_rss": ("factor_news_event_detection", "Headline event/sentiment detection"),
}

EXCLUSION_REASONS = {
    "broker_target_price_metadata": "Broker target / analyst opinion is metadata only and cannot directly affect rating/action/confidence.",
    "google_news_rss": "Google News RSS is event detection / sentiment support only and cannot be core forecast evidence.",
    "yfinance_yahoo": "yfinance/Yahoo is an external reference/proxy and cannot replace official sources.",
    "finmind": "FinMind is a normalized external data provider and cannot replace MOPS / TWSE / company official information.",
    "gemini_google_generative_ai": "Gemini is AI-generated analysis and not original evidence.",
}


def _category_map(context: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for category, rows in context.get("source_summary", {}).items():
        for row in rows:
            result[row.get("source_id", "")] = category
    return result


def _source_explanations(context: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {category: [] for category in SOURCE_CATEGORIES}
    for category, rows in context.get("source_summary", {}).items():
        for row in sorted(rows, key=lambda item: item.get("source_id", "")):
            source_id = row["source_id"]
            output.setdefault(category, []).append(
                {
                    "source_id": source_id,
                    "provider": row.get("provider"),
                    "credibility_level": row.get("credibility_level"),
                    "decision_value": row.get("decision_value"),
                    "explanation": _source_explanation_text(category, source_id),
                    "allowed_usage": _allowed_usage(category, source_id),
                    "disallowed_usage": _disallowed_usage(category, source_id),
                    "direct_rating_action_confidence_impact": False,
                }
            )
    return {category: output.get(category, []) for category in SOURCE_CATEGORIES}


def _source_explanation_text(category: str, source_id: str) -> str:
    if source_id in EXCLUSION_REASONS:
        return EXCLUSION_REASONS[source_id]
    if category == "official_primary_source":
        return "Official primary source can anchor context but still does not mutate production decisions in this artifact."
    if category == "official_market_source":
        return "Official market source can explain market/chip context but cannot directly change production rating/action/confidence here."
    return "Source is included as attributed context with no direct production decision mutation."


def _allowed_usage(category: str, source_id: str) -> list[str]:
    if source_id == "google_news_rss":
        return ["event_detection", "sentiment_support", "metadata_warning"]
    if source_id == "broker_target_price_metadata":
        return ["sentiment_metadata", "analyst_opinion_context"]
    if source_id == "gemini_google_generative_ai":
        return ["draft_explanation", "summary_generation_after_source_attribution"]
    if category in {"official_primary_source", "official_market_source"}:
        return ["context_anchor", "report_explanation", "dashboard_drill_down"]
    return ["supplemental_context", "report_explanation", "dashboard_drill_down"]


def _disallowed_usage(category: str, source_id: str) -> list[str]:
    disallowed = ["direct_rating_action_confidence_change", "production_weight_mutation", "order_execution"]
    if source_id in {"finmind", "yfinance_yahoo", "google_news_rss", "broker_target_price_metadata", "gemini_google_generative_ai"}:
        disallowed.append("official_source_replacement")
    if source_id == "google_news_rss":
        disallowed.append("core_forecast_evidence")
    if source_id == "gemini_google_generative_ai":
        disallowed.append("original_evidence")
    return disallowed


def _trace_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    category_by_source = _category_map(context)
    for source in sorted(context.get("source_credibility_summary", []), key=lambda item: item.get("source_id", "")):
        source_id = source["source_id"]
        factor_id, factor_name = FACTOR_BY_SOURCE.get(source_id, (f"factor_{source_id}", source_id.replace("_", " ").title()))
        explanation_id = f"explain_{source_id}"
        report_block_id = f"report_block_{source_id}"
        dashboard_block_id = f"dashboard_card_{source_id}"
        category = category_by_source.get(source_id, source.get("source_category", "unknown"))
        rows.append(
            {
                "source_id": source_id,
                "provider": source.get("provider"),
                "source_type": category,
                "credibility_level": source.get("credibility_level"),
                "context_section": CONTEXT_SECTION_BY_SOURCE.get(source_id, f"source_summary.{category}"),
                "factor_id": factor_id,
                "factor_name": factor_name,
                "explanation_id": explanation_id,
                "explanation_summary": _source_explanation_text(category, source_id),
                "report_block_id": report_block_id,
                "dashboard_block_id": dashboard_block_id,
                "allowed_usage": _allowed_usage(category, source_id),
                "disallowed_usage": _disallowed_usage(category, source_id),
                "direct_rating_action_confidence_impact": False,
            }
        )
    return rows


def _factor_explanations(trace_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "factor_id": row["factor_id"],
            "factor_name": row["factor_name"],
            "source_ids": [row["source_id"]],
            "rationale": row["explanation_summary"],
            "allowed_usage": row["allowed_usage"],
            "disallowed_usage": row["disallowed_usage"],
            "direct_rating_action_confidence_impact": False,
        }
        for row in trace_rows
    ]


def _graph(trace_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in trace_rows:
        sequence = [
            (f"source:{row['source_id']}", "source", row["provider"]),
            (f"context:{row['context_section']}", "context_section", row["context_section"]),
            (f"factor:{row['factor_id']}", "factor", row["factor_name"]),
            (f"explanation:{row['explanation_id']}", "explanation", row["explanation_summary"]),
            (f"report:{row['report_block_id']}", "report_block", row["report_block_id"]),
            (f"dashboard:{row['dashboard_block_id']}", "dashboard_block", row["dashboard_block_id"]),
        ]
        for node_id, node_type, label in sequence:
            if node_id not in seen:
                nodes.append({"node_id": node_id, "node_type": node_type, "label": label})
                seen.add(node_id)
        for a, b in zip(sequence, sequence[1:]):
            edges.append({"from": a[0], "to": b[0], "relation": "supports_trace", "direct_rating_action_confidence_impact": False})
    return {"nodes": sorted(nodes, key=lambda item: item["node_id"]), "edges": sorted(edges, key=lambda item: (item["from"], item["to"]))}


def build_unified_explainability_artifact(context: dict[str, Any]) -> dict[str, Any]:
    trace_rows = _trace_rows(context)
    exclusions = {source_id: reason for source_id, reason in sorted(EXCLUSION_REASONS.items())}
    metadata_sources = context.get("exclusions", {}).get("metadata_only_sources", [])
    official_replacement_disallowed = context.get("exclusions", {}).get("official_source_replacement_disallowed_sources", [])
    report_blocks = [
        {"block_id": "report_source_credibility_summary", "title": "Source credibility summary", "source_ids": sorted({row["source_id"] for row in trace_rows}), "deterministic": True},
        {"block_id": "report_factor_rationale_summary", "title": "Factor rationale summary", "factor_ids": [row["factor_id"] for row in trace_rows], "deterministic": True},
        {"block_id": "report_metadata_only_warning", "title": "Metadata-only warning", "source_ids": metadata_sources, "deterministic": True},
        {"block_id": "report_official_source_replacement_warning", "title": "Official-source replacement warning", "source_ids": official_replacement_disallowed, "deterministic": True},
        {"block_id": "report_evidence_trace_summary", "title": "Evidence trace summary", "trace_count": len(trace_rows), "deterministic": True},
    ]
    dashboard_blocks = [
        {"block_id": "dashboard_evidence_cards", "title": "Evidence cards", "node_type": "source", "deterministic": True},
        {"block_id": "dashboard_factor_contribution_cards", "title": "Factor contribution cards", "node_type": "factor", "deterministic": True},
        {"block_id": "dashboard_excluded_source_cards", "title": "Excluded source cards", "source_ids": sorted(exclusions), "deterministic": True},
        {"block_id": "dashboard_source_credibility_badges", "title": "Source credibility badges", "source_ids": sorted({row["source_id"] for row in trace_rows}), "deterministic": True},
        {"block_id": "dashboard_trace_graph", "title": "Trace graph nodes / edges", "node_count": len(_graph(trace_rows)["nodes"]), "edge_count": len(_graph(trace_rows)["edges"]), "deterministic": True},
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "artifact_type": ARTIFACT_TYPE,
        "generated_at": context.get("generated_at"),
        "symbol": context.get("symbol"),
        "market": context.get("market"),
        "context_ref": {
            "schema_version": context.get("schema_version"),
            "task_id": context.get("task_id"),
            "artifact_type": context.get("artifact_type"),
            "template_path": "templates/prediction_context_artifact.example.json",
        },
        "source_explanations": _source_explanations(context),
        "factor_explanations": _factor_explanations(trace_rows),
        "evidence_links": trace_rows,
        "evidence_trace_graph": _graph(trace_rows),
        "exclusion_reasons": exclusions,
        "confidence_rationale": {
            "summary": "Confidence can be explained from prediction context calibration, source credibility, factor effectiveness, and evidence trace; this task does not rewrite production confidence.",
            "context_refs": ["confidence_calibration_context", "source_credibility_summary", "factor_effectiveness_context", "explainability_context"],
            "direct_rating_action_confidence_impact": False,
        },
        "metadata_only_warnings": [{"source_id": source_id, "warning": exclusions.get(source_id, "metadata only")} for source_id in metadata_sources],
        "official_source_replacement_warnings": [{"source_id": source_id, "warning": exclusions.get(source_id, "cannot replace official source")} for source_id in official_replacement_disallowed],
        "report_explanation_blocks": report_blocks,
        "dashboard_explanation_blocks": dashboard_blocks,
        "safety_policy": safety_policy(),
        "warnings": [
            "Deterministic offline explainability artifact only.",
            "No rating/action/confidence mutation is allowed in this task.",
            "No report delivery or Dashboard UI modification is performed.",
        ],
    }
