"""Schemas and constants for Prediction Context V1."""
from __future__ import annotations

SCHEMA_VERSION = "prediction_context_v1"
TASK_ID = "AI-DEV-136"
ARTIFACT_TYPE = "unified_decision_context_v1"

REQUIRED_CONTEXT_FIELDS = [
    "schema_version",
    "task_id",
    "generated_at",
    "symbol",
    "market",
    "context_window",
    "source_summary",
    "source_credibility_summary",
    "formal_report_integrations",
    "technical_context",
    "chip_context",
    "adr_context",
    "news_context",
    "finmind_context",
    "twse_context",
    "yfinance_context",
    "historical_context",
    "rolling_evaluation_context",
    "market_regime_context",
    "confidence_calibration_context",
    "factor_effectiveness_context",
    "explainability_context",
    "warnings",
    "exclusions",
    "safety_policy",
]

SOURCE_SUMMARY_CATEGORIES = [
    "official_primary_source",
    "official_market_source",
    "normalized_external_data_provider",
    "external_reference_proxy",
    "ai_generated_analysis",
    "low_priority_metadata",
]

CREDIBILITY_REQUIRED_FIELDS = [
    "source_id",
    "provider",
    "source_priority",
    "credibility_level",
    "decision_value",
    "report_allowed",
    "prediction_context_allowed",
    "direct_rating_action_confidence_impact",
]

FORMAL_REPORT_INTEGRATION_IDS = [
    "finmind_report_integration_artifact",
    "twse_report_integration_artifact",
    "yfinance_yahoo_report_integration_artifact",
]

SAFETY_FALSE_FLAGS = [
    "external_api_called",
    "secrets_read",
    "production_db_read",
    "production_db_write",
    "scheduler_modified",
    "line_email_sent",
    "dashboard_published",
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
        "context_artifact_only": True,
        "not_production_decision_engine": True,
        "no_direct_rating_action_confidence_change": True,
    }
    policy.update({key: False for key in SAFETY_FALSE_FLAGS})
    return policy
