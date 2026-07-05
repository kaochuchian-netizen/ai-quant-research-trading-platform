"""Schemas/constants for Official Primary Source Context Admission V1."""
from __future__ import annotations

SCHEMA_VERSION = "official_primary_source_context_admission_v1"
TASK_ID = "AI-DEV-141"
ARTIFACT_TYPE = "official_primary_source_context_admission_foundation_v1"

SOURCE_FAMILIES = [
    "mops_public_information_observatory",
    "company_announcements",
    "financial_statements",
    "monthly_revenue",
    "investor_conference",
    "company_ir_materials",
    "industry_supply_chain",
    "peer_company_context",
]

SOURCE_FAMILY_FIELDS = [
    "source_id",
    "source_name",
    "source_family",
    "source_type",
    "provider",
    "credibility_level",
    "source_priority",
    "official_primary_source",
    "official_financial_source",
    "official_ir_source",
    "industry_context_source",
    "peer_context_source",
    "credential_required",
    "external_api_required",
    "production_connector_exists",
    "deterministic_sample_available",
    "freshness_policy",
    "failure_mode",
    "allowed_usage",
    "disallowed_usage",
    "official_source_replacement_allowed",
    "direct_rating_action_confidence_impact",
]

ADMISSION_FIELDS = [
    "prediction_context_allowed",
    "explainability_evidence_allowed",
    "report_assembly_allowed",
    "dashboard_drilldown_allowed",
    "decision_feedback_allowed",
    "production_decision_mutation_allowed",
    "core_forecast_evidence_allowed",
    "direct_rating_action_confidence_impact",
]

REQUIRED_FIELDS = [
    "schema_version",
    "task_id",
    "generated_at",
    "source_families",
    "admission_matrix",
    "source_priority_policy",
    "official_source_replacement_policy",
    "relationship_to_existing_sources",
    "integration_targets",
    "warnings",
    "safety_policy",
    "mutation_policy",
]

INTEGRATION_TARGETS = [
    ("AI-DEV-136", "prediction_context_v1"),
    ("AI-DEV-137", "unified_explainability_evidence_trace_v1"),
    ("AI-DEV-138", "context_based_report_assembly_v1"),
    ("AI-DEV-139", "dashboard_decision_intelligence_v1"),
    ("AI-DEV-140", "decision_quality_feedback_v1"),
]

EXISTING_SOURCE_POLICIES = {
    "finmind": {
        "role": "normalized_external_data_provider",
        "can_assist_normalization": True,
        "can_replace_official_source": False,
        "core_forecast_evidence_allowed": False,
        "direct_rating_action_confidence_impact": False,
    },
    "twse_openapi": {
        "role": "official_market_chip_source",
        "official_market_source": True,
        "can_replace_company_official_source": False,
        "direct_rating_action_confidence_impact": False,
    },
    "yfinance_yahoo": {
        "role": "external_reference_proxy",
        "can_replace_official_source": False,
        "core_forecast_evidence_allowed": False,
        "direct_rating_action_confidence_impact": False,
    },
    "google_news_rss": {
        "role": "event_sentiment_support_only",
        "core_forecast_evidence_allowed": False,
        "direct_rating_action_confidence_impact": False,
    },
    "broker_target_analyst_opinion": {
        "role": "metadata_only",
        "core_forecast_evidence_allowed": False,
        "direct_rating_action_confidence_impact": False,
    },
    "gemini_google_generative_ai": {
        "role": "ai_generated_analysis_not_original_evidence",
        "original_evidence": False,
        "direct_rating_action_confidence_impact": False,
    },
}

SAFETY_FALSE_FLAGS = [
    "external_api_called",
    "secrets_read",
    "production_db_read",
    "production_db_write",
    "scheduler_modified",
    "line_email_sent",
    "dashboard_published",
    "dashboard_ui_modified",
    "dashboard_runtime_modified",
    "broker_order_trading",
    "production_pipeline_run",
    "python_main_executed",
    "production_connector_modified",
    "production_rating_action_confidence_weight_mutation",
    "formal_delivery_behavior_modified",
    "production_runtime_modified",
    "direct_rating_action_confidence_impact",
]

MUTATION_FALSE_FLAGS = [
    "production_connector_modified",
    "production_decision_mutation_allowed",
    "production_rating_action_changed",
    "production_confidence_changed",
    "production_weight_changed",
    "production_pipeline_modified",
    "delivery_behavior_modified",
    "direct_rating_action_confidence_impact",
]


def safety_policy() -> dict[str, object]:
    policy = {
        "read_only": True,
        "offline_sample_only": True,
        "context_admission_artifact_only": True,
        "not_production_crawler": True,
        "not_runtime_connector": True,
        "no_mops_or_company_api_calls": True,
    }
    policy.update({key: False for key in SAFETY_FALSE_FLAGS})
    return policy


def mutation_policy() -> dict[str, object]:
    policy = {
        "policy_definition_only": True,
        "human_review_required_for_connector_activation": True,
    }
    policy.update({key: False for key in MUTATION_FALSE_FLAGS})
    return policy
