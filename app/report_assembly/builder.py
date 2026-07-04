"""Build deterministic Context-Based Report Assembly artifacts."""
from __future__ import annotations
from typing import Any
from .schemas import ARTIFACT_TYPE, DASHBOARD_BLOCK_IDS, EMAIL_BLOCK_IDS, LINE_BLOCK_IDS, REPORT_SECTION_IDS, SCHEMA_VERSION, SOURCE_CATEGORIES, TASK_ID, delivery_policy, safety_policy


def _section(section_id: str, title: str, summary: str, source_ids: list[str] | None = None, warning: bool = False) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "title": title,
        "summary": summary,
        "source_ids": source_ids or [],
        "deterministic": True,
        "warning": warning,
        "direct_rating_action_confidence_impact": False,
    }


def _source_category_summary(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_summary = context.get("source_summary", {})
    for category in SOURCE_CATEGORIES:
        sources = source_summary.get(category, [])
        rows.append({
            "category": category,
            "source_ids": [row.get("source_id") for row in sources],
            "providers": [row.get("provider") for row in sources],
            "count": len(sources),
            "direct_rating_action_confidence_impact": False,
        })
    return rows


def _formal_integrations(context: dict[str, Any]) -> list[dict[str, Any]]:
    integrations = context.get("formal_report_integrations", {})
    ordered = [
        ("finmind_report_integration", "FinMind report integration", "finmind_report_integration_artifact"),
        ("twse_report_integration", "TWSE report integration", "twse_report_integration_artifact"),
        ("yfinance_yahoo_report_integration", "yfinance/Yahoo report integration", "yfinance_yahoo_report_integration_artifact"),
    ]
    return [
        {
            "integration_id": integration_id,
            "title": title,
            "source_id": integrations.get(key, {}).get("source_id"),
            "artifact_path": integrations.get(key, {}).get("artifact_path"),
            "report_allowed": integrations.get(key, {}).get("report_allowed"),
            "prediction_context_allowed": integrations.get(key, {}).get("prediction_context_allowed"),
            "direct_rating_action_confidence_impact": False,
        }
        for integration_id, title, key in ordered
    ]


def _warnings(explainability: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in explainability.get("metadata_only_warnings", []):
        rows.append({"warning_type": "metadata_only", **item, "direct_rating_action_confidence_impact": False})
    for item in explainability.get("official_source_replacement_warnings", []):
        rows.append({"warning_type": "official_source_replacement", **item, "direct_rating_action_confidence_impact": False})
    return sorted(rows, key=lambda row: (row.get("warning_type", ""), row.get("source_id", "")))


def _report_sections(context: dict[str, Any], explainability: dict[str, Any]) -> list[dict[str, Any]]:
    exclusions = explainability.get("exclusion_reasons", {})
    trace_count = len(explainability.get("evidence_links", []))
    source_ids = [row.get("source_id") for row in context.get("source_credibility_summary", [])]
    sections = [
        _section("executive_summary", "Executive summary", "Offline sample report-ready context assembled from Prediction Context and Unified Explainability.", source_ids),
        _section("market_regime_summary", "Market regime summary", "Market regime context is included as advisory context only.", []),
        _section("source_credibility_summary", "Source credibility summary", "Sources are grouped by official, normalized external, external proxy, AI-generated, and metadata-only roles.", source_ids),
        _section("technical_context_summary", "Technical context summary", "Technical context is sample-ready and has no direct production decision impact.", []),
        _section("chip_context_summary", "Chip context summary", "TWSE chip context is official market/chip attribution but does not mutate rating/action/confidence.", ["twse_openapi"]),
        _section("adr_context_summary", "ADR context summary", "ADR and US ETF proxy context is external reference only.", ["yfinance_yahoo"]),
        _section("finmind_summary", "FinMind summary", "FinMind is normalized external report supplement and cannot replace official sources.", ["finmind"]),
        _section("twse_summary", "TWSE summary", "TWSE is official market/chip source for formal report context.", ["twse_openapi"]),
        _section("yfinance_summary", "yfinance/Yahoo summary", "yfinance/Yahoo supports ADR, US index, ETF, and sector proxy context only.", ["yfinance_yahoo"]),
        _section("rolling_evaluation_summary", "Rolling evaluation summary", "Rolling evaluation context is included for future decision quality review.", []),
        _section("confidence_rationale_summary", "Confidence rationale summary", explainability.get("confidence_rationale", {}).get("summary", "Confidence rationale unavailable."), []),
        _section("evidence_trace_summary", "Evidence trace summary", f"Evidence trace links available: {trace_count}.", []),
        _section("metadata_only_warning", "Metadata-only warning", "; ".join([exclusions.get("broker_target_price_metadata", ""), exclusions.get("google_news_rss", "")]).strip("; "), ["broker_target_price_metadata", "google_news_rss"], True),
        _section("official_source_replacement_warning", "Official-source replacement warning", "; ".join([exclusions.get("yfinance_yahoo", ""), exclusions.get("finmind", ""), exclusions.get("gemini_google_generative_ai", "")]).strip("; "), ["yfinance_yahoo", "finmind", "gemini_google_generative_ai"], True),
        _section("advisory_only_disclaimer", "Advisory-only disclaimer", "This report assembly artifact is advisory-only and does not execute delivery or production decisions.", [], True),
    ]
    return sections


def _dashboard_blocks(report_sections: list[dict[str, Any]], explainability: dict[str, Any]) -> list[dict[str, Any]]:
    payload = {
        "summary_card": {"title": "Report summary", "section_id": "executive_summary"},
        "source_credibility_card": {"title": "Source credibility", "section_id": "source_credibility_summary"},
        "factor_rationale_card": {"title": "Factor rationale", "source_block": "report_factor_rationale_summary"},
        "evidence_trace_card": {"title": "Evidence trace", "trace_node_count": len(explainability.get("evidence_trace_graph", {}).get("nodes", [])), "trace_edge_count": len(explainability.get("evidence_trace_graph", {}).get("edges", []))},
        "warning_card": {"title": "Warnings", "section_ids": ["metadata_only_warning", "official_source_replacement_warning"]},
        "formal_integration_card": {"title": "Formal integrations", "section_id": "formal_report_integration_section"},
    }
    return [{"block_id": block_id, "deterministic": True, **payload[block_id]} for block_id in DASHBOARD_BLOCK_IDS]


def _email_blocks(report_sections: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = {
        "headline": {"text": "Context-based report assembly dry-run"},
        "summary_paragraph": {"text": "Unified context and evidence trace are assembled into report-ready sections."},
        "detailed_sections": {"section_ids": [section["section_id"] for section in report_sections]},
        "evidence_notes": {"text": "Evidence trace remains deterministic and advisory-only."},
        "warnings": {"items": warnings},
        "advisory_only_disclaimer": {"text": "No delivery executed; no production decision mutation."},
    }
    return [{"block_id": block_id, "deterministic": True, **payload[block_id]} for block_id in EMAIL_BLOCK_IDS]


def _line_blocks() -> list[dict[str, Any]]:
    payload = {
        "short_title": {"text": "AI report context ready"},
        "one_line_summary": {"text": "Offline context-based report assembly artifact is ready for review."},
        "dashboard_link_placeholder": {"text": "DASHBOARD_LINK_PLACEHOLDER"},
        "advisory_only_badge": {"text": "Research-only / no trading instruction"},
    }
    return [{"block_id": block_id, "deterministic": True, **payload[block_id]} for block_id in LINE_BLOCK_IDS]


def build_context_based_report_assembly_artifact(prediction_context: dict[str, Any], explainability: dict[str, Any]) -> dict[str, Any]:
    report_sections = _report_sections(prediction_context, explainability)
    warnings = _warnings(explainability)
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "artifact_type": ARTIFACT_TYPE,
        "generated_at": prediction_context.get("generated_at"),
        "symbol": prediction_context.get("symbol"),
        "market": prediction_context.get("market"),
        "report_window": prediction_context.get("context_window"),
        "context_ref": {"schema_version": prediction_context.get("schema_version"), "task_id": prediction_context.get("task_id"), "template_path": "templates/prediction_context_artifact.example.json"},
        "explainability_ref": {"schema_version": explainability.get("schema_version"), "task_id": explainability.get("task_id"), "template_path": "templates/unified_explainability_artifact.example.json"},
        "report_sections": report_sections,
        "report_summary": {"section_count": len(report_sections), "advisory_only": True, "direct_rating_action_confidence_impact": False},
        "source_credibility_section": {"categories": _source_category_summary(prediction_context), "direct_rating_action_confidence_impact": False},
        "factor_rationale_section": {"factor_explanations": explainability.get("factor_explanations", []), "direct_rating_action_confidence_impact": False},
        "formal_report_integration_section": {"integrations": _formal_integrations(prediction_context), "direct_rating_action_confidence_impact": False},
        "market_regime_section": {"context": prediction_context.get("market_regime_context"), "direct_rating_action_confidence_impact": False},
        "rolling_evaluation_section": {"context": prediction_context.get("rolling_evaluation_context"), "direct_rating_action_confidence_impact": False},
        "warning_section": {"warnings": warnings, "direct_rating_action_confidence_impact": False},
        "exclusion_section": {"exclusion_reasons": explainability.get("exclusion_reasons", {}), "direct_rating_action_confidence_impact": False},
        "evidence_trace_section": {"evidence_links": explainability.get("evidence_links", []), "trace_graph_summary": {"node_count": len(explainability.get("evidence_trace_graph", {}).get("nodes", [])), "edge_count": len(explainability.get("evidence_trace_graph", {}).get("edges", []))}, "direct_rating_action_confidence_impact": False},
        "dashboard_ready_blocks": _dashboard_blocks(report_sections, explainability),
        "email_ready_blocks": _email_blocks(report_sections, warnings),
        "line_summary_blocks": _line_blocks(),
        "safety_policy": safety_policy(),
        "delivery_policy": delivery_policy(),
    }
