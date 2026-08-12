"""Cross-market intelligence readiness and semantic quality guardrails.

This module describes whether intelligence inputs are ready.  It never owns
trade actions, eligibility, ranking, or execution.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

READINESS_SCHEMA_VERSION = "intelligence_readiness_v2"
READINESS_METHOD_VERSION = "per_dimension_applicability_policy_v2"

FAILURE_REASONS = {
    "NO_SOURCE_CONFIGURED", "AUTH_UNAVAILABLE", "TIMEOUT", "UPSTREAM_ERROR",
    "PARSER_ERROR", "SCHEMA_MISMATCH", "NORMALIZATION_FAILED",
    "SYMBOL_MAPPING_FAILED", "STALE", "INSUFFICIENT_LOOKBACK",
    "INVALID_GEOMETRY", "DUPLICATE_DATE", "FUTURE_DATA", "NOT_APPLICABLE",
    "ADMISSION_REJECTED", "NO_MATERIAL_EVENT", "NO_RELIABLE_NEWS",
    "CONSUMER_DISCONNECTED", "UNKNOWN",
}


def coverage_dimension(
    ready_symbols: int, total_applicable_symbols: int, *,
    reason_codes: Iterable[str] = (), method: str = READINESS_METHOD_VERSION,
    none_status: str = "NONE", complete_status: str = "COMPLETE",
    zero_status: str = "NOT_APPLICABLE",
) -> dict[str, Any]:
    """Return denominator-preserving universe coverage without any()-promotion."""
    ready = max(0, int(ready_symbols))
    total = max(0, int(total_applicable_symbols))
    if ready > total:
        raise ValueError("ready_symbols cannot exceed total_applicable_symbols")
    if zero_status not in {"NOT_APPLICABLE", "NOT_EVALUATED"}:
        raise ValueError("zero_status must be NOT_APPLICABLE or NOT_EVALUATED")
    status = zero_status if total == 0 else complete_status if ready == total else none_status if ready == 0 else "PARTIAL"
    return {
        "status": status,
        "ready_symbols": ready,
        "total_applicable_symbols": total,
        "coverage_ratio": None if total == 0 else round(ready / total, 4),
        "reason_codes": sorted(set(str(x) for x in reason_codes if x)),
        "method": method, "version": READINESS_SCHEMA_VERSION,
        "provenance": "canonical_symbol_readiness_aggregation",
        "applicability": "OUT_OF_SCOPE" if total == 0 else "APPLICABLE",
    }


def decision_input_readiness(required_inputs_by_symbol: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive health readiness from declared Decision inputs; does not change policy."""
    applicable = [row for row in required_inputs_by_symbol if row.get("applicable", True)]
    ready = 0
    missing: set[str] = set()
    for row in applicable:
        required = row.get("required_inputs") if isinstance(row.get("required_inputs"), dict) else {}
        if required and all(bool(value) for value in required.values()):
            ready += 1
        else:
            missing.update(str(key) for key, value in required.items() if not value)
    dimension = coverage_dimension(
        ready, len(applicable), reason_codes=[f"MISSING_{name.upper()}" for name in sorted(missing)],
        none_status="INSUFFICIENT", complete_status="SUFFICIENT",
        method="declared_decision_required_inputs_v1",
        zero_status="NOT_EVALUATED",
    )
    if dimension["status"] == "PARTIAL":
        dimension["readiness"] = "PARTIAL"
    elif dimension["status"] == "SUFFICIENT":
        dimension["readiness"] = "SUFFICIENT"
    elif dimension["status"] in {"NOT_APPLICABLE", "NOT_EVALUATED"}:
        dimension["readiness"] = "NOT_EVALUATED"
    else:
        dimension["readiness"] = "INSUFFICIENT"
    dimension["ownership"] = "health_semantics_only_decision_layer_unchanged"
    contracts = sorted({
        str((row.get("contract") or {}).get("contract_id"))
        for row in applicable if isinstance(row.get("contract"), dict) and (row.get("contract") or {}).get("contract_id")
    })
    dimension["required_input_contract_ids"] = contracts
    dimension["required_input_contract_provenance"] = "decision_layer_export" if contracts else "legacy_or_not_evaluated"
    return dimension


