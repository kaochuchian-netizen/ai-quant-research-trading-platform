"""Schemas/constants for Decision Quality Feedback V1."""
from __future__ import annotations

SCHEMA_VERSION = "decision_quality_feedback_v1"
TASK_ID = "AI-DEV-140"
ARTIFACT_TYPE = "decision_quality_feedback_loop_foundation_v1"

REQUIRED_FIELDS = [
    "schema_version",
    "task_id",
    "generated_at",
    "symbol",
    "market",
    "feedback_window",
    "prediction_context_ref",
    "explainability_ref",
    "report_assembly_ref",
    "dashboard_intelligence_ref",
    "rolling_evaluation_summary",
    "prediction_review_summary",
    "factor_effectiveness_summary",
    "confidence_calibration_summary",
    "market_regime_quality_summary",
    "source_error_attribution",
    "factor_feedback_blocks",
    "confidence_feedback_blocks",
    "regime_feedback_blocks",
    "source_reliability_feedback_blocks",
    "report_feedback_blocks",
    "dashboard_feedback_blocks",
    "recommendation_blocks",
    "warning_blocks",
    "mutation_policy",
    "safety_policy",
]

ROLLING_EVALUATION_FIELDS = [
    "evaluation_window",
    "sample_count",
    "direction_hit_rate",
    "high_range_hit_rate",
    "low_range_hit_rate",
    "bias_summary",
    "insufficient_data_flag",
]

PREDICTION_REVIEW_FIELDS = [
    "reviewed_predictions",
    "pending_predictions",
    "insufficient_actuals",
    "major_error_cases",
    "review_quality_flag",
]

FACTOR_EFFECTIVENESS_FIELDS = [
    "factor_id",
    "factor_name",
    "factor_category",
    "recent_effectiveness",
    "evidence_support",
    "confidence_support",
    "warning_flag",
    "recommended_action",
    "production_weight_changed",
]

CONFIDENCE_CALIBRATION_FIELDS = [
    "calibration_window",
    "overconfidence_flag",
    "underconfidence_flag",
    "confidence_bias",
    "recommended_confidence_note",
    "production_confidence_changed",
]

MARKET_REGIME_QUALITY_FIELDS = [
    "regime",
    "regime_confidence",
    "regime_specific_performance_note",
    "regime_caution",
    "recommended_report_note",
]

SOURCE_ERROR_ATTRIBUTION_FIELDS = [
    "source_id",
    "provider",
    "source_type",
    "credibility_level",
    "allowed_usage",
    "disallowed_usage",
    "possible_error_contribution",
    "attribution_confidence",
    "recommendation_only",
]

RECOMMENDATION_FIELDS = [
    "recommendation_id",
    "recommendation_type",
    "target",
    "rationale",
    "priority",
    "evidence_refs",
    "requires_human_review",
    "production_mutation_allowed",
    "production_mutation_executed",
]

REPORT_FEEDBACK_BLOCK_IDS = [
    "feedback_summary",
    "factor_effectiveness_note",
    "confidence_calibration_note",
    "source_reliability_note",
    "market_regime_caution",
    "human_review_required_note",
]

DASHBOARD_FEEDBACK_BLOCK_IDS = [
    "feedback_summary_card",
    "factor_quality_card",
    "confidence_bias_card",
    "source_error_attribution_card",
    "regime_quality_card",
    "recommendation_card",
]

WARNING_SOURCE_IDS = [
    "broker_target_price_metadata",
    "google_news_rss",
    "yfinance_yahoo",
    "finmind",
    "gemini_google_generative_ai",
    "recommendation_policy",
]

MUTATION_FALSE_FLAGS = [
    "production_weight_changed",
    "production_confidence_changed",
    "production_rating_action_changed",
    "production_pipeline_modified",
    "dashboard_runtime_modified",
    "delivery_behavior_modified",
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
    "dashboard_runtime_modified",
    "broker_order_trading",
    "production_pipeline_run",
    "python_main_executed",
    "production_rating_action_confidence_weight_mutation",
    "formal_delivery_behavior_modified",
    "production_runtime_modified",
    "factor_weights_adjusted",
    "confidence_adjusted",
    "rating_action_adjusted",
    "direct_rating_action_confidence_impact",
]


def mutation_policy() -> dict[str, object]:
    policy = {
        "recommendation_only": True,
        "human_review_required_for_any_mutation": True,
        "adaptive_strategy_engine": False,
        "production_mutation_engine": False,
    }
    policy.update({key: False for key in MUTATION_FALSE_FLAGS})
    return policy


def safety_policy() -> dict[str, object]:
    policy = {
        "read_only": True,
        "offline_sample_only": True,
        "feedback_loop_artifact_only": True,
        "recommendation_review_attribution_only": True,
        "not_adaptive_strategy_engine": True,
        "not_production_mutation_engine": True,
        "no_direct_rating_action_confidence_change": True,
    }
    policy.update({key: False for key in SAFETY_FALSE_FLAGS})
    return policy
