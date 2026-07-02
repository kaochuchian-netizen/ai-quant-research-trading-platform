"""Read-only source endpoint registry for AI-DEV-123."""
from __future__ import annotations
from app.sources.schemas import SourceEndpoint

COMMON_OFFICIAL_POLICY = ["primary_or_official_reference", "read_only", "no production score mutation"]
YFINANCE_POLICY = ["external market context / confirmation signal", "must_not_replace_primary_source", "must_not_independently_raise_rating", "no production score mutation"]
FINMIND_POLICY = ["coverage accelerator", "fallback / cross-check source", "normalized evidence source", "must_not_replace_primary_source", "must_not_independently_raise_rating", "no production score mutation"]

def build_endpoint_registry() -> list[SourceEndpoint]:
    endpoints = [
        SourceEndpoint("twse_monthly_revenue", "TWSE OpenAPI", "monthly_revenue", "fundamental", "B_official_or_company_linked", False, None, "monthly_revenue", True, COMMON_OFFICIAL_POLICY, "Primary monthly revenue representation."),
        SourceEndpoint("twse_material_information", "TWSE OpenAPI", "material_information", "disclosure", "B_official_or_company_linked", False, None, "material_information", True, COMMON_OFFICIAL_POLICY, "Primary material information representation."),
        SourceEndpoint("twse_financial_statement_readiness", "TWSE OpenAPI", "financial_statement_readiness", "fundamental", "B_official_or_company_linked", False, None, "financial_statement", True, COMMON_OFFICIAL_POLICY, "Readiness marker for official statement coverage."),
        SourceEndpoint("tpex_openapi_readiness", "TPEx OpenAPI", "readiness", "disclosure", "B_official_or_company_linked", False, None, "missing_source_notice", True, COMMON_OFFICIAL_POLICY, "TPEx readiness marker."),
        SourceEndpoint("tdcc_shareholding_distribution", "TDCC", "shareholding_distribution", "chip", "B_official_or_company_linked", False, None, "chip_structure", True, COMMON_OFFICIAL_POLICY, "TDCC optional readiness marker."),
        SourceEndpoint("etf_holdings_nav_distribution", "ETF issuer / TWSE", "etf_reference", "etf", "B_official_or_company_linked", False, None, "etf_reference", True, COMMON_OFFICIAL_POLICY, "ETF NAV holdings distribution readiness marker."),
        SourceEndpoint("mops_investor_conference", "MOPS", "investor_conference", "disclosure", "B_official_or_company_linked", False, None, "investor_conference", True, COMMON_OFFICIAL_POLICY, "Investor conference readiness marker."),
        SourceEndpoint("company_official_guidance", "Company official", "guidance", "disclosure", "B_official_or_company_linked", False, None, "material_information", True, COMMON_OFFICIAL_POLICY, "Company guidance readiness marker."),
        SourceEndpoint("management_interview", "Company / media", "management_interview", "news", "D_sentiment_or_noise", False, None, "news_event", True, ["metadata_only", "must_not_independently_raise_rating", "no production score mutation"], "Management interview metadata marker."),
        SourceEndpoint("yfinance_external_market_context", "yfinance / Yahoo Finance", "external_market_context", "macro", "C_market_or_industry", False, None, "market_context", True, YFINANCE_POLICY, "External market context only; cannot replace primary source."),
    ]
    for source_id, evidence_type, category in [
        ("finmind_taiwan_stock_price", "market_price", "market_price"),
        ("finmind_monthly_revenue", "monthly_revenue", "fundamental"),
        ("finmind_financial_statement", "financial_statement", "fundamental"),
        ("finmind_balance_sheet", "financial_statement", "fundamental"),
        ("finmind_cash_flows", "financial_statement", "fundamental"),
        ("finmind_institutional_investors_buy_sell", "institutional_flow", "chip"),
        ("finmind_margin_purchase_short_sale", "margin_short", "chip"),
        ("finmind_holding_shares_per", "chip_structure", "chip"),
    ]:
        endpoints.append(SourceEndpoint(source_id, "FinMind", source_id.replace("finmind_", ""), category, "C_market_or_aggregated_data", "optional", None, evidence_type, True, FINMIND_POLICY, "Third-party aggregated data for offline artifacts, fallback, and cross-check only."))
    return endpoints

def endpoint_by_id() -> dict[str, SourceEndpoint]:
    return {item.source_id: item for item in build_endpoint_registry()}
