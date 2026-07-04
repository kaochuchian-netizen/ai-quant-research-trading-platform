"""Schemas/constants for Context-Based Report Assembly V1."""
from __future__ import annotations

SCHEMA_VERSION = "context_based_report_assembly_v1"
TASK_ID = "AI-DEV-138"
ARTIFACT_TYPE = "context_based_report_assembly_foundation_v1"

REPORT_SECTION_IDS = [
    "executive_summary",
    "market_regime_summary",
    "source_credibility_summary",
    "technical_context_summary",
    "chip_context_summary",
    "adr_context_summary",
    "finmind_summary",
    "twse_summary",
    "yfinance_summary",
    "rolling_evaluation_summary",
    "confidence_rationale_summary",
    "evidence_trace_summary",
    "metadata_only_warning",
    "official_source_replacement_warning",
    "advisory_only_disclaimer",
]

SOURCE_CATEGORIES = [
    "official_primary_source",
    "official_market_source",
    "normalized_external_data_provider",
    "external_reference_proxy",
    "ai_generated_analysis",
    "low_priority_metadata",
]

DASHBOARD_BLOCK_IDS = [
    "summary_card",
    "source_credibility_card",
    "factor_rationale_card",
    "evidence_trace_card",
    "warning_card",
    "formal_integration_card",
]

EMAIL_BLOCK_IDS = [
    "headline",
    "summary_paragraph",
    "detailed_sections",
    "evidence_notes",
    "warnings",
    "advisory_only_disclaimer",
]

LINE_BLOCK_IDS = [
    "short_title",
    "one_line_summary",
    "dashboard_link_placeholder",
    "advisory_only_badge",
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
    "production_runtime_modified",
]

REQUIRED_FIELDS = [
    "schema_version",
    "task_id",
    "generated_at",
    "symbol",
    "market",
    "report_window",
    "context_ref",
    "explainability_ref",
    "report_sections",
    "report_summary",
    "source_credibility_section",
    "factor_rationale_section",
    "formal_report_integration_section",
    "market_regime_section",
    "rolling_evaluation_section",
    "warning_section",
    "exclusion_section",
    "evidence_trace_section",
    "dashboard_ready_blocks",
    "email_ready_blocks",
    "line_summary_blocks",
    "safety_policy",
    "delivery_policy",
]


def safety_policy() -> dict[str, object]:
    policy = {
        "read_only": True,
        "offline_sample_only": True,
        "report_assembly_artifact_only": True,
        "not_production_renderer": True,
        "not_production_decision_engine": True,
        "no_direct_rating_action_confidence_change": True,
    }
    policy.update({key: False for key in SAFETY_FALSE_FLAGS})
    return policy


def delivery_policy() -> dict[str, object]:
    return {
        "line_allowed_for_summary_only": True,
        "email_allowed_for_full_report": True,
        "dashboard_allowed_for_full_report_and_drilldown": True,
        "delivery_executed": False,
        "dashboard_published": False,
        "external_notification_sent": False,
        "production_delivery_behavior_modified": False,
    }
