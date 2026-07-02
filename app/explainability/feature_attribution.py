"""Build deterministic feature attributions from normalized source evidence."""
from __future__ import annotations
from typing import Any
from app.explainability.explanation_policy import FINMIND_NO_RAISE_POLICY, NEWS_NO_RAISE_POLICY, YFINANCE_NO_RAISE_POLICY, official_source_wins, policy_notes
from app.explainability.schemas import FEATURE_ATTRIBUTION_SCHEMA_VERSION, FeatureAttribution, FeatureContribution

def _contribution(feature_id: str, name: str, group: str, direction: str, magnitude: float, score: float, confidence: float, source_ids: list[str], evidence_ids: list[str], text: str, risk: str | None = None) -> FeatureContribution:
    return FeatureContribution(feature_id, name, group, direction, magnitude, score, confidence, source_ids, evidence_ids, text, risk)

def build_feature_attribution(run_id: str, stock_id: str, stock_name: str, evidence: list[dict[str, Any]]) -> FeatureAttribution:
    by_source = {item.get("source_id"): item for item in evidence}
    contributions: list[FeatureContribution] = []
    contributions.append(_contribution("technical_price_strength", "Technical price strength", "technical", "positive", 0.72, 8.0, 0.04, ["finmind_taiwan_stock_price"], [by_source.get("finmind_taiwan_stock_price", {}).get("evidence_id", "finmind_taiwan_stock_price:missing")], "Price/market data sample supports a positive technical contribution, but remains a cross-check input."))
    if "yfinance_external_market_context" in by_source:
        contributions.append(_contribution("external_market_context", "ADR / yfinance market context", "macro", "positive", 0.48, 2.0, 0.0, ["yfinance_external_market_context"], [by_source["yfinance_external_market_context"]["evidence_id"]], "External market context supports confirmation only and cannot independently raise rating.", YFINANCE_NO_RAISE_POLICY))
    if "twse_monthly_revenue" in by_source:
        contributions.append(_contribution("official_monthly_revenue", "Official monthly revenue", "fundamental", "positive", 0.7, 6.0, 0.08, ["twse_monthly_revenue"], [by_source["twse_monthly_revenue"]["evidence_id"]], "Official monthly revenue primary evidence is available."))
    if "finmind_monthly_revenue" in by_source:
        risk = FINMIND_NO_RAISE_POLICY
        if official_source_wins(by_source["finmind_monthly_revenue"]): risk += "; source_conflict marked and official source is authoritative"
        contributions.append(_contribution("finmind_monthly_revenue_cross_check", "FinMind monthly revenue cross-check", "fundamental", "neutral", 0.45, 0.0, 0.02, ["finmind_monthly_revenue"], [by_source["finmind_monthly_revenue"]["evidence_id"]], "Aggregated monthly revenue evidence is available, but primary source confirmation controls readiness.", risk))
    if "finmind_financial_statement" in by_source:
        contributions.append(_contribution("finmind_statement_partial_readiness", "FinMind financial statement partial readiness", "fundamental", "neutral", 0.4, 0.0, 0.02, ["finmind_financial_statement"], [by_source["finmind_financial_statement"]["evidence_id"]], "FinMind statement evidence can move readiness to partial when official statement source is missing, not ready.", FINMIND_NO_RAISE_POLICY))
    if "finmind_institutional_investors_buy_sell" in by_source:
        contributions.append(_contribution("finmind_institutional_flow", "FinMind institutional flow", "chip", "positive", 0.42, 2.5, 0.02, ["finmind_institutional_investors_buy_sell"], [by_source["finmind_institutional_investors_buy_sell"]["evidence_id"]], "Institutional flow contributes chip explanation but cannot override official source."))
    for source_id, text in [("twse_material_information", "Material information primary source missing; disclosure gap is non-fatal."), ("tdcc_shareholding_distribution", "TDCC unavailable; chip structure evidence unavailable without hard failure."), ("etf_holdings_nav_distribution", "ETF-specific holdings/NAV/distribution source gap must cap ETF explanation readiness."), ("finmind_cash_flows", "FinMind unavailable is non-fatal and recorded in missing data summary.")]:
        item = by_source.get(source_id)
        if item and item.get("evidence_type") == "missing_source_notice":
            contributions.append(_contribution(source_id + "_missing", source_id + " missing", "missing_data" if "etf" not in source_id else "etf", "not_available", 0.0, 0.0, -0.08, [source_id], [item["evidence_id"]], text, "missing source can cap confidence"))
    contributions.append(_contribution("news_metadata_only", "News-only event metadata", "news", "neutral", 0.2, 0.0, 0.0, ["management_interview"], ["management_interview:2330:missing"], "News-only evidence is metadata only and cannot raise rating alone.", NEWS_NO_RAISE_POLICY))
    return FeatureAttribution(FEATURE_ATTRIBUTION_SCHEMA_VERSION, run_id, stock_id, stock_name, [item.to_dict() for item in contributions], policy_notes())
