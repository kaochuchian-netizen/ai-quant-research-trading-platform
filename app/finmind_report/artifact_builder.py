from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from app.finmind_report.schemas import FinMindReportIntegrationArtifact, FinMindReportSection, SCHEMA_VERSION, SUPPORTED_SECTION_TYPES, safety_summary

SOURCE_ID_BY_SECTION = {
    "monthly_revenue": "finmind_monthly_revenue",
    "financial_statement_summary": "finmind_financial_statement",
    "eps": "finmind_financial_statement",
    "roe": "finmind_financial_statement",
    "margin": "finmind_financial_statement",
    "institutional_trading": "finmind_institutional_investors_buy_sell",
    "dividend": "finmind_dividend",
    "share_capital": "finmind_share_capital",
    "market_cap": "finmind_market_cap",
}
TITLE_BY_SECTION = {
    "monthly_revenue": "FinMind 月營收補充",
    "financial_statement_summary": "FinMind 財報摘要補充",
    "eps": "FinMind EPS 補充",
    "roe": "FinMind ROE 補充",
    "margin": "FinMind Margin 補充",
    "institutional_trading": "FinMind 三大法人補充",
    "dividend": "FinMind 股利補充",
    "share_capital": "FinMind 股本補充",
    "market_cap": "FinMind 市值補充",
}

def _summary(section_type: str, metrics: dict[str, Any]) -> str:
    period = metrics.get("period") or metrics.get("year") or "sample"
    if section_type == "monthly_revenue":
        return f"{period} revenue YoY {metrics.get('revenue_yoy_pct')}%, MoM {metrics.get('revenue_mom_pct')}%."
    if section_type == "institutional_trading":
        return f"{period} institutional trading sample: foreign net {metrics.get('foreign_net_buy_shares')} shares."
    if section_type == "dividend":
        return f"{period} dividend sample: cash {metrics.get('cash_dividend')}, stock {metrics.get('stock_dividend')}."
    return f"{period} normalized FinMind {section_type} sample metrics available."

def build_report_sections(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
    output: list[dict[str, Any]] = []
    for section_type in sorted(SUPPORTED_SECTION_TYPES):
        metrics = sections.get(section_type, {})
        if not isinstance(metrics, dict):
            metrics = {}
        section = FinMindReportSection(
            section_id=f"finmind_{section_type}",
            section_type=section_type,
            title=TITLE_BY_SECTION[section_type],
            summary=_summary(section_type, metrics),
            metrics=metrics,
            source_ids=[SOURCE_ID_BY_SECTION[section_type]],
            freshness_policy="offline sample; future runtime must validate dataset period and staleness before report use",
            explainability_notes=[
                "FinMind is a normalized external data provider.",
                "Use as formal report supplement after deterministic validation.",
                "Must not replace MOPS / TWSE / Shioaji official source governance.",
            ],
            limitations=["sample data only", "not a production runtime fetch", "no direct rating/action/confidence impact"],
        )
        output.append(section.to_dict())
    return output

def build_finmind_report_integration_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    sections = build_report_sections(payload)
    artifact = FinMindReportIntegrationArtifact(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        input_summary={
            "schema_version": payload.get("schema_version"),
            "as_of_date": payload.get("as_of_date"),
            "stock_id": payload.get("stock_id"),
            "stock_name": payload.get("stock_name"),
            "source_kind": payload.get("source_kind", "offline_sample"),
            "sample_mode": payload.get("source_kind", "offline_sample") == "offline_sample",
        },
        source_attribution={
            "provider": "FinMind",
            "source_role": "normalized_external_data_provider",
            "connector_file": "app/sources/finmind_connector.py",
            "api_token_required_for_builder": False,
            "external_api_called": False,
            "official_source_replacement_allowed": False,
            "official_governance_sources": ["MOPS/company official sources", "TWSE", "Shioaji/Sinopac"],
        },
        freshness_policy={
            "builder_mode": "deterministic_offline_sample",
            "runtime_requirement": "validate dataset period, freshness, schema, and source attribution before formal report use",
            "stale_data_action": "mark section stale and keep advisory only",
        },
        report_sections=sections,
        explainability_notes=[
            "FinMind can reduce integration cost for Taiwan fundamental and market datasets.",
            "FinMind report sections must carry source_ids and limitations.",
            "Official source governance wins conflicts with MOPS, TWSE, or Shioaji.",
        ],
        integration_policy={
            "formal_report_candidate": True,
            "prediction_context_candidate": True,
            "daily_report_integration_next_step": "map validated sections into daily report supplemental blocks",
            "prediction_context_next_step": "use only as attributed supplemental context after freshness validation",
            "direct_rating_action_confidence_impact": False,
            "production_weight_mutation_allowed": False,
        },
        safety_summary=safety_summary(),
        advisory_only=True,
    )
    return artifact.to_dict()
