"""Offline sample input for Prediction Context V1."""
from __future__ import annotations
from typing import Any
from .schemas import SCHEMA_VERSION, TASK_ID


def offline_sample_input() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "generated_at": "2026-07-04T00:00:00+00:00",
        "symbol": "2330",
        "market": "TW",
        "context_window": {
            "as_of_date": "2026-07-04",
            "lookback_days": 90,
            "forecast_horizons": ["same_day_high_low", "next_day_high_low", "one_month_trend", "three_month_trend"],
            "sample_mode": True,
        },
        "source_inputs": {
            "official_primary_source": [
                {"source_id": "company_filing", "provider": "Company official filing / MOPS", "source_priority": "A_primary", "credibility_level": "official", "decision_value": "primary company disclosure anchor"}
            ],
            "official_market_source": [
                {"source_id": "twse_openapi", "provider": "TWSE OpenAPI", "source_priority": "A_official_market", "credibility_level": "official_market", "decision_value": "market/chip attribution"},
                {"source_id": "shioaji_sinopac", "provider": "Sinopac/Shioaji", "source_priority": "A_broker_market", "credibility_level": "official_runtime_market", "decision_value": "future runtime market data anchor"},
            ],
            "normalized_external_data_provider": [
                {"source_id": "finmind", "provider": "FinMind", "source_priority": "B_normalized_external", "credibility_level": "normalized_supplement", "decision_value": "supplemental formal report context"}
            ],
            "external_reference_proxy": [
                {"source_id": "yfinance_yahoo", "provider": "Yahoo Finance / yfinance", "source_priority": "C_external_proxy", "credibility_level": "reference_proxy", "decision_value": "ADR / US ETF / sector proxy only"}
            ],
            "ai_generated_analysis": [
                {"source_id": "gemini_google_generative_ai", "provider": "Gemini", "source_priority": "D_ai_generated", "credibility_level": "generated_analysis", "decision_value": "draft explanation only"}
            ],
            "low_priority_metadata": [
                {"source_id": "broker_target_price_metadata", "provider": "Broker target/rating metadata", "source_priority": "E_low_priority_metadata", "credibility_level": "sentiment_metadata", "decision_value": "metadata only"},
                {"source_id": "google_news_rss", "provider": "Google News RSS", "source_priority": "E_low_priority_metadata", "credibility_level": "headline_sentiment", "decision_value": "headline context only"},
            ],
        },
        "formal_report_integrations": {
            "finmind_report_integration_artifact": {"source_id": "finmind", "artifact_path": "templates/finmind_report_integration_artifact.example.json", "report_allowed": True, "prediction_context_allowed": True},
            "twse_report_integration_artifact": {"source_id": "twse_openapi", "artifact_path": "templates/twse_yfinance_report_integration_artifact.example.json", "report_allowed": True, "prediction_context_allowed": True},
            "yfinance_yahoo_report_integration_artifact": {"source_id": "yfinance_yahoo", "artifact_path": "templates/twse_yfinance_report_integration_artifact.example.json", "report_allowed": True, "prediction_context_allowed": True},
        },
        "technical_context": {"status": "sample_ready", "signals": ["momentum_breakout", "moving_average_alignment"], "direct_rating_action_confidence_impact": False},
        "chip_context": {"status": "sample_ready", "source_ids": ["twse_openapi"], "summary": "Sample institutional flow context only.", "direct_rating_action_confidence_impact": False},
        "adr_context": {"status": "sample_ready", "source_ids": ["yfinance_yahoo"], "summary": "ADR and US ETF proxy reference only.", "official_source_replacement_allowed": False, "direct_rating_action_confidence_impact": False},
        "news_context": {"status": "sample_ready", "source_ids": ["google_news_rss"], "summary": "Headline metadata only.", "direct_rating_action_confidence_impact": False},
        "finmind_context": {"status": "sample_ready", "artifact_ref": "finmind_report_integration_artifact", "official_source_replacement_allowed": False, "direct_rating_action_confidence_impact": False},
        "twse_context": {"status": "sample_ready", "artifact_ref": "twse_report_integration_artifact", "official_source_replacement_allowed": True, "direct_rating_action_confidence_impact": False},
        "yfinance_context": {"status": "sample_ready", "artifact_ref": "yfinance_yahoo_report_integration_artifact", "official_source_replacement_allowed": False, "direct_rating_action_confidence_impact": False},
        "historical_context": {"status": "sample_ready", "artifact_ref": "templates/historical_artifact_store.example.json", "direct_rating_action_confidence_impact": False},
        "rolling_evaluation_context": {"status": "sample_ready", "artifact_ref": "templates/rolling_evaluation_artifact.example.json", "direct_rating_action_confidence_impact": False},
        "market_regime_context": {"status": "sample_ready", "artifact_ref": "templates/market_regime_artifact.example.json", "direct_rating_action_confidence_impact": False},
        "confidence_calibration_context": {"status": "sample_ready", "artifact_ref": "templates/confidence_calibration_artifact.example.json", "direct_rating_action_confidence_impact": False},
        "factor_effectiveness_context": {"status": "sample_ready", "artifact_ref": "templates/factor_recommendation_artifact.example.json", "direct_rating_action_confidence_impact": False},
        "explainability_context": {"status": "sample_ready", "artifact_ref": "templates/source_explainability_artifact.example.json", "required_for_future_traceability": True, "direct_rating_action_confidence_impact": False},
    }
