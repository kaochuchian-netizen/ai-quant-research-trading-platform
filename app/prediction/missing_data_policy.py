"""Explicit missing-data policy for prediction foundation V1."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
SCHEMA_VERSION = "missing_data_policy_v1"
POLICIES: dict[str, dict[str, Any]] = {
    "missing_historical_ohlcv": {"policy_id": "missing_historical_ohlcv", "applies_to": ["intraday_high_low", "next_day_high_low", "rating_action"], "effect": "technical prediction cannot be completed", "confidence_cap": 0.4, "status": "insufficient_data", "notes": "OHLCV is required for high/low and technical evaluation."},
    "missing_actual_outcome": {"policy_id": "missing_actual_outcome", "applies_to": ["evaluation_v1"], "effect": "evaluation_status=pending_actual_outcome", "confidence_cap": None, "status": "pending", "notes": "Future or unavailable actuals must not fail evaluation."},
    "missing_fundamental": {"policy_id": "missing_fundamental", "applies_to": ["one_month_trend", "three_month_trend"], "effect": "confidence cap lowered and readiness reduced", "confidence_cap": 0.6, "status": "partial_or_insufficient", "notes": "MOPS revenue, statements, and material information are important for longer horizons."},
    "news_only_without_primary_source": {"policy_id": "news_only_without_primary_source", "applies_to": ["one_month_trend", "three_month_trend", "rating_action"], "effect": "must_not_raise_rating", "confidence_cap": 0.45, "status": "insufficient_data", "notes": "Google News RSS and AI summaries can only be event/risk metadata without primary sources."},
    "adr_not_applicable": {"policy_id": "adr_not_applicable", "applies_to": ["next_day_high_low", "rating_action"], "effect": "ADR source marked not_applicable for stocks without ADR mapping", "confidence_cap": None, "status": "not_applicable", "notes": "Missing ADR is not an error when the stock has no ADR mapping."},
    "etf_specific_source_gap": {"policy_id": "etf_specific_source_gap", "applies_to": ["one_month_trend", "three_month_trend", "rating_action"], "effect": "ETF prediction must mark NAV, holdings, and distribution gaps", "confidence_cap": 0.6, "status": "partial", "notes": "ETF coverage requires ETF-specific NAV, holdings, and distribution sources."},
    "yfinance_unavailable": {"policy_id": "yfinance_unavailable", "applies_to": ["next_day_high_low", "one_month_trend", "three_month_trend", "rating_action"], "effect": "external_market_context=unavailable; lower external market coverage only", "confidence_cap": None, "status": "unavailable", "notes": "yfinance must not fail the pipeline and cannot replace primary sources."},
}
def build_missing_data_policy_summary() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "policies": [deepcopy(POLICIES[key]) for key in sorted(POLICIES)], "global_rules": ["Missing values must be explicit pending, insufficient_data, unavailable, or not_applicable states.", "Prediction snapshots remain advisory-only.", "Source coverage gaps cap or downgrade confidence instead of silently passing.", "News-only evidence cannot independently raise rating.", "yfinance is external market context only and must not replace primary sources."]}
def policy_by_id(policy_id: str) -> dict[str, Any] | None:
    item = POLICIES.get(policy_id)
    return deepcopy(item) if item else None
def validate_missing_data_policies(summary: dict[str, Any] | None = None) -> list[str]:
    payload = summary or build_missing_data_policy_summary(); reasons: list[str] = []
    policies = payload.get("policies")
    if not isinstance(policies, list): return ["missing_data_policy_summary.policies must be a list"]
    ids = {item.get("policy_id") for item in policies if isinstance(item, dict)}
    for required in POLICIES:
        if required not in ids: reasons.append(f"missing policy: {required}")
    for item in policies:
        if not isinstance(item, dict): reasons.append("missing data policy entry must be an object"); continue
        for field in ["policy_id", "applies_to", "effect", "status", "notes"]:
            if field not in item: reasons.append(f"policy {item.get('policy_id', '<unknown>')}: missing {field}")
    return reasons
