"""Build deterministic Decision Quality Feedback artifacts."""
from __future__ import annotations
from typing import Any

from .schemas import (
    ARTIFACT_TYPE,
    DASHBOARD_FEEDBACK_BLOCK_IDS,
    REPORT_FEEDBACK_BLOCK_IDS,
    SCHEMA_VERSION,
    TASK_ID,
    WARNING_SOURCE_IDS,
    mutation_policy,
    safety_policy,
)


def _ref(payload: dict[str, Any], template_path: str) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "task_id": payload.get("task_id"),
        "template_path": template_path,
    }


def _rolling_evaluation(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "evaluation_window": sample.get("evaluation_window", "last_7_sessions"),
        "sample_count": sample.get("sample_count", 0),
        "direction_hit_rate": sample.get("direction_hit_rate"),
        "high_range_hit_rate": sample.get("high_range_hit_rate"),
        "low_range_hit_rate": sample.get("low_range_hit_rate"),
        "bias_summary": sample.get("bias_summary", "Deterministic sample only."),
        "insufficient_data_flag": sample.get("insufficient_data_flag", True),
    }


def _prediction_review(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "reviewed_predictions": sample.get("reviewed_predictions", 0),
        "pending_predictions": sample.get("pending_predictions", 0),
        "insufficient_actuals": sample.get("insufficient_actuals", 0),
        "major_error_cases": sample.get("major_error_cases", []),
        "review_quality_flag": sample.get("review_quality_flag", "sample_only"),
    }


def _factor_effectiveness(sample_rows: list[dict[str, Any]], explainability: dict[str, Any]) -> list[dict[str, Any]]:
    sample_by_id = {row.get("factor_id"): row for row in sample_rows}
    rows: list[dict[str, Any]] = []
    for item in explainability.get("factor_explanations", []):
        factor_id = item.get("factor_id") or item.get("id") or "unknown_factor"
        sample = sample_by_id.get(factor_id, {})
        rows.append({
            "factor_id": factor_id,
            "factor_name": item.get("factor_name") or item.get("name") or factor_id,
            "factor_category": item.get("factor_category") or item.get("category") or "context",
            "recent_effectiveness": sample.get("recent_effectiveness", "sample_observe"),
            "evidence_support": sample.get("evidence_support", item.get("supporting_sources", item.get("source_ids", []))),
            "confidence_support": sample.get("confidence_support", "neutral"),
            "warning_flag": sample.get("warning_flag", False),
            "recommended_action": sample.get("recommended_action", "review_only_no_weight_change"),
            "production_weight_changed": False,
        })
    return sorted(rows, key=lambda row: row["factor_id"])


def _confidence_calibration(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "calibration_window": sample.get("calibration_window", "last_7_sessions"),
        "overconfidence_flag": sample.get("overconfidence_flag", False),
        "underconfidence_flag": sample.get("underconfidence_flag", False),
        "confidence_bias": sample.get("confidence_bias", "sample_neutral"),
        "recommended_confidence_note": sample.get("recommended_confidence_note", "Human review only; do not mutate confidence."),
        "production_confidence_changed": False,
    }


