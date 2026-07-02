"""Build stock explanations from feature attributions and source coverage."""
from __future__ import annotations
from typing import Any
from app.explainability.explanation_policy import confidence_cap_reason, readiness_from_sources
from app.explainability.schemas import STOCK_EXPLANATION_SCHEMA_VERSION, StockExplanation

def build_stock_explanation(run_id: str, stock_id: str, stock_name: str, attribution: dict[str, Any], evidence: list[dict[str, Any]]) -> StockExplanation:
    contributions = list(attribution.get("contributions", []))
    positive = [c for c in contributions if c.get("direction") == "positive"]
    negative = [c for c in contributions if c.get("direction") == "negative"]
    neutral = [c for c in contributions if c.get("direction") == "neutral"]
    missing = [c for c in contributions if c.get("direction") == "not_available" or c.get("feature_group") in {"missing_data", "etf"}]
    sources = {item.get("source_id") for item in evidence}
    missing_sources = sorted({item.get("source_id") for item in evidence if item.get("evidence_type") == "missing_source_notice"})
    has_official = "twse_monthly_revenue" in sources
    has_finmind = "finmind_monthly_revenue" in sources or "finmind_financial_statement" in sources
    readiness = readiness_from_sources(has_official, has_finmind, bool(missing_sources))
    if missing_sources and readiness == "ready": readiness = "partial"
    cap_reason = confidence_cap_reason(readiness, missing_sources)
    status = "complete" if readiness == "ready" else "limited_by_missing_primary_sources" if readiness == "insufficient" else "partial"
    return StockExplanation(STOCK_EXPLANATION_SCHEMA_VERSION, run_id, stock_id, stock_name, "positive", 78.5, "watch", ["next_day_high_low", "one_month_trend", "three_month_trend", "rating_action"], positive[:4], negative[:4], neutral[:5], missing[:6], {"readiness": readiness, "missing_sources": missing_sources, "has_finmind_cross_check": has_finmind, "has_official_monthly_revenue": has_official}, cap_reason, status, True)
