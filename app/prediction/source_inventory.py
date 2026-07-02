"""Deterministic V1 data source inventory for prediction coverage."""
from __future__ import annotations
from copy import deepcopy
from typing import Any

SCHEMA_VERSION = "data_source_inventory_v1"
SOURCE_CATEGORIES = {"market_price", "technical", "chip", "news", "adr", "fundamental", "disclosure", "industry", "macro", "etf", "trading_runtime"}
SOURCE_PRIORITIES = {"A_primary", "B_official_or_company_linked", "C_market_or_industry", "D_sentiment_or_noise"}
CURRENT_SOURCE_IDS = {"google_sheet_stock_universe", "shioaji_ohlcv", "historical_csv_fallback", "twse_openapi", "google_news_rss", "gemini_news_summary", "chip_analysis_existing", "adr_yfinance", "yfinance_external_market", "sqlite_historical_or_analysis"}
CANDIDATE_SOURCE_IDS = {"mops_monthly_revenue", "mops_financial_statement", "mops_material_information", "mops_investor_conference", "tdcc_shareholding_distribution", "etf_holdings_nav_distribution", "industry_chain_sources", "macro_vix_us_yield_usd_sox_nasdaq", "securities_branch_flow", "securities_lending", "company_official_guidance", "management_interviews", "earnings_call_transcript_or_investor_deck"}
ALL_TARGETS = ["intraday_high_low", "next_day_high_low", "one_month_trend", "three_month_trend", "rating_action"]

def _source(source_id: str, category: str, provider: str, priority: str, status: str, refresh_frequency: str, credential_required: bool, current_integration: str, prediction_targets: list[str], quality_score: float, noise_risk: str, recommended_usage: str, notes: str, **extra: Any) -> dict[str, Any]:
    item = {"source_id": source_id, "category": category, "provider": provider, "priority": priority, "status": status, "refresh_frequency": refresh_frequency, "credential_required": credential_required, "current_integration": current_integration, "prediction_targets": prediction_targets, "quality_score": quality_score, "noise_risk": noise_risk, "recommended_usage": recommended_usage, "notes": notes}
    item.update(extra)
    return item

def build_data_source_inventory() -> list[dict[str, Any]]:
    inventory = [
        _source("google_sheet_stock_universe", "market_price", "Google Sheets", "A_primary", "current", "manual_or_runtime_refresh", True, "existing stock universe loader", ALL_TARGETS, 0.75, "low", "stock universe and metadata anchor", "Current universe source; credentials are not read by V1."),
        _source("shioaji_ohlcv", "market_price", "Sinopac Shioaji", "A_primary", "current", "market_session", True, "existing read path only; not invoked by this artifact builder", ["intraday_high_low", "next_day_high_low", "rating_action"], 0.9, "low", "primary OHLCV / recent price when approved runtime is active", "Trading runtime is out of scope for AI-DEV-122."),
        _source("historical_csv_fallback", "market_price", "repo-local CSV", "A_primary", "current", "repo_local", False, "data/historical/*_daily.csv", ["intraday_high_low", "next_day_high_low", "rating_action"], 0.82, "low", "local deterministic OHLCV fallback and actual outcome lookup", "Used by V1 outcome loader without external calls."),
        _source("twse_openapi", "market_price", "TWSE OpenAPI", "B_official_or_company_linked", "current", "daily", False, "existing source registry reference", ["intraday_high_low", "next_day_high_low", "rating_action"], 0.86, "low", "official market reference and confirmation", "Not called by AI-DEV-122 scripts."),
        _source("google_news_rss", "news", "Google News RSS", "D_sentiment_or_noise", "current", "event_driven", False, "existing news fetcher", ["one_month_trend", "three_month_trend", "rating_action"], 0.45, "high", "event/risk metadata only; must not raise rating without primary source", "Useful for alerting context, not standalone evidence."),
        _source("gemini_news_summary", "news", "Gemini news summary", "D_sentiment_or_noise", "current", "on_demand", True, "existing summarization path; not invoked here", ["one_month_trend", "three_month_trend", "rating_action"], 0.42, "high", "summarization of already collected news metadata only", "AI-DEV-122 performs no AI/Gemini batch call."),
        _source("chip_analysis_existing", "chip", "existing chip analysis", "C_market_or_industry", "current", "daily_or_manual", False, "analysis/chip", ["next_day_high_low", "one_month_trend", "rating_action"], 0.65, "medium", "chip flow context and confirmation signal", "Not a replacement for official filings."),
        _source("adr_yfinance", "adr", "yfinance / Yahoo Finance", "C_market_or_industry", "current", "market_day", False, "existing ADR analyzer/mapper", ["next_day_high_low", "rating_action"], 0.58, "medium", "ADR confirmation signal only where ADR mapping exists", "Non-ADR stocks must be marked not_applicable.", must_not_replace_primary_source=True, must_not_independently_raise_rating=True),
        _source("yfinance_external_market", "macro", "yfinance / Yahoo Finance", "C_market_or_industry", "current", "market_day", False, "external market context helper", ["next_day_high_low", "one_month_trend", "three_month_trend", "rating_action"], 0.56, "medium", "external market context / confirmation signal", "Must not replace primary source and must not independently raise rating.", must_not_replace_primary_source=True, must_not_independently_raise_rating=True, external_market_context="confirmation_only"),
        _source("sqlite_historical_or_analysis", "market_price", "repo-local SQLite", "A_primary", "current", "repo_local", False, "existing analysis storage reference; not written by this release", ["rating_action"], 0.72, "low", "local historical/analysis reference when already available", "AI-DEV-122 does not write production DB."),
    ]
    candidates = [
        ("mops_monthly_revenue", "fundamental", "MOPS", "B_official_or_company_linked", ["one_month_trend", "three_month_trend", "rating_action"], "monthly revenue official coverage"),
        ("mops_financial_statement", "fundamental", "MOPS", "B_official_or_company_linked", ["one_month_trend", "three_month_trend", "rating_action"], "financial statements official coverage"),
        ("mops_material_information", "disclosure", "MOPS", "B_official_or_company_linked", ["one_month_trend", "three_month_trend", "rating_action"], "material information official coverage"),
        ("mops_investor_conference", "disclosure", "MOPS", "B_official_or_company_linked", ["three_month_trend", "rating_action"], "investor conference material"),
        ("tdcc_shareholding_distribution", "chip", "TDCC", "B_official_or_company_linked", ["one_month_trend", "three_month_trend", "rating_action"], "shareholding distribution"),
        ("etf_holdings_nav_distribution", "etf", "ETF issuer / TWSE", "B_official_or_company_linked", ["one_month_trend", "three_month_trend", "rating_action"], "ETF NAV, holdings, and distribution coverage"),
        ("industry_chain_sources", "industry", "industry research", "C_market_or_industry", ["one_month_trend", "three_month_trend", "rating_action"], "industry chain context"),
        ("macro_vix_us_yield_usd_sox_nasdaq", "macro", "external macro market data", "C_market_or_industry", ["next_day_high_low", "one_month_trend", "three_month_trend", "rating_action"], "VIX, US yield, USD, SOX, NASDAQ context"),
        ("securities_branch_flow", "chip", "broker / exchange data", "C_market_or_industry", ["next_day_high_low", "one_month_trend", "rating_action"], "branch flow context"),
        ("securities_lending", "chip", "exchange / broker data", "C_market_or_industry", ["one_month_trend", "three_month_trend", "rating_action"], "securities lending pressure"),
        ("company_official_guidance", "disclosure", "company official", "B_official_or_company_linked", ["three_month_trend", "rating_action"], "official guidance"),
        ("management_interviews", "news", "company / media", "D_sentiment_or_noise", ["three_month_trend", "rating_action"], "management interview context"),
        ("earnings_call_transcript_or_investor_deck", "disclosure", "company official", "B_official_or_company_linked", ["three_month_trend", "rating_action"], "earnings call or investor deck"),
    ]
    for source_id, category, provider, priority, targets, usage in candidates:
        inventory.append(_source(source_id, category, provider, priority, "candidate_missing_or_not_integrated", "to_be_defined", False, "not_integrated", targets, 0.7 if priority.startswith("B_") else 0.55, "low" if priority.startswith("B_") else "medium", usage, "Candidate source recorded for coverage policy; no integration is added in AI-DEV-122."))
    return inventory

