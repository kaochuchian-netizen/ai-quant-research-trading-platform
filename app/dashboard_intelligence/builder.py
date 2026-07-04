"""Build deterministic Dashboard Decision Intelligence artifacts."""
from __future__ import annotations
from typing import Any

from .schemas import (
    ADVISORY_ONLY_BADGE_IDS,
    ARTIFACT_TYPE,
    DASHBOARD_PAGE_IDS,
    FORMAL_INTEGRATION_IDS,
    METADATA_ONLY_BADGE_IDS,
    SCHEMA_VERSION,
    SOURCE_CATEGORIES,
    SUMMARY_CARD_IDS,
    TASK_ID,
    publish_policy,
    safety_policy,
)


def _page(page_id: str, title: str) -> dict[str, Any]:
    return {
        "page_id": page_id,
        "title": title,
        "deterministic": True,
        "drilldown_enabled": True,
        "publish_url": None,
        "direct_rating_action_confidence_impact": False,
    }


def _dashboard_page_model() -> list[dict[str, Any]]:
    titles = {
        "overview": "Overview",
        "source_credibility": "Source credibility",
        "factor_rationale": "Factor rationale",
        "evidence_trace": "Evidence trace",
        "formal_integrations": "Formal integrations",
        "market_regime": "Market regime",
        "rolling_evaluation": "Rolling evaluation",
        "warnings": "Warnings",
        "advisory_policy": "Advisory policy",
    }
    return [_page(page_id, titles[page_id]) for page_id in DASHBOARD_PAGE_IDS]


def _summary_cards(context: dict[str, Any], report: dict[str, Any], explainability: dict[str, Any]) -> list[dict[str, Any]]:
    payload = {
        "symbol_summary_card": {"title": "Symbol", "value": context.get("symbol"), "subtitle": context.get("market")},
        "report_window_summary_card": {"title": "Report window", "value": report.get("report_window")},
        "market_regime_summary_card": {"title": "Market regime", "value": context.get("market_regime_context", {}).get("regime_label", "sample_only")},
        "confidence_rationale_summary_card": {"title": "Confidence rationale", "value": explainability.get("confidence_rationale", {}).get("summary", "Advisory confidence rationale only.")},
        "advisory_only_summary_card": {"title": "Advisory only", "value": "Research-only; no trading advice; no order execution."},
    }
    return [
        {"card_id": card_id, "deterministic": True, "direct_rating_action_confidence_impact": False, **payload[card_id]}
        for card_id in SUMMARY_CARD_IDS
    ]


def _source_credibility_cards(context: dict[str, Any]) -> list[dict[str, Any]]:
    source_summary = context.get("source_summary", {})
    cards: list[dict[str, Any]] = []
    for category in SOURCE_CATEGORIES:
        sources = source_summary.get(category, [])
        cards.append({
            "card_id": f"{category}_card",
            "category": category,
            "source_ids": [row.get("source_id") for row in sources],
            "providers": [row.get("provider") for row in sources],
            "count": len(sources),
            "allowed_usage": "Display source role and credibility context for drill-down.",
            "disallowed_usage": "Must not directly mutate rating/action/confidence.",
            "direct_rating_action_confidence_impact": False,
            "deterministic": True,
        })
    return cards


def _factor_rationale_cards(explainability: dict[str, Any]) -> list[dict[str, Any]]:
    cards = []
    for item in explainability.get("factor_explanations", []):
        factor_id = item.get("factor_id") or item.get("id") or "unknown_factor"
        cards.append({
            "card_id": f"{factor_id}_rationale_card",
            "factor_id": factor_id,
            "factor_name": item.get("factor_name") or item.get("name") or factor_id,
            "factor_category": item.get("factor_category") or item.get("category") or "context",
            "rationale_summary": item.get("rationale_summary") or item.get("summary") or item.get("explanation") or "Deterministic factor rationale sample.",
            "supporting_sources": item.get("supporting_sources") or item.get("source_ids") or [],
            "allowed_usage": item.get("allowed_usage", "Dashboard explanation and drill-down only."),
            "disallowed_usage": item.get("disallowed_usage", "No direct rating/action/confidence mutation."),
            "direct_rating_action_confidence_impact": False,
            "deterministic": True,
        })
    return sorted(cards, key=lambda row: row["factor_id"])


