"""Deterministic US stock batch artifact builder.

V1 is a foundation contract: scheduler-ready and Dashboard/report-ready, but
validation uses offline fixtures and does not call yfinance/Yahoo, Google
Sheets, LINE, Email, trading, DB, or production pipelines.
"""
from __future__ import annotations

from typing import Any

from app.us_stock.constants import (
    DEFAULT_CURRENCY,
    DEFAULT_MARKET,
    DELIVERY_POLICY,
    SAFETY_POLICY,
    SCHEDULER_POLICY,
    TIMEZONE,
    US_BATCH_WINDOWS,
    US_SCORING_WEIGHTS,
)
from app.us_stock.watchlist import normalize_us_watchlist_rows

GENERATED_AT = "2026-07-10T00:00:00+08:00"


def us_stock_batch_input_example() -> dict[str, Any]:
    return {
        "schema_version": "us_stock_dedicated_batch_input_v1",
        "task_id": "AI-DEV-168",
        "generated_at": GENERATED_AT,
        "source_google_sheet": {
            "same_google_sheet_file": True,
            "tw_watchlist_sheet": "工作表1",
            "us_watchlist_sheet": "工作表2",
            "google_sheet_id_required_at_runtime": True,
            "google_sheet_api_called_in_validation": False,
        },
        "sample_us_watchlist_rows": [
            {"ticker": "AAPL", "company_name": "Apple Inc.", "exchange": "NASDAQ", "enabled": "TRUE", "note": "large cap technology"},
            {"symbol": "MSFT", "name": "Microsoft Corp.", "exchange": "NASDAQ", "enabled": "yes"},
            {"symbol": "NVDA", "name": "NVIDIA Corp.", "exchange": "NASDAQ", "enabled": "1"},
            {"symbol": "TSLA", "name": "Tesla Inc.", "exchange": "NASDAQ", "enabled": "FALSE", "note": "disabled sample row"},
        ],
        "market_data_fixture": {
            "source_id": "yfinance_yahoo",
            "source_role": "market_external_reference",
            "external_api_called": False,
            "items": {},
        },
        "news_fixture": {
            "source_policy": "copyright_safe_bilingual_summary_contract",
            "external_api_called": False,
            "items": {},
        },
    }


