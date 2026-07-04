"""Build deterministic TWSE/yfinance formal report integration artifacts."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
from .twse_yfinance_report_schema import REPORT_SECTION_IDS, SCHEMA_VERSION, ReportSourcePolicy, safety_summary

def offline_sample_input() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": "AI-DEV-134",
        "generated_from": "deterministic_offline_sample",
        "twse": {
            "chip_institutional_summary": {"foreign_investor_net_buy_sell": "sample_positive", "investment_trust_net_buy_sell": "sample_neutral", "dealer_net_buy_sell": "sample_negative", "official_attribution": "TWSE official chip/institutional source"},
            "margin_trading_summary": {"margin_balance_change": "sample_increase", "short_balance_change": "sample_decrease", "official_attribution": "TWSE official margin trading source"},
            "freshness": {"expected_frequency": "market_day", "stale_after": "next_market_day", "failure_mode": "mark_unavailable_and_show_diagnostics"},
        },
        "yfinance": {
            "adr_reference": {"symbols": ["TSM"], "usage": "ADR cross-check/reference only"},
            "us_index_etf_sector_proxy": {"symbols": ["^IXIC", "SPY", "SOXX", "SMH"], "usage": "US index/ETF/sector proxy only"},
            "external_market_sentiment_proxy": {"signals": ["US index direction", "semiconductor ETF direction", "ADR context"], "usage": "external market sentiment proxy"},
            "freshness": {"expected_frequency": "market_day", "stale_after": "next_market_day", "failure_mode": "mark_unavailable_without_failing_report"},
        },
    }

def source_policies() -> list[dict[str, Any]]:
    return [
        ReportSourcePolicy(
            source_id="twse_openapi",
            provider="TWSE OpenAPI",
            source_role="official_market_chip_source",
            report_use=["chip / institutional summary", "margin trading summary", "official market/chip attribution"],
            freshness_policy="market_day; stale after next market day",
            failure_mode="show unavailable/stale diagnostics without failing full report",
            official_source_replacement_allowed=True,
            direct_rating_action_confidence_impact=False,
            explainability_note="TWSE is official market/chip attribution, but this artifact does not directly mutate rating/action/confidence.",
        ).to_dict(),
        ReportSourcePolicy(
            source_id="yfinance_yahoo",
            provider="Yahoo Finance / yfinance",
            source_role="external_reference_proxy",
            report_use=["ADR reference", "US index / ETF / sector proxy", "external market sentiment proxy"],
            freshness_policy="market_day; stale after next market day",
            failure_mode="show unavailable/stale diagnostics without failing full report",
            official_source_replacement_allowed=False,
            direct_rating_action_confidence_impact=False,
            explainability_note="yfinance/Yahoo is external reference/proxy only and cannot replace TWSE/MOPS/company official sources.",
        ).to_dict(),
    ]

def build_artifact(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = payload or offline_sample_input()
    generated_at = datetime.now(timezone.utc).isoformat()
    policies = source_policies()
    report_sections = [
        {"section_id": "twse_chip_institutional_summary", "title": "TWSE chip / institutional summary", "source_id": "twse_openapi", "summary": payload["twse"]["chip_institutional_summary"], "official_attribution": True, "direct_rating_action_confidence_impact": False},
        {"section_id": "twse_margin_trading_summary", "title": "TWSE margin trading summary", "source_id": "twse_openapi", "summary": payload["twse"]["margin_trading_summary"], "official_attribution": True, "direct_rating_action_confidence_impact": False},
        {"section_id": "twse_official_market_attribution", "title": "Official market/chip attribution", "source_id": "twse_openapi", "summary": "TWSE sections are official market/chip attribution for formal reports.", "official_attribution": True, "direct_rating_action_confidence_impact": False},
        {"section_id": "yfinance_adr_reference", "title": "ADR reference", "source_id": "yfinance_yahoo", "summary": payload["yfinance"]["adr_reference"], "official_source_replacement_allowed": False, "direct_rating_action_confidence_impact": False},
        {"section_id": "yfinance_us_index_etf_sector_proxy", "title": "US index / ETF / sector proxy", "source_id": "yfinance_yahoo", "summary": payload["yfinance"]["us_index_etf_sector_proxy"], "official_source_replacement_allowed": False, "direct_rating_action_confidence_impact": False},
        {"section_id": "yfinance_external_market_sentiment_proxy", "title": "External market sentiment proxy", "source_id": "yfinance_yahoo", "summary": payload["yfinance"]["external_market_sentiment_proxy"], "official_source_replacement_allowed": False, "direct_rating_action_confidence_impact": False},
        {"section_id": "freshness_and_failure_modes", "title": "Freshness and failure modes", "source_id": "twse_openapi,yfinance_yahoo", "summary": {"twse": payload["twse"]["freshness"], "yfinance": payload["yfinance"]["freshness"]}, "direct_rating_action_confidence_impact": False},
        {"section_id": "safety_and_governance", "title": "Safety and governance", "source_id": "policy", "summary": safety_summary(), "direct_rating_action_confidence_impact": False},
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": "AI-DEV-134",
        "artifact_type": "twse_yfinance_formal_report_integration_foundation_v1",
        "generated_at": generated_at,
        "input_summary": {"source": payload.get("generated_from", "provided_payload"), "external_api_called": False, "secrets_required": False},
        "source_policies": policies,
        "freshness_policy": {"twse_openapi": payload["twse"]["freshness"], "yfinance_yahoo": payload["yfinance"]["freshness"]},
        "report_sections": report_sections,
        "explainability_notes": [policy["explainability_note"] for policy in policies],
        "daily_report_integration": {"ready_for_daily_report_context": True, "prediction_context_allowed": True, "direct_rating_action_confidence_impact": False, "requires_future_runtime_fetch_task": True},
        "safety_summary": safety_summary(),
        "future_integration": {"ai_dev_135_ready": True, "notes": ["Connect real runtime data in a separate gated task.", "Keep yfinance as external reference/proxy only.", "TWSE remains official market/chip source."]},
    }