def intelligence_readiness_v1(
    *, runtime_status: str, total_symbols: int, market_ready: int,
    history_ready: int, technical_ready: int, research_ready: int,
    baseline_prediction_ready: int, full_prediction_ready: int,
    decision_required_inputs: list[dict[str, Any]], outcome_evaluable: int = 0,
    reasons: dict[str, Iterable[str]] | None = None,
    applicability: dict[str, int] | None = None,
    zero_statuses: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build canonical readiness dimensions with explicit counts and methods."""
    reasons = reasons or {}
    applicability = applicability or {}
    zero_statuses = zero_statuses or {}
    total = max(0, int(total_symbols))
    def applicable(name: str) -> int:
        return max(0, int(applicability.get(name, total)))
    def dimension(name: str, ready: int) -> dict[str, Any]:
        return coverage_dimension(
            ready, applicable(name), reason_codes=reasons.get(name, ()),
            zero_status=zero_statuses.get(name, "NOT_APPLICABLE"),
        )
    dimensions = {
        "market_data": dimension("market_data", market_ready),
        "historical_data": dimension("historical_data", history_ready),
        "technical_evidence": dimension("technical_evidence", technical_ready),
        "research_evidence": dimension("research_evidence", research_ready),
        "baseline_prediction": dimension("baseline_prediction", baseline_prediction_ready),
        "full_prediction": dimension("full_prediction", full_prediction_ready),
        "outcome_evaluation": dimension("outcome_evaluation", outcome_evaluable),
    }
    dimensions["baseline_prediction"]["readiness_class"] = (
        "BASELINE_EVALUABLE" if dimensions["baseline_prediction"]["status"] == "COMPLETE"
        else "DEGRADED_BASELINE" if dimensions["baseline_prediction"]["status"] == "PARTIAL"
        else dimensions["baseline_prediction"]["status"] if dimensions["baseline_prediction"]["status"] in {"NOT_EVALUATED", "NOT_APPLICABLE"}
        else "INSUFFICIENT"
    )
    dimensions["full_prediction"]["readiness_class"] = (
        "FULL_READY" if dimensions["full_prediction"]["status"] == "COMPLETE"
        else "PARTIAL" if dimensions["full_prediction"]["status"] == "PARTIAL"
        else dimensions["full_prediction"]["status"] if dimensions["full_prediction"]["status"] in {"NOT_EVALUATED", "NOT_APPLICABLE"}
        else "INSUFFICIENT"
    )
    dimensions["decision_input"] = decision_input_readiness(decision_required_inputs)
    intelligence_complete = all(
        dimensions[name]["status"] in {"COMPLETE", "SUFFICIENT", "NOT_APPLICABLE", "NOT_EVALUATED"}
        for name in ("market_data", "historical_data", "technical_evidence", "research_evidence", "full_prediction", "decision_input")
    )
    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "runtime": {"status": runtime_status, "promotes_intelligence": False},
        **dimensions,
        "overall_intelligence": {
            "status": "READY" if intelligence_complete else "DEGRADED",
            "reason_codes": sorted({code for value in dimensions.values() for code in value.get("reason_codes", [])}),
            "method": "all_required_dimensions_truthful_v1",
        },
    }


def validate_intelligence_readiness(readiness: dict[str, Any]) -> dict[str, Any]:
    """Semantic consistency gate used by Operations and deterministic tests."""
    reasons: list[str] = []
    dimensions = ("market_data", "historical_data", "technical_evidence", "research_evidence", "baseline_prediction", "full_prediction", "decision_input", "outcome_evaluation")
    for name in dimensions:
        value = readiness.get(name) if isinstance(readiness.get(name), dict) else {}
        ready, total, status = value.get("ready_symbols"), value.get("total_applicable_symbols"), value.get("status")
        if not isinstance(ready, int) or not isinstance(total, int) or ready < 0 or total < 0 or ready > total:
            reasons.append(f"{name}:INVALID_COVERAGE")
            continue
        expected = ({"NOT_APPLICABLE", "NOT_EVALUATED"} if total == 0 else
                    {"SUFFICIENT" if name == "decision_input" else "COMPLETE"} if ready == total else
                    {"INSUFFICIENT" if name == "decision_input" else "NONE"} if ready == 0 else {"PARTIAL"})
        if status not in expected:
            reasons.append(f"{name}:STATUS_COVERAGE_MISMATCH")
        reason_codes = [str(code) for code in value.get("reason_codes", [])]
        if total == 0 and any(
            token in code for code in reason_codes
            for token in ("INSUFFICIENT", "MISSING", "FAILED", "STALE", "ERROR")
        ) and not all(code.startswith(("NOT_EVALUATED", "NOT_APPLICABLE")) for code in reason_codes):
            reasons.append(f"{name}:OUT_OF_SCOPE_REASON_CONTRADICTION")
    baseline = readiness.get("baseline_prediction") or {}
    full = readiness.get("full_prediction") or {}
    if int(full.get("ready_symbols") or 0) > int(baseline.get("ready_symbols") or 0):
        reasons.append("FULL_READY_EXCEEDS_BASELINE_EVALUABLE")
    full_count = int(full.get("ready_symbols") or 0)
    for dependency in ("technical_evidence", "research_evidence"):
        if full_count > int((readiness.get(dependency) or {}).get("ready_symbols") or 0):
            reasons.append(f"FULL_READY_EXCEEDS_{dependency.upper()}")
    if readiness.get("runtime", {}).get("promotes_intelligence") is not False:
        reasons.append("RUNTIME_PROMOTES_INTELLIGENCE")
    return {"status": "FAIL" if reasons else "PASS", "reason_codes": reasons}


def readiness_health_projection(readiness: dict[str, Any]) -> dict[str, str]:
    """Project canonical readiness into legacy summary fields without contradiction."""
    baseline = readiness.get("baseline_prediction") or {}
    decision = readiness.get("decision_input") or {}
    research = readiness.get("research_evidence") or {}
    prediction_map = {
        "COMPLETE": "AVAILABLE", "PARTIAL": "PARTIAL", "NONE": "INSUFFICIENT",
        "NOT_APPLICABLE": "NOT_APPLICABLE", "NOT_EVALUATED": "NOT_EVALUATED",
    }
    return {
        "prediction_status": prediction_map.get(str(baseline.get("status")), "NOT_EVALUATED"),
        "decision_status": str(decision.get("readiness") or decision.get("status") or "NOT_EVALUATED"),
        "research_status": str(research.get("status") or "NOT_EVALUATED"),
    }


def validate_health_readiness_consistency(health: dict[str, Any]) -> dict[str, Any]:
    readiness = health.get("intelligence_readiness_v1")
    if not isinstance(readiness, dict):
        return {"status": "NOT_EVALUATED", "reason_codes": []}
    expected = readiness_health_projection(readiness)
    reasons = [
        f"{field.upper()}_READINESS_CONTRADICTION"
        for field, value in expected.items() if str(health.get(field)) != str(value)
    ]
    if health.get("runtime_success_is_intelligence_success") is not False:
        reasons.append("RUNTIME_PROMOTES_INTELLIGENCE")
    readiness_result = validate_intelligence_readiness(readiness)
    reasons.extend(readiness_result.get("reason_codes", []))
    return {"status": "FAIL" if reasons else "PASS", "reason_codes": sorted(set(reasons)), "expected": expected}


def completeness_v2(*, market_data: str, technical: str, research: str,
                    decision_input: str, prediction_input: str,
                    research_score: float | None = None,
                    missing_categories: list[str] | None = None,
                    readiness: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "intelligence_completeness_v2",
        "market_data_completeness": market_data,
        "technical_evidence_completeness": technical,
        "research_evidence_completeness": research,
        "decision_input_completeness": decision_input,
        "prediction_input_completeness": prediction_input,
        "research_coverage_pct": research_score,
        "missing_research_categories": sorted(set(missing_categories or [])),
        "intelligence_readiness_v1": readiness,
        "universal_data_complete": False,
    }


def semantic_degradation(*, quote_total: int = 0, quote_available: int = 0,
                         history_claimed_valid: int = 0, technical_executable: int = 0,
                         provider_market_values: bool = False, research_market_available: bool = False,
                         price_exists: bool = False, research_price_missing: bool = False,
                         prediction_exists: bool = False, evidence_identity: Any = None,
                         expected_source_gaps: Iterable[str] = (), optional_source_gaps: Iterable[str] = (),
                         insufficient_data: Iterable[str] = (), not_applicable: Iterable[str] = (),
                         provider_failures: Iterable[str] = (),
                         completeness: dict[str, Any] | None = None) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    def add(code: str, category: str, severity: str) -> None:
        findings.append({"reason_code": code, "category": category, "severity": severity})
    if quote_total and quote_available == quote_total and history_claimed_valid and technical_executable == 0:
        add("HISTORY_VALID_BUT_TECHNICAL_EMPTY", "STRUCTURAL_DEGRADATION", "HIGH")
    if provider_market_values and not research_market_available:
        add("PROVIDER_DATA_CONSUMER_DISCONNECTED", "CONSUMER_DISCONNECTED", "HIGH")
    if price_exists and research_price_missing:
        add("PRICE_EVIDENCE_CONSUMER_DISCONNECTED", "CONSUMER_DISCONNECTED", "HIGH")
    if prediction_exists and not evidence_identity:
        add("PREDICTION_EVIDENCE_IDENTITY_MISSING", "STRUCTURAL_DEGRADATION", "HIGH")
    for code in provider_failures: add(str(code), "PROVIDER_FAILURE", "HIGH")
    for code in expected_source_gaps: add(str(code), "EXPECTED_SOURCE_GAP", "INFO")
    for code in optional_source_gaps: add(str(code), "OPTIONAL_SOURCE_UNAVAILABLE", "INFO")
    for code in insufficient_data: add(str(code), "INSUFFICIENT_DATA", "MEDIUM")
    for code in not_applicable: add(str(code), "NOT_APPLICABLE", "INFO")
    # Research being partial while quotes are complete is an observation, not
    # structural failure, unless a provider/consumer disconnect is known.
    if completeness and completeness.get("market_data_completeness") == "COMPLETE" and completeness.get("research_evidence_completeness") != "COMPLETE":
        add("MARKET_COMPLETE_RESEARCH_NOT_COMPLETE", "EXPECTED_SOURCE_GAP", "INFO")
    structural = [x for x in findings if x["category"] in {"STRUCTURAL_DEGRADATION", "CONSUMER_DISCONNECTED", "PROVIDER_FAILURE"}]
    return {
        "status": "DEGRADED" if structural else "HEALTHY_WITH_GAPS" if findings else "HEALTHY",
        "reason_codes": [x["reason_code"] for x in findings],
        "structural_reason_codes": [x["reason_code"] for x in structural],
        "findings": findings,
    }


def _timestamp(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}:MALFORMED_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field}:TIMEZONE_REQUIRED")
    return parsed


def resolve_outcome_timestamp(actual: dict[str, Any], *, session_fallback: str | None = None) -> dict[str, Any]:
    """Prefer admitted evidence time, then bar time, then an explicit fallback."""
    if actual.get("first_observation_timestamp"):
        return {"timestamp": actual["first_observation_timestamp"], "timestamp_method": "ACTUAL_EVIDENCE", "reason_code": None}
    if actual.get("first_bar_timestamp"):
        return {"timestamp": actual["first_bar_timestamp"], "timestamp_method": "BAR_TIMESTAMP", "reason_code": None}
    return {"timestamp": session_fallback, "timestamp_method": "SESSION_FALLBACK", "reason_code": "ACTUAL_EVIDENCE_TIMESTAMP_UNAVAILABLE"}


def validate_no_lookahead_v2(timeline: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "prediction_generated_at", "prediction_data_cutoff", "last_input_market_timestamp",
        "first_outcome_observation_timestamp", "outcome_data_cutoff", "review_generated_at",
    )
    try:
        values = {field: _timestamp(timeline.get(field), field) for field in fields}
    except ValueError as exc:
        return {"status": "FAIL", "reason_codes": [str(exc)], "timestamp_method": timeline.get("timestamp_method")}
    checks = (
        (values["last_input_market_timestamp"] <= values["prediction_data_cutoff"], "INPUT_AFTER_PREDICTION_CUTOFF"),
        (values["prediction_data_cutoff"] < values["first_outcome_observation_timestamp"], "OUTCOME_NOT_AFTER_PREDICTION"),
        (values["first_outcome_observation_timestamp"] <= values["outcome_data_cutoff"], "OUTCOME_SEQUENCE_INVALID"),
        (values["outcome_data_cutoff"] <= values["review_generated_at"], "REVIEW_BEFORE_OUTCOME_CUTOFF"),
        (values["prediction_data_cutoff"] <= values["prediction_generated_at"], "PREDICTION_GENERATED_BEFORE_CUTOFF"),
    )
    reasons = [reason for valid, reason in checks if not valid]
    prediction_date = timeline.get("prediction_effective_trading_date")
    outcome_date = timeline.get("outcome_effective_trading_date")
    if prediction_date and outcome_date and str(prediction_date) != str(outcome_date):
        reasons.append("TRADING_DATE_MISMATCH")
    return {"status": "FAIL" if reasons else "PASS", "reason_codes": reasons, "timestamp_method": timeline.get("timestamp_method")}


def intelligence_health(*, runtime_status: str, data_quality_status: str,
                        research_status: str, prediction_status: str,
                        decision_status: str, degradation: dict[str, Any],
                        readiness: dict[str, Any] | None = None) -> dict[str, Any]:
    intelligence_status = "DEGRADED" if degradation.get("status") == "DEGRADED" else (readiness or {}).get("overall_intelligence", {}).get("status", "HEALTHY")
    derived = readiness_health_projection(readiness) if isinstance(readiness, dict) else {
        "research_status": research_status, "prediction_status": prediction_status, "decision_status": decision_status,
    }
    result = {
        "schema_version": "runtime_intelligence_health_v1",
        "runtime_status": runtime_status,
        "data_quality_status": data_quality_status,
        "research_status": derived["research_status"],
        "prediction_status": derived["prediction_status"],
        "decision_status": derived["decision_status"],
        "intelligence_status": intelligence_status,
        "reason_codes": degradation.get("reason_codes") or [],
        "intelligence_readiness_v1": readiness,
        "runtime_success_is_intelligence_success": False,
    }
    result["health_readiness_consistency"] = validate_health_readiness_consistency(result)
    return result