def _market_regime_quality(sample: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    regime_context = context.get("market_regime_context") or {}
    return {
        "regime": sample.get("regime", regime_context.get("regime_label", "sample_regime")),
        "regime_confidence": sample.get("regime_confidence", regime_context.get("regime_confidence", "sample_only")),
        "regime_specific_performance_note": sample.get("regime_specific_performance_note", "Regime-specific feedback is deterministic sample only."),
        "regime_caution": sample.get("regime_caution", "Use as report note only."),
        "recommended_report_note": sample.get("recommended_report_note", "Add regime caution to future report display."),
    }


def _source_error_attribution(context: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    source_rows: list[dict[str, Any]] = []
    for category, sources in (context.get("source_summary") or {}).items():
        for source in sources:
            source_rows.append({
                "source_id": source.get("source_id"),
                "provider": source.get("provider"),
                "source_type": category,
                "credibility_level": source.get("credibility_level", category),
                "allowed_usage": source.get("allowed_usage", "Context and attribution only."),
                "disallowed_usage": source.get("disallowed_usage", "No direct production mutation."),
                "possible_error_contribution": "sample_attribution_only",
                "attribution_confidence": "low_sample_only",
                "recommendation_only": True,
            })
    known = {row["source_id"] for row in source_rows}
    for warning in report.get("warning_section", {}).get("warnings", []):
        sid = warning.get("source_id")
        if sid and sid not in known:
            source_rows.append({
                "source_id": sid,
                "provider": warning.get("provider", sid),
                "source_type": warning.get("warning_type", "warning_source"),
                "credibility_level": "warning_only",
                "allowed_usage": "Warning display and human review only.",
                "disallowed_usage": "No direct production mutation.",
                "possible_error_contribution": warning.get("warning_summary", "sample_warning_attribution"),
                "attribution_confidence": "low_sample_only",
                "recommendation_only": True,
            })
    return sorted(source_rows, key=lambda row: str(row.get("source_id")))


def _factor_feedback_blocks(factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "block_id": f"{row['factor_id']}_feedback",
            "factor_id": row["factor_id"],
            "feedback_summary": f"{row['factor_name']} recent effectiveness: {row['recent_effectiveness']}",
            "recommended_action": row["recommended_action"],
            "production_weight_changed": False,
            "recommendation_only": True,
        }
        for row in factors
    ]


def _confidence_feedback_blocks(confidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "block_id": "confidence_calibration_feedback",
        "confidence_bias": confidence["confidence_bias"],
        "overconfidence_flag": confidence["overconfidence_flag"],
        "underconfidence_flag": confidence["underconfidence_flag"],
        "recommended_confidence_note": confidence["recommended_confidence_note"],
        "production_confidence_changed": False,
        "recommendation_only": True,
    }]


def _regime_feedback_blocks(regime: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "block_id": "market_regime_quality_feedback",
        "regime": regime["regime"],
        "regime_caution": regime["regime_caution"],
        "recommended_report_note": regime["recommended_report_note"],
        "recommendation_only": True,
    }]


def _source_reliability_feedback_blocks(attribution: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "block_id": f"{row['source_id']}_source_reliability_feedback",
            "source_id": row["source_id"],
            "possible_error_contribution": row["possible_error_contribution"],
            "attribution_confidence": row["attribution_confidence"],
            "recommendation_only": True,
        }
        for row in attribution
    ]


def _report_feedback_blocks() -> list[dict[str, Any]]:
    payload = {
        "feedback_summary": "Decision quality feedback is available for report review.",
        "factor_effectiveness_note": "Show factor effectiveness notes without changing weights.",
        "confidence_calibration_note": "Show confidence calibration note without changing confidence.",
        "source_reliability_note": "Show source reliability attribution for human review.",
        "market_regime_caution": "Show regime caution in future report display.",
        "human_review_required_note": "All recommendations require human review before production mutation.",
    }
    return [{"block_id": block_id, "text": payload[block_id], "recommendation_only": True} for block_id in payload]


def _dashboard_feedback_blocks() -> list[dict[str, Any]]:
    payload = {
        "feedback_summary_card": "Decision quality feedback summary.",
        "factor_quality_card": "Factor quality review card.",
        "confidence_bias_card": "Confidence bias review card.",
        "source_error_attribution_card": "Source error attribution card.",
        "regime_quality_card": "Market regime quality card.",
        "recommendation_card": "Human-gated recommendation card.",
    }
    return [{"card_id": card_id, "text": payload[card_id], "recommendation_only": True} for card_id in payload]


