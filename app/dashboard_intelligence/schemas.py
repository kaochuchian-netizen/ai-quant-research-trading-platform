"""Schemas/constants for Dashboard Decision Intelligence V1."""
from __future__ import annotations

SCHEMA_VERSION = "dashboard_decision_intelligence_v1"
TASK_ID = "AI-DEV-139"
ARTIFACT_TYPE = "dashboard_decision_intelligence_drilldown_foundation_v1"

DASHBOARD_PAGE_IDS = [
    "overview",
    "source_credibility",
    "factor_rationale",
    "evidence_trace",
    "formal_integrations",
    "market_regime",
    "rolling_evaluation",
    "warnings",
    "advisory_policy",
]

SUMMARY_CARD_IDS = [
    "symbol_summary_card",
    "report_window_summary_card",
    "market_regime_summary_card",
    "confidence_rationale_summary_card",
    "advisory_only_summary_card",
]

SOURCE_CATEGORIES = [
    "official_primary_source",
    "official_market_source",
    "normalized_external_data_provider",
    "external_reference_proxy",
    "ai_generated_analysis",
    "low_priority_metadata",
]

FORMAL_INTEGRATION_IDS = [
    "finmind_report_integration",
    "twse_report_integration",
    "yfinance_yahoo_report_integration",
]

METADATA_ONLY_BADGE_IDS = [
    "broker_target_analyst_opinion_metadata_only",
    "google_news_rss_support_only",
    "gemini_generated_analysis_only",
]

ADVISORY_ONLY_BADGE_IDS = [
    "advisory_only",
    "not_trading_advice",
    "no_order_execution",
    "no_direct_rating_action_confidence_mutation",
]

REQUIRED_FIELDS = [
    "schema_version",
    "task_id",
    "generated_at",
    "symbol",
    "market",
    "dashboard_context_ref",
    "prediction_context_ref",
    "explainability_ref",
    "report_assembly_ref",
    "dashboard_page_model",
    "summary_cards",
    "source_credibility_cards",
    "factor_rationale_cards",
    "evidence_trace_cards",
    "formal_integration_cards",
    "market_regime_cards",
    "rolling_evaluation_cards",
    "warning_cards",
    "exclusion_cards",
    "metadata_only_badges",
    "advisory_only_badges",
    "drilldown_links",
    "ui_contract_notes",
    "safety_policy",
    "publish_policy",
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
    "dashboard_runtime_modified",
    "broker_order_trading",
    "production_pipeline_run",
    "python_main_executed",
    "production_rating_action_confidence_weight_mutation",
    "formal_delivery_behavior_modified",
    "production_runtime_modified",
    "direct_rating_action_confidence_impact",
]


def safety_policy() -> dict[str, object]:
    policy = {
        "read_only": True,
        "offline_sample_only": True,
        "dashboard_drilldown_artifact_only": True,
        "not_dashboard_ui_implementation": True,
        "not_production_dashboard_runtime": True,
        "not_production_decision_engine": True,
        "no_direct_rating_action_confidence_change": True,
    }
    policy.update({key: False for key in SAFETY_FALSE_FLAGS})
    return policy


def publish_policy() -> dict[str, object]:
    return {
        "dashboard_ui_modified": False,
        "dashboard_published": False,
        "dashboard_runtime_modified": False,
        "external_notification_sent": False,
        "delivery_executed": False,
        "production_delivery_behavior_modified": False,
    }