def inventory_by_id(inventory: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    return {item["source_id"]: deepcopy(item) for item in (inventory or build_data_source_inventory())}

def validate_inventory(inventory: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    ids: set[str] = set()
    for index, item in enumerate(inventory):
        label = f"data_source_inventory[{index}]"
        for field in ["source_id", "category", "provider", "priority", "status", "refresh_frequency", "credential_required", "current_integration", "prediction_targets", "quality_score", "noise_risk", "recommended_usage", "notes"]:
            if field not in item: reasons.append(f"{label}: missing {field}")
        source_id = item.get("source_id")
        if not isinstance(source_id, str) or not source_id: reasons.append(f"{label}: invalid source_id")
        elif source_id in ids: reasons.append(f"duplicate source_id: {source_id}")
        else: ids.add(source_id)
        if item.get("category") not in SOURCE_CATEGORIES: reasons.append(f"{label}: invalid category {item.get('category')!r}")
        if item.get("priority") not in SOURCE_PRIORITIES: reasons.append(f"{label}: invalid priority {item.get('priority')!r}")
        if not isinstance(item.get("credential_required"), bool): reasons.append(f"{label}: credential_required must be boolean")
        targets = item.get("prediction_targets")
        if not isinstance(targets, list) or not targets: reasons.append(f"{label}: prediction_targets must be non-empty list")
        else:
            for target in targets:
                if target not in ALL_TARGETS: reasons.append(f"{label}: invalid prediction target {target!r}")
    for source_id in sorted(CURRENT_SOURCE_IDS - ids): reasons.append(f"missing required current source: {source_id}")
    for source_id in sorted(CANDIDATE_SOURCE_IDS - ids): reasons.append(f"missing required candidate source: {source_id}")
    yfinance = [item for item in inventory if item.get("source_id") == "yfinance_external_market"]
    if not yfinance: reasons.append("missing yfinance_external_market source")
    else:
        item = yfinance[0]
        if item.get("provider") != "yfinance / Yahoo Finance": reasons.append("yfinance provider policy mismatch")
        if item.get("priority") != "C_market_or_industry": reasons.append("yfinance priority must be C_market_or_industry")
        if item.get("noise_risk") != "medium": reasons.append("yfinance noise_risk must be medium")
        if not item.get("must_not_replace_primary_source"): reasons.append("yfinance must_not_replace_primary_source policy missing")
        if not item.get("must_not_independently_raise_rating"): reasons.append("yfinance must_not_independently_raise_rating policy missing")
    return reasons