def _evidence_trace_cards(explainability: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    graph = explainability.get("evidence_trace_graph", {})
    node_count = len(graph.get("nodes", []))
    edge_count = len(graph.get("edges", []))
    report_block_ids = [block.get("block_id") for block in report.get("dashboard_ready_blocks", [])]
    cards = []
    for index, item in enumerate(explainability.get("evidence_links", []), start=1):
        source_id = item.get("source_id") or item.get("source") or "unknown_source"
        factor_id = item.get("factor_id") or "context_factor"
        explanation_id = item.get("explanation_id") or f"explanation_{index:02d}"
        dashboard_block_id = report_block_ids[(index - 1) % len(report_block_ids)] if report_block_ids else "summary_card"
        cards.append({
            "card_id": f"evidence_trace_{index:02d}",
            "source_id": source_id,
            "context_section": item.get("context_section") or item.get("section") or "prediction_context",
            "factor_id": factor_id,
            "explanation_id": explanation_id,
            "report_block_id": item.get("report_block_id") or "evidence_trace_summary",
            "dashboard_block_id": item.get("dashboard_block_id") or dashboard_block_id,
            "trace_summary": item.get("trace_summary") or item.get("summary") or "Deterministic evidence trace link for dashboard drill-down.",
            "node_count": node_count,
            "edge_count": edge_count,
            "direct_rating_action_confidence_impact": False,
            "deterministic": True,
        })
    return cards


def _formal_integration_cards(report: dict[str, Any]) -> list[dict[str, Any]]:
    integrations = {row.get("integration_id"): row for row in report.get("formal_report_integration_section", {}).get("integrations", [])}
    cards = []
    for integration_id in FORMAL_INTEGRATION_IDS:
        row = integrations.get(integration_id, {})
        cards.append({
            "card_id": f"{integration_id}_card",
            "integration_id": integration_id,
            "title": row.get("title") or integration_id,
            "source_id": row.get("source_id"),
            "artifact_path": row.get("artifact_path"),
            "allowed_usage": "Dashboard context and attribution only.",
            "disallowed_usage": "No direct rating/action/confidence mutation and no official-source replacement unless explicitly official.",
            "direct_rating_action_confidence_impact": False,
            "deterministic": True,
        })
    return cards


def _warning_cards(report: dict[str, Any]) -> list[dict[str, Any]]:
    cards = []
    for item in report.get("warning_section", {}).get("warnings", []):
        source_id = item.get("source_id", "unknown_source")
        warning_type = item.get("warning_type", "warning")
        cards.append({
            "card_id": f"{source_id}_{warning_type}_card",
            "source_id": source_id,
            "warning_type": warning_type,
            "warning_summary": item.get("warning") or item.get("summary") or item.get("reason") or "Warning policy applies.",
            "direct_rating_action_confidence_impact": False,
            "deterministic": True,
        })
    return sorted(cards, key=lambda row: row["card_id"])


def _exclusion_cards(report: dict[str, Any]) -> list[dict[str, Any]]:
    exclusions = report.get("exclusion_section", {}).get("exclusion_reasons", {})
    return [
        {
            "card_id": f"{source_id}_exclusion_card",
            "source_id": source_id,
            "exclusion_reason": reason,
            "direct_rating_action_confidence_impact": False,
            "deterministic": True,
        }
        for source_id, reason in sorted(exclusions.items())
    ]


def _metadata_only_badges() -> list[dict[str, Any]]:
    payload = {
        "broker_target_analyst_opinion_metadata_only": "Broker target / analyst opinion metadata only.",
        "google_news_rss_support_only": "Google News RSS support only; event detection / sentiment support.",
        "gemini_generated_analysis_only": "Gemini generated analysis only; not original evidence.",
    }
    return [{"badge_id": badge_id, "label": payload[badge_id], "metadata_only": True, "direct_rating_action_confidence_impact": False} for badge_id in METADATA_ONLY_BADGE_IDS]


def _advisory_only_badges() -> list[dict[str, Any]]:
    payload = {
        "advisory_only": {"advisory_only": True},
        "not_trading_advice": {"not_trading_advice": True},
        "no_order_execution": {"no_order_execution": True},
        "no_direct_rating_action_confidence_mutation": {"no_direct_rating_action_confidence_mutation": True},
    }
    return [{"badge_id": badge_id, "label": badge_id.replace("_", " "), **payload[badge_id]} for badge_id in ADVISORY_ONLY_BADGE_IDS]


def _drilldown_links(symbol: str) -> list[dict[str, Any]]:
    slugs = {
        "overview": "overview",
        "source_credibility": "source-credibility",
        "factor_rationale": "factor-rationale",
        "evidence_trace": "evidence-trace",
        "formal_integrations": "formal-integrations",
        "market_regime": "market-regime",
        "rolling_evaluation": "rolling-evaluation",
        "warnings": "warnings",
        "advisory_policy": "advisory-policy",
    }
    return [
        {"link_id": f"{page_id}_drilldown", "page_id": page_id, "href": f"dashboard://symbol/{symbol}/{slug}", "placeholder_only": True, "published": False}
        for page_id, slug in slugs.items()
    ]


def build_dashboard_decision_intelligence_artifact(prediction_context: dict[str, Any], explainability: dict[str, Any], report_assembly: dict[str, Any]) -> dict[str, Any]:
    symbol = prediction_context.get("symbol") or report_assembly.get("symbol")
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "artifact_type": ARTIFACT_TYPE,
        "generated_at": prediction_context.get("generated_at") or report_assembly.get("generated_at"),
        "symbol": symbol,
        "market": prediction_context.get("market") or report_assembly.get("market"),
        "dashboard_context_ref": {"artifact_type": ARTIFACT_TYPE, "template_path": "templates/dashboard_decision_intelligence_artifact.example.json"},
        "prediction_context_ref": {"schema_version": prediction_context.get("schema_version"), "task_id": prediction_context.get("task_id"), "template_path": "templates/prediction_context_artifact.example.json"},
        "explainability_ref": {"schema_version": explainability.get("schema_version"), "task_id": explainability.get("task_id"), "template_path": "templates/unified_explainability_artifact.example.json"},
        "report_assembly_ref": {"schema_version": report_assembly.get("schema_version"), "task_id": report_assembly.get("task_id"), "template_path": "templates/context_based_report_assembly_artifact.example.json"},
        "dashboard_page_model": _dashboard_page_model(),
        "summary_cards": _summary_cards(prediction_context, report_assembly, explainability),
        "source_credibility_cards": _source_credibility_cards(prediction_context),
        "factor_rationale_cards": _factor_rationale_cards(explainability),
        "evidence_trace_cards": _evidence_trace_cards(explainability, report_assembly),
        "formal_integration_cards": _formal_integration_cards(report_assembly),
        "market_regime_cards": [{"card_id": "market_regime_detail_card", "context": prediction_context.get("market_regime_context"), "direct_rating_action_confidence_impact": False, "deterministic": True}],
        "rolling_evaluation_cards": [{"card_id": "rolling_evaluation_detail_card", "context": prediction_context.get("rolling_evaluation_context"), "direct_rating_action_confidence_impact": False, "deterministic": True}],
        "warning_cards": _warning_cards(report_assembly),
        "exclusion_cards": _exclusion_cards(report_assembly),
        "metadata_only_badges": _metadata_only_badges(),
        "advisory_only_badges": _advisory_only_badges(),
        "drilldown_links": _drilldown_links(str(symbol)),
        "ui_contract_notes": [
            "Artifact only; not a Dashboard UI implementation.",
            "Renderer may consume cards and placeholder drilldown links in a later gated task.",
            "Do not publish dashboard from this artifact builder or validator.",
        ],
        "safety_policy": safety_policy(),
        "publish_policy": publish_policy(),
    }
