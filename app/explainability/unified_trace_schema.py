"""Schemas/constants for Unified Explainability & Evidence Trace V1."""
from __future__ import annotations

SCHEMA_VERSION = "unified_explainability_evidence_trace_v1"
TASK_ID = "AI-DEV-137"
ARTIFACT_TYPE = "unified_explainability_evidence_trace_foundation_v1"

SOURCE_CATEGORIES = [
    "official_primary_source",
    "official_market_source",
    "normalized_external_data_provider",
    "external_reference_proxy",
    "ai_generated_analysis",
    "low_priority_metadata",
]

REQUIRED_FIELDS = [
    "schema_version",
    "task_id",
    "generated_at",
    "symbol",
    "market",
    "context_ref",
    "source_explanations",
    "factor_explanations",
    "evidence_links",
    "evidence_trace_graph",
    "exclusion_reasons",
    "confidence_rationale",
    "metadata_only_warnings",
    "official_source_replacement_warnings",
    "report_explanation_blocks",
    "dashboard_explanation_blocks",
    "safety_policy",
    "warnings",
]

TRACE_REQUIRED_FIELDS = [
    "source_id",
    "provider",
    "source_type",
    "credibility_level",
    "context_section",
    "factor_id",
    "factor_name",
    "explanation_id",
    "explanation_summary",
    "report_block_id",
    "dashboard_block_id",
    "allowed_usage",
    "disallowed_usage",
    "direct_rating_action_confidence_impact",
]

SAFETY_FALSE_FLAGS = [
    "external_api_called",
    "secrets_read",
    "production_db_read",
    "production_db_write",
    "scheduler_modified",
    "line_email_sent",
    "dashboard_published",
    "dashboard_ui_modified",
    "broker_order_trading",
    "production_pipeline_run",
    "python_main_executed",
    "production_rating_action_confidence_weight_mutation",
    "formal_delivery_behavior_modified",
]


def safety_policy() -> dict[str, object]:
    policy = {
        "read_only": True,
        "offline_sample_only": True,
        "explainability_artifact_only": True,
        "not_production_decision_engine": True,
        "no_direct_rating_action_confidence_change": True,
    }
    policy.update({key: False for key in SAFETY_FALSE_FLAGS})
    return policy
