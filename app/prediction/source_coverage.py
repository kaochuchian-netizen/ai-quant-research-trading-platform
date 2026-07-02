"""Source coverage matrix and confidence-cap logic."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
from app.prediction.schemas import PREDICTION_TARGETS
from app.prediction.source_inventory import inventory_by_id
SCHEMA_VERSION = "source_coverage_matrix_v1"
READINESS_LEVELS = {"ready", "partial", "insufficient"}
COVERAGE_POLICIES: dict[str, dict[str, Any]] = {
    "intraday_high_low": {"required_sources": ["historical_csv_fallback", "shioaji_ohlcv"], "optional_sources": ["twse_openapi", "adr_yfinance", "yfinance_external_market"], "minimum_required_available": 1, "confidence_caps": {"ready": 0.9, "partial": 0.65, "insufficient": 0.4}, "missing_data_policy": ["missing_historical_ohlcv", "adr_not_applicable", "yfinance_unavailable"], "notes": "Requires OHLCV / technical / recent price context. ADR and external market are optional confirmation signals."},
    "next_day_high_low": {"required_sources": ["historical_csv_fallback", "shioaji_ohlcv"], "optional_sources": ["twse_openapi", "adr_yfinance", "yfinance_external_market", "chip_analysis_existing", "macro_vix_us_yield_usd_sox_nasdaq"], "minimum_required_available": 1, "confidence_caps": {"ready": 0.9, "partial": 0.68, "insufficient": 0.4}, "missing_data_policy": ["missing_historical_ohlcv", "adr_not_applicable", "yfinance_unavailable"], "notes": "Requires OHLCV / technical / recent price. ADR, US market, semiconductor proxy, and chip data are optional/important."},
    "one_month_trend": {"required_sources": ["historical_csv_fallback", "mops_monthly_revenue", "mops_financial_statement", "mops_material_information"], "optional_sources": ["chip_analysis_existing", "tdcc_shareholding_distribution", "industry_chain_sources", "google_news_rss", "gemini_news_summary", "yfinance_external_market"], "minimum_required_available": 2, "confidence_caps": {"ready": 0.9, "partial": 0.6, "insufficient": 0.4}, "missing_data_policy": ["missing_fundamental", "news_only_without_primary_source", "yfinance_unavailable", "etf_specific_source_gap"], "notes": "Requires stronger fundamental/disclosure coverage; missing monthly revenue, statements, or material information lowers readiness."},
    "three_month_trend": {"required_sources": ["historical_csv_fallback", "mops_monthly_revenue", "mops_financial_statement", "mops_material_information", "company_official_guidance", "industry_chain_sources", "macro_vix_us_yield_usd_sox_nasdaq"], "optional_sources": ["mops_investor_conference", "earnings_call_transcript_or_investor_deck", "management_interviews", "tdcc_shareholding_distribution", "securities_lending", "google_news_rss", "gemini_news_summary", "yfinance_external_market"], "minimum_required_available": 4, "confidence_caps": {"ready": 0.9, "partial": 0.6, "insufficient": 0.4}, "missing_data_policy": ["missing_fundamental", "news_only_without_primary_source", "yfinance_unavailable", "etf_specific_source_gap"], "notes": "Requires fundamental, industry, company guidance, macro, and disclosure coverage; missing core sources makes readiness insufficient."},
    "rating_action": {"required_sources": ["historical_csv_fallback", "google_sheet_stock_universe"], "optional_sources": ["chip_analysis_existing", "adr_yfinance", "yfinance_external_market", "google_news_rss", "gemini_news_summary", "mops_monthly_revenue", "mops_financial_statement", "mops_material_information", "etf_holdings_nav_distribution"], "minimum_required_available": 1, "confidence_caps": {"ready": 0.9, "partial": 0.7, "insufficient": 0.4}, "missing_data_policy": ["news_only_without_primary_source", "adr_not_applicable", "yfinance_unavailable", "etf_specific_source_gap"], "notes": "Can run with existing technical/news/chip/ADR scoring, but rating confidence must reflect source quality and coverage gaps."},
}
def _current_available_source_ids(inventory: dict[str, dict[str, Any]]) -> set[str]:
    return {sid for sid, item in inventory.items() if item.get("status") == "current" and item.get("current_integration") != "not_integrated"}
def _readiness(required: list[str], available: list[str], minimum: int) -> str:
    count = len(set(required) & set(available))
    if count == len(required): return "ready"
    if count >= minimum: return "partial"
    return "insufficient"
def build_source_coverage_matrix(available_source_ids: set[str] | None = None, inventory: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    indexed = inventory_by_id(inventory); available = set(available_source_ids) if available_source_ids is not None else _current_available_source_ids(indexed); matrix: list[dict[str, Any]] = []
    for target in sorted(PREDICTION_TARGETS):
        policy = COVERAGE_POLICIES[target]; required = list(policy["required_sources"]); optional = list(policy["optional_sources"]); expected = required + optional
        available_sources = [sid for sid in expected if sid in available]; missing = [sid for sid in required if sid not in available]; optional_missing = [sid for sid in optional if sid not in available]
        readiness = _readiness(required, available_sources, int(policy["minimum_required_available"])); required_score = len(set(required) & set(available_sources)) / len(required); optional_score = len(set(optional) & set(available_sources)) / max(len(optional), 1)
        matrix.append({"schema_version": SCHEMA_VERSION, "prediction_target": target, "required_sources": required, "optional_sources": optional, "available_sources": available_sources, "missing_sources": missing, "optional_missing_sources": optional_missing, "coverage_score": round(required_score * 0.8 + optional_score * 0.2, 4), "readiness": readiness, "confidence_cap": policy["confidence_caps"][readiness], "missing_data_policy": list(policy["missing_data_policy"]), "notes": policy["notes"]})
    return matrix
def coverage_by_target(matrix: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    return {item["prediction_target"]: deepcopy(item) for item in (matrix or build_source_coverage_matrix())}
def cap_confidence(confidence: float | None, coverage: dict[str, Any]) -> tuple[float | None, str]:
    if confidence is None: return None, "insufficient_data"
    cap = float(coverage.get("confidence_cap", 1.0)); readiness = coverage.get("readiness"); capped = min(float(confidence), cap)
    if readiness == "insufficient": return capped, "insufficient_data"
    if capped < float(confidence): return capped, "capped"
    if readiness == "partial": return capped, "downgraded"
    return capped, "ready"
def validate_source_coverage_matrix(matrix: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []; targets = set()
    for index, item in enumerate(matrix):
        label = f"source_coverage_matrix[{index}]"
        for field in ["prediction_target", "required_sources", "optional_sources", "available_sources", "missing_sources", "coverage_score", "readiness", "confidence_cap", "missing_data_policy"]:
            if field not in item: reasons.append(f"{label}: missing {field}")
        target = item.get("prediction_target")
        if target not in PREDICTION_TARGETS: reasons.append(f"{label}: invalid prediction_target {target!r}")
        else: targets.add(target)
        if item.get("readiness") not in READINESS_LEVELS: reasons.append(f"{label}: invalid readiness {item.get('readiness')!r}")
        for name in ["coverage_score", "confidence_cap"]:
            value = item.get(name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 1: reasons.append(f"{label}: {name} must be 0..1")
    for target in sorted(PREDICTION_TARGETS - targets): reasons.append(f"missing coverage target: {target}")
    return reasons
