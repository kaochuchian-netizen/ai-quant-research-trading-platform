"""Build deterministic Official Primary Source Context Admission artifacts."""
from __future__ import annotations
from typing import Any

from .schemas import (
    ARTIFACT_TYPE,
    EXISTING_SOURCE_POLICIES,
    INTEGRATION_TARGETS,
    SCHEMA_VERSION,
    SOURCE_FAMILIES,
    TASK_ID,
    mutation_policy,
    safety_policy,
)

FAMILY_META: dict[str, dict[str, Any]] = {
    "mops_public_information_observatory": {
        "source_name": "MOPS Public Information Observatory",
        "source_type": "official_disclosure",
        "provider": "TWSE/MOPS",
        "credibility_level": "official_primary_source",
        "source_priority": 1,
        "official_primary_source": True,
        "official_financial_source": False,
        "official_ir_source": False,
        "industry_context_source": False,
        "peer_context_source": False,
    },
    "company_announcements": {
        "source_name": "Company official announcements",
        "source_type": "company_official_disclosure",
        "provider": "listed_company",
        "credibility_level": "official_primary_source",
        "source_priority": 1,
        "official_primary_source": True,
        "official_financial_source": False,
        "official_ir_source": False,
        "industry_context_source": False,
        "peer_context_source": False,
    },
    "financial_statements": {
        "source_name": "Financial statements",
        "source_type": "official_financial_report",
        "provider": "listed_company_or_mops",
        "credibility_level": "official_financial_source",
        "source_priority": 1,
        "official_primary_source": True,
        "official_financial_source": True,
        "official_ir_source": False,
        "industry_context_source": False,
        "peer_context_source": False,
    },
    "monthly_revenue": {
        "source_name": "Monthly revenue",
        "source_type": "official_financial_metric",
        "provider": "listed_company_or_mops",
        "credibility_level": "official_financial_source",
        "source_priority": 1,
        "official_primary_source": True,
        "official_financial_source": True,
        "official_ir_source": False,
        "industry_context_source": False,
        "peer_context_source": False,
    },
    "investor_conference": {
        "source_name": "Investor conference materials",
        "source_type": "official_ir_event",
        "provider": "listed_company",
        "credibility_level": "official_ir_source",
        "source_priority": 2,
        "official_primary_source": True,
        "official_financial_source": False,
        "official_ir_source": True,
        "industry_context_source": False,
        "peer_context_source": False,
    },
    "company_ir_materials": {
        "source_name": "Company IR materials",
        "source_type": "official_ir_material",
        "provider": "listed_company",
        "credibility_level": "official_ir_source",
        "source_priority": 2,
        "official_primary_source": True,
        "official_financial_source": False,
        "official_ir_source": True,
        "industry_context_source": False,
        "peer_context_source": False,
    },
    "industry_supply_chain": {
        "source_name": "Industry supply chain context",
        "source_type": "industry_context",
        "provider": "industry_sources",
        "credibility_level": "industry_context_source",
        "source_priority": 3,
        "official_primary_source": False,
        "official_financial_source": False,
        "official_ir_source": False,
        "industry_context_source": True,
        "peer_context_source": False,
    },
    "peer_company_context": {
        "source_name": "Peer company context",
        "source_type": "peer_context",
        "provider": "peer_companies",
        "credibility_level": "peer_context_source",
        "source_priority": 3,
        "official_primary_source": False,
        "official_financial_source": False,
        "official_ir_source": False,
        "industry_context_source": False,
        "peer_context_source": True,
    },
}


def _source_family(family: str) -> dict[str, Any]:
    meta = FAMILY_META[family]
    official = bool(meta["official_primary_source"] or meta["official_financial_source"] or meta["official_ir_source"])
    return {
        "source_id": family,
        "source_family": family,
        "credential_required": False,
        "external_api_required": False,
        "production_connector_exists": False,
        "deterministic_sample_available": True,
        "freshness_policy": "deterministic_policy_only_no_runtime_fetch",
        "failure_mode": "runtime_connector_not_configured_in_ai_dev_141",
        "allowed_usage": "Admit as context/evidence according to admission matrix after future connector validation.",
        "disallowed_usage": "No production mutation, no direct rating/action/confidence impact, no runtime crawling in AI-DEV-141.",
        "official_source_replacement_allowed": False,
        "direct_rating_action_confidence_impact": False,
        **meta,
        "core_forecast_evidence_eligible": official,
    }


def _admission_matrix(families: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in families:
        core = bool(item.get("official_primary_source") or item.get("official_financial_source") or item.get("official_ir_source"))
        rows.append({
            "source_id": item["source_id"],
            "source_family": item["source_family"],
            "prediction_context_allowed": True,
            "explainability_evidence_allowed": core,
            "report_assembly_allowed": True,
            "dashboard_drilldown_allowed": True,
            "decision_feedback_allowed": True,
            "production_decision_mutation_allowed": False,
            "core_forecast_evidence_allowed": core,
            "direct_rating_action_confidence_impact": False,
        })
    return rows


def _source_priority_policy() -> dict[str, Any]:
    return {
        "mops_and_company_announcements": "official_primary_source",
        "financial_statements_and_monthly_revenue": "official_financial_source",
        "investor_conference_and_company_ir_materials": "official_ir_source",
        "industry_supply_chain": "industry_context_source",
        "peer_company_context": "peer_context_source",
        "finmind": "normalized_external_data_provider_assist_only_not_replacement",
        "twse": "official_market_chip_source",
        "yfinance_yahoo": "external_reference_proxy_not_official",
        "google_news_rss": "event_sentiment_support_only_not_core_forecast_evidence",
        "broker_target_analyst_opinion": "metadata_only_no_rating_action_confidence_impact",
    }


def _official_replacement_policy() -> dict[str, Any]:
    return {
        "official_source_replacement_allowed": False,
        "finmind_can_replace_official_source": False,
        "yfinance_can_replace_official_source": False,
        "google_news_can_be_core_forecast_evidence": False,
        "broker_target_can_affect_rating_action_confidence": False,
        "gemini_ai_generated_analysis_is_original_evidence": False,
    }


def _integration_targets() -> list[dict[str, Any]]:
    return [
        {
            "task_id": task_id,
            "schema_version": schema,
            "integration_role": "context_admission_target",
            "production_mutation_allowed": False,
        }
        for task_id, schema in INTEGRATION_TARGETS
    ]


def build_official_primary_source_context_admission_artifact(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    families = [_source_family(family) for family in SOURCE_FAMILIES]
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "artifact_type": ARTIFACT_TYPE,
        "generated_at": payload.get("generated_at", "2026-07-05T00:00:00Z"),
        "source_families": families,
        "admission_matrix": _admission_matrix(families),
        "source_priority_policy": _source_priority_policy(),
        "official_source_replacement_policy": _official_replacement_policy(),
        "relationship_to_existing_sources": EXISTING_SOURCE_POLICIES,
        "integration_targets": _integration_targets(),
        "warnings": [
            "AI-DEV-141 is not a production crawler and does not call MOPS, company websites, or external APIs.",
            "FinMind may assist normalization but cannot replace official sources.",
            "Broker target price / analyst opinion remains metadata only and cannot affect rating/action/confidence.",
            "Gemini / AI-generated analysis is not original evidence.",
        ],
        "safety_policy": safety_policy(),
        "mutation_policy": mutation_policy(),
    }
