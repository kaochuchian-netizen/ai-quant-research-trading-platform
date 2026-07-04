from __future__ import annotations
from typing import Any
from app.source_roadmap.schemas import SourceConnectorPriorityPolicy

LOW_PRIORITY_IDS = {"google_news_rss", "gemini_google_generative_ai", "management_interviews", "analyst_target_broker_opinion"}
FORMAL_REPORT_FIRST = {"twse_openapi", "yfinance_yahoo"}
CONNECTOR_BUILD = {"mops_public_information_observatory", "company_announcements", "financial_statements", "investor_conference", "industry_supply_chain", "etf_index_sector_proxy"}
IMMEDIATE_CONTEXT = {"google_sheet", "shioaji_sinopac", "sqlite_historical_csv", "twse_openapi", "mops_public_information_observatory", "financial_statements", "company_announcements"}
MANUAL_REVIEW = {"analyst_target_broker_opinion"}

def _risk_from_record(record: dict[str, Any]) -> str:
    if record.get("credential_required") or record.get("current_status") == "needs_connector":
        return "high"
    if record.get("source_priority") in {"C_market_or_industry", "D_low_priority_metadata_noise"}:
        return "medium"
    return "low"

def _decision_value(record: dict[str, Any]) -> str:
    if record.get("source_id") in LOW_PRIORITY_IDS:
        return "low"
    if record.get("source_priority") in {"A_primary", "B_official_or_company_linked"}:
        return "high"
    return "medium"

def _complexity(record: dict[str, Any]) -> str:
    status = record.get("current_status")
    if status == "production_used":
        return "low"
    if status == "connector_exists_not_in_formal_report":
        return "medium"
    if status == "needs_connector" or record.get("credential_required"):
        return "high"
    return "medium"

def _phase(record: dict[str, Any]) -> str:
    source_id = record.get("source_id")
    status = record.get("current_status")
    if source_id in MANUAL_REVIEW:
        return "manual_review_required"
    if source_id in LOW_PRIORITY_IDS:
        return "phase_4_defer_metadata_only"
    if status == "production_used":
        return "phase_0_maintain"
    if source_id in FORMAL_REPORT_FIRST:
        return "phase_2_formal_report"
    if source_id in CONNECTOR_BUILD:
        return "phase_3_connector_build"
    return "phase_1_prediction_context"

def build_priority_policy(record: dict[str, Any]) -> dict[str, Any]:
    source_id = record["source_id"]
    phase = _phase(record)
    low_priority = source_id in LOW_PRIORITY_IDS
    prediction_candidate = source_id in IMMEDIATE_CONTEXT and not low_priority
    formal_report_candidate = phase in {"phase_0_maintain", "phase_2_formal_report", "phase_3_connector_build"} and not low_priority
    rating_allowed = record.get("source_priority") in {"A_primary", "B_official_or_company_linked"} and not low_priority and phase != "manual_review_required"
    rationale: list[str] = []
    if prediction_candidate:
        rationale.append("candidate for prediction context after deterministic artifact validation")
    if formal_report_candidate:
        rationale.append("candidate for formal report once freshness and failure policy are validated")
    if low_priority:
        rationale.append("low-priority metadata/noise; must not independently affect rating/action/confidence")
    if phase == "manual_review_required":
        rationale.append("requires manual review for licensing, quality, and credential policy")
    return SourceConnectorPriorityPolicy(
        source_id=source_id,
        source_name=record["source_name"],
        current_status=record["current_status"],
        source_priority=record["source_priority"],
        decision_value=_decision_value(record),
        freshness_requirement=record.get("freshness_policy", "to_be_defined"),
        reliability_risk=_risk_from_record(record),
        explainability_value="high" if record.get("explainability_support") == "supported_with_evidence_ids" else "medium" if record.get("source_priority") != "D_low_priority_metadata_noise" else "low",
        credential_requirement="required" if record.get("credential_required") else "not_required",
        implementation_complexity=_complexity(record),
        production_risk="high" if low_priority or record.get("credential_required") else "medium" if record.get("current_status") != "production_used" else "low",
        recommended_phase=phase,
        prediction_context_candidate=prediction_candidate,
        formal_report_candidate=formal_report_candidate,
        low_priority_metadata_only=low_priority,
        rating_action_confidence_allowed=rating_allowed,
        rationale=rationale,
    ).to_dict()
