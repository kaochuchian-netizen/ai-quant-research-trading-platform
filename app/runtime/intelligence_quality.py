"""Cross-layer semantic quality, completeness and no-lookahead guardrails."""
from __future__ import annotations

from datetime import datetime
from typing import Any

FAILURE_REASONS = {
    "NO_SOURCE_CONFIGURED", "AUTH_UNAVAILABLE", "TIMEOUT", "UPSTREAM_ERROR",
    "PARSER_ERROR", "SCHEMA_MISMATCH", "NORMALIZATION_FAILED",
    "SYMBOL_MAPPING_FAILED", "STALE", "INSUFFICIENT_LOOKBACK",
    "INVALID_GEOMETRY", "DUPLICATE_DATE", "FUTURE_DATA", "NOT_APPLICABLE",
    "ADMISSION_REJECTED", "NO_MATERIAL_EVENT", "NO_RELIABLE_NEWS",
    "CONSUMER_DISCONNECTED", "UNKNOWN",
}


def completeness_v2(*, market_data: str, technical: str, research: str,
                    decision_input: str, prediction_input: str,
                    research_score: float | None = None,
                    missing_categories: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "intelligence_completeness_v2",
        "market_data_completeness": market_data,
        "technical_evidence_completeness": technical,
        "research_evidence_completeness": research,
        "decision_input_completeness": decision_input,
        "prediction_input_completeness": prediction_input,
        "research_coverage_pct": research_score,
        "missing_research_categories": sorted(set(missing_categories or [])),
        "universal_data_complete": False,
    }


def semantic_degradation(*, quote_total: int = 0, quote_available: int = 0,
                         history_claimed_valid: int = 0, technical_executable: int = 0,
                         provider_market_values: bool = False, research_market_available: bool = False,
                         price_exists: bool = False, research_price_missing: bool = False,
                         prediction_exists: bool = False, evidence_identity: Any = None,
                         completeness: dict[str, Any] | None = None) -> dict[str, Any]:
    reasons = []
    if quote_total and quote_available == quote_total and history_claimed_valid and technical_executable == 0:
        reasons.append("HISTORY_VALID_BUT_TECHNICAL_EMPTY")
    if provider_market_values and not research_market_available:
        reasons.append("PROVIDER_DATA_CONSUMER_DISCONNECTED")
    if price_exists and research_price_missing:
        reasons.append("PRICE_EVIDENCE_CONSUMER_DISCONNECTED")
    if prediction_exists and not evidence_identity:
        reasons.append("PREDICTION_EVIDENCE_IDENTITY_MISSING")
    if completeness and completeness.get("market_data_completeness") == "COMPLETE" and completeness.get("research_evidence_completeness") != "COMPLETE":
        reasons.append("MARKET_COMPLETE_RESEARCH_NOT_COMPLETE")
    return {"status": "DEGRADED" if reasons else "HEALTHY", "reason_codes": reasons}


def _timestamp(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}:MALFORMED_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field}:TIMEZONE_REQUIRED")
    return parsed


def validate_no_lookahead_v2(timeline: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "prediction_generated_at", "prediction_data_cutoff", "last_input_market_timestamp",
        "first_outcome_observation_timestamp", "outcome_data_cutoff", "review_generated_at",
    )
    try:
        values = {field: _timestamp(timeline.get(field), field) for field in fields}
    except ValueError as exc:
        return {"status": "FAIL", "reason_codes": [str(exc)]}
    checks = (
        (values["last_input_market_timestamp"] <= values["prediction_data_cutoff"], "INPUT_AFTER_PREDICTION_CUTOFF"),
        (values["prediction_data_cutoff"] < values["first_outcome_observation_timestamp"], "OUTCOME_NOT_AFTER_PREDICTION"),
        (values["first_outcome_observation_timestamp"] <= values["outcome_data_cutoff"], "OUTCOME_SEQUENCE_INVALID"),
        (values["outcome_data_cutoff"] <= values["review_generated_at"], "REVIEW_BEFORE_OUTCOME_CUTOFF"),
        (values["prediction_data_cutoff"] <= values["prediction_generated_at"], "PREDICTION_GENERATED_BEFORE_CUTOFF"),
    )
    reasons = [reason for valid, reason in checks if not valid]
    return {"status": "FAIL" if reasons else "PASS", "reason_codes": reasons}


def intelligence_health(*, runtime_status: str, data_quality_status: str,
                        research_status: str, prediction_status: str,
                        decision_status: str, degradation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "runtime_intelligence_health_v1",
        "runtime_status": runtime_status,
        "data_quality_status": data_quality_status,
        "research_status": research_status,
        "prediction_status": prediction_status,
        "decision_status": decision_status,
        "intelligence_status": "DEGRADED" if degradation.get("status") == "DEGRADED" else "HEALTHY",
        "reason_codes": degradation.get("reason_codes") or [],
        "runtime_success_is_intelligence_success": False,
    }