def _recommendations(factors: list[dict[str, Any]], confidence: dict[str, Any], regime: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "recommendation_id": "review_factor_effectiveness_notes",
            "recommendation_type": "factor_review",
            "target": "factor_effectiveness_summary",
            "rationale": "Recent factor effectiveness should be displayed for human review.",
            "priority": "medium",
            "evidence_refs": [row["factor_id"] for row in factors[:3]],
            "requires_human_review": True,
            "production_mutation_allowed": False,
            "production_mutation_executed": False,
        },
        {
            "recommendation_id": "review_confidence_calibration_note",
            "recommendation_type": "confidence_review",
            "target": "confidence_calibration_summary",
            "rationale": confidence["recommended_confidence_note"],
            "priority": "medium",
            "evidence_refs": ["confidence_calibration_summary"],
            "requires_human_review": True,
            "production_mutation_allowed": False,
            "production_mutation_executed": False,
        },
        {
            "recommendation_id": "show_market_regime_caution",
            "recommendation_type": "regime_report_note",
            "target": "market_regime_quality_summary",
            "rationale": regime["recommended_report_note"],
            "priority": "low",
            "evidence_refs": ["market_regime_quality_summary"],
            "requires_human_review": True,
            "production_mutation_allowed": False,
            "production_mutation_executed": False,
        },
    ]
    return rows


def _warning_blocks(report: dict[str, Any]) -> list[dict[str, Any]]:
    exclusions = report.get("exclusion_section", {}).get("exclusion_reasons", {})
    rows = [
        {
            "warning_id": source_id,
            "source_id": source_id,
            "warning_summary": exclusions.get(source_id, "Policy warning applies."),
            "recommendation_only": True,
            "direct_rating_action_confidence_impact": False,
        }
        for source_id in WARNING_SOURCE_IDS
        if source_id != "recommendation_policy"
    ]
    rows.append({
        "warning_id": "recommendation_policy",
        "source_id": "recommendation_policy",
        "warning_summary": "recommendation cannot automatically change production rating/action/confidence/weight.",
        "recommendation_only": True,
        "direct_rating_action_confidence_impact": False,
    })
    return rows


def build_decision_quality_feedback_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    context = payload["prediction_context"]
    explainability = payload["unified_explainability"]
    report = payload["context_based_report_assembly"]
    dashboard = payload["dashboard_decision_intelligence"]
    rolling = _rolling_evaluation(payload.get("rolling_evaluation_sample", {}))
    review = _prediction_review(payload.get("prediction_review_sample", {}))
    factors = _factor_effectiveness(payload.get("factor_effectiveness_sample", []), explainability)
    confidence = _confidence_calibration(payload.get("confidence_calibration_sample", {}))
    regime = _market_regime_quality(payload.get("market_regime_quality_sample", {}), context)
    attribution = _source_error_attribution(context, report)
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "artifact_type": ARTIFACT_TYPE,
        "generated_at": context.get("generated_at"),
        "symbol": context.get("symbol"),
        "market": context.get("market"),
        "feedback_window": payload.get("feedback_window", "last_7_sessions_sample"),
        "prediction_context_ref": _ref(context, "templates/prediction_context_artifact.example.json"),
        "explainability_ref": _ref(explainability, "templates/unified_explainability_artifact.example.json"),
        "report_assembly_ref": _ref(report, "templates/context_based_report_assembly_artifact.example.json"),
        "dashboard_intelligence_ref": _ref(dashboard, "templates/dashboard_decision_intelligence_artifact.example.json"),
        "rolling_evaluation_summary": rolling,
        "prediction_review_summary": review,
        "factor_effectiveness_summary": factors,
        "confidence_calibration_summary": confidence,
        "market_regime_quality_summary": regime,
        "source_error_attribution": attribution,
        "factor_feedback_blocks": _factor_feedback_blocks(factors),
        "confidence_feedback_blocks": _confidence_feedback_blocks(confidence),
        "regime_feedback_blocks": _regime_feedback_blocks(regime),
        "source_reliability_feedback_blocks": _source_reliability_feedback_blocks(attribution),
        "report_feedback_blocks": _report_feedback_blocks(),
        "dashboard_feedback_blocks": _dashboard_feedback_blocks(),
        "recommendation_blocks": _recommendations(factors, confidence, regime),
        "warning_blocks": _warning_blocks(report),
        "mutation_policy": mutation_policy(),
        "safety_policy": safety_policy(),
    }