def _enabled_watchlist(input_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = input_payload.get("sample_us_watchlist_rows", [])
    return [entry for entry in normalize_us_watchlist_rows(rows) if entry.get("enabled") is True]


def _market_data_contract(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "market": DEFAULT_MARKET,
        "currency": DEFAULT_CURRENCY,
        "source_id": "yfinance_yahoo",
        "source_role": "market_external_reference",
        "source_quality_classification": "external_reference_not_official_disclosure",
        "current_or_last_price": None,
        "previous_close": None,
        "open": None,
        "high": None,
        "low": None,
        "close": None,
        "volume": None,
        "pre_market_price": None,
        "post_market_price": None,
        "exchange_metadata": None,
        "data_status": "missing_data_external_api_disabled",
        "missing_fields": ["ohlcv", "pre_market_price", "post_market_price"],
        "failure_mode": "pm_readable_missing_data_state",
    }


def _technical_contract(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "market": DEFAULT_MARKET,
        "technical_score": None,
        "technical_summary": "資料待接：V1 foundation 未呼叫外部行情，保留 MA/RSI/MACD/Bollinger/volume/range contract。",
        "signal_light": "insufficient_data",
        "indicators": {
            "ma5": None,
            "ma20": None,
            "ma60": None,
            "rsi14": None,
            "macd": None,
            "bollinger": None,
            "volume_moving_average": None,
            "range_position": None,
            "trend_momentum_summary": "insufficient_data",
        },
        "excluded_taiwan_assumptions": ["taiwan_price_limit", "twd_formatting", "twse_trading_day", "chip_score"],
    }


def _news_contract(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "market": DEFAULT_MARKET,
        "news_status": "not_configured",
        "preferred_sources": [
            "company_official_ir_sec_earnings_release_transcript",
            "google_news_rss_us_symbol",
            "yfinance_news",
            "factiva_optional_placeholder",
        ],
        "bilingual_items": [
            {
                "english_headline": None,
                "english_excerpt": None,
                "chinese_translation": "重大新聞資料待接。",
                "vocabulary": [],
                "investment_reading": "尚未找到可安全引用的英文新聞或公司資訊 artifact。",
                "copyright_policy": "headline_or_short_excerpt_only_no_full_article_copy",
            }
        ],
    }


def _scoring_contract(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "market": DEFAULT_MARKET,
        "total_score": None,
        "rating": "資料待接",
        "action": "保守觀望",
        "confidence": "insufficient_data",
        "rationale": "US scoring V1 is isolated from Taiwan chip weights and waits for US market/news data.",
        "weight_version": "us_scoring_v1_foundation",
        "weights": US_SCORING_WEIGHTS,
        "excluded_taiwan_dimensions": ["taiwan_chip", "twse_institutional", "margin_trading"],
    }


def _prediction_contract(symbol: str, window: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "market": DEFAULT_MARKET,
        "currency": DEFAULT_CURRENCY,
        "prediction_window": US_BATCH_WINDOWS[window]["prediction_window"],
        "generated_at": GENERATED_AT,
        "current_or_last_price": None,
        "predicted_session_high": None,
        "predicted_session_low": None,
        "predicted_next_session_high": None,
        "predicted_next_session_low": None,
        "one_month_trend": "uncertain",
        "three_month_trend": "uncertain",
        "confidence_score": None,
        "confidence_level": "insufficient_data",
        "prediction_rationale": "insufficient_data: yfinance/Yahoo external API disabled in deterministic foundation validation.",
        "prediction_status": "insufficient_data",
        "intraday_adjusted": window == "us_intraday_2300",
        "source_evidence": ["yfinance_yahoo_market_external_reference_contract"],
        "missing_fields": ["current_or_last_price", "historical_ohlcv", "session_actual"],
        "model_version": "us_deterministic_baseline_contract_v1",
    }


def _review_contract(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "market": DEFAULT_MARKET,
        "review_window": "us_post_close_review_0630",
        "snapshot_prediction_artifact_ref": "artifacts/runtime/us_stock_prediction_snapshot_latest.json",
        "actual_outcome_status": "pending_or_unavailable",
        "direction_hit": None,
        "high_low_error": {"high_error_abs": None, "low_error_abs": None, "high_error_pct": None, "low_error_pct": None},
        "confidence_calibration": "pending_insufficient_actuals",
        "rating_action_effectiveness": "pending_insufficient_actuals",
        "pending_policy": "keep_review_pending_until_us_session_actual_available",
        "review_status": "pending",
    }


def _dashboard_card(entry: dict[str, Any], window: str) -> dict[str, Any]:
    symbol = entry["symbol"]
    return {
        "card_id": f"us_stock_{symbol}_{window}",
        "market_label": "美股",
        "window_label": {
            "us_pre_market_2000": "美股盤前 20:00",
            "us_intraday_2300": "美股盤中 23:00",
            "us_post_close_review_0630": "美股檢討 06:30",
        }[window],
        "symbol": symbol,
        "name": entry.get("name"),
        "price": None,
        "currency": DEFAULT_CURRENCY,
        "rating": "資料待接",
        "action": "保守觀望",
        "confidence": "insufficient_data",
        "session_predicted_high_low": "資料待接",
        "next_session_predicted_high_low": "資料待接",
        "one_month_trend": "不明朗",
        "three_month_trend": "不明朗",
        "latest_status": "US batch foundation ready; market data not fetched in validation.",
        "bilingual_news_snippet": {
            "english_headline": None,
            "chinese_translation": "重大新聞資料待接",
            "investment_reading": "無安全新聞 artifact 時不產生假新聞。",
        },
    }


def build_us_stock_batch_artifact(input_payload: dict[str, Any] | None = None, window: str = "us_pre_market_2000") -> dict[str, Any]:
    if window not in US_BATCH_WINDOWS:
        raise ValueError(f"unsupported US batch window: {window}")
    payload = input_payload or us_stock_batch_input_example()
    entries = _enabled_watchlist(payload)
    stock_symbols = [entry["symbol"] for entry in entries]
    return {
        "schema_version": "us_stock_dedicated_batch_lifecycle_v1",
        "artifact_type": "us_stock_batch_lifecycle",
        "task_id": "AI-DEV-168",
        "generated_at": GENERATED_AT,
        "window": window,
        "window_metadata": {"window_key": window, **US_BATCH_WINDOWS[window], "timezone": TIMEZONE},
        "market": DEFAULT_MARKET,
        "currency": DEFAULT_CURRENCY,
        "source_watchlist": {
            "same_google_sheet_file": True,
            "tw_watchlist_sheet": "工作表1",
            "us_watchlist_sheet": "工作表2",
            "source_sheet": "工作表2",
            "source_kind": "google_sheet_us_watchlist",
            "enabled_symbol_count": len(entries),
            "symbols": stock_symbols,
        },
        "us_watchlist": entries,
        "market_data_source_contract": {
            "primary_source": "yfinance_yahoo",
            "role": "market_external_reference",
            "not_official_disclosure_source": True,
            "external_api_called": False,
            "graceful_fallback": "symbol_missing_data_does_not_fail_batch",
            "items": [_market_data_contract(symbol) for symbol in stock_symbols],
        },
        "technical_analysis_contract": [_technical_contract(symbol) for symbol in stock_symbols],
        "news_company_info_contract": [_news_contract(symbol) for symbol in stock_symbols],
        "scoring_contract": {
            "market": DEFAULT_MARKET,
            "weight_version": "us_scoring_v1_foundation",
            "weights": US_SCORING_WEIGHTS,
            "tw_scoring_formula_reused": False,
            "items": [_scoring_contract(symbol) for symbol in stock_symbols],
        },
        "prediction_contract": {
            "market": DEFAULT_MARKET,
            "window": window,
            "items": [_prediction_contract(symbol, window) for symbol in stock_symbols],
        },
        "prediction_review_contract": {
            "market": DEFAULT_MARKET,
            "review_window": "us_post_close_review_0630",
            "reviewable_stock_count": len(entries) if window == "us_post_close_review_0630" else 0,
            "reviewed_stock_count": 0,
            "skipped_stock_count": len(entries),
            "items": [_review_contract(symbol) for symbol in stock_symbols],
        },
        "dashboard_ready_contract": {
            "market_label": "美股",
            "sections": ["美股盤前 20:00", "美股盤中 23:00", "美股檢討 06:30"],
            "cards": [_dashboard_card(entry, window) for entry in entries],
        },
        "report_ready_contract": {
            "email_summary_candidate": True,
            "line_short_reminder_candidate": True,
            "bilingual_news_support": True,
            "full_report_renderer_not_activated": True,
        },
        "delivery_policy": DELIVERY_POLICY,
        "scheduler_contract": {"windows": US_BATCH_WINDOWS, **SCHEDULER_POLICY},
        "market_separation_policy": {
            "tw_loader_sheet": "工作表1",
            "us_loader_sheet": "工作表2",
            "us_symbols_to_shioaji": False,
            "us_symbols_to_twse": False,
            "us_symbols_to_taiwan_chip_modules": False,
            "us_symbols_to_taiwan_margin_modules": False,
            "tw_four_window_flows_modified": False,
        },
        "safety_policy": SAFETY_POLICY,
        "known_limitations": [
            "V1 does not activate runtime cron/systemd scheduler.",
            "V1 does not call yfinance/Yahoo or Google Sheet APIs during validation.",
            "V1 does not send LINE/Email and does not publish production US reports.",
            "US prediction values remain null when offline fixture data is insufficient.",
        ],
    }
