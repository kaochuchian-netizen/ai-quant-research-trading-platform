#!/usr/bin/env python3
"""Semantic acceptance matrix for AI-DEV-203 (no network or writes)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.market.instrument_master import instrument_metadata, load_instrument_master
from app.market.tw_history_admission import public_admission, validate_history_candidate
from app.runtime.intelligence_quality import (
    FAILURE_REASONS, completeness_v2, intelligence_health,
    semantic_degradation, validate_no_lookahead_v2,
)
from app.us_stock.institutional_research import build_bundle
from app.us_stock.market_context_contract import canonical_ticker, normalize_us_market_context

OBSERVED = "2026-08-07T20:00:00+08:00"
TW_SYMBOLS = ("2330", "2337", "2353", "6873", "2305", "4743", "1409", "00878", "009816")


def production_us_context() -> dict:
    values = {"SPY": .05, "QQQ": .08, "SOXX": 1.42, "DIA": -.1, "^VIX": -.3}
    return {
        "items": {symbol: {
            "label": symbol, "ok": True, "last_price": 100 + change,
            "previous_close": 100, "change_pct": change, "error": None,
            "source_timestamp": OBSERVED,
            "premarket": {"price": 100 + change, "change_pct": change,
                          "timestamp": OBSERVED, "source": "yfinance",
                          "freshness": "fresh", "availability": "available"},
        } for symbol, change in values.items()},
        "market_environment_score": 50, "market_regime": "neutral",
        "risk_environment": "normal", "source_timestamp": OBSERVED,
    }


def production_shape_fixture() -> dict:
    return {
        "fixture_class": "PRODUCTION_SHAPE_FIXTURE",
        "raw_schema_identity": "yfinance_us_context_items_v1",
        "raw_schema_version": 1,
        "payload": production_us_context(),
    }


def history(periods: int, *, end: str = "2026-08-11") -> pd.DataFrame:
    close = pd.Series([100 + index * .2 for index in range(periods)], dtype=float)
    return pd.DataFrame({
        "date": pd.bdate_range(end=end, periods=periods), "open": close,
        "high": close + 1, "low": close - 1, "close": close + .2,
        "volume": [1000 + index for index in range(periods)],
    })


def check(name: str, condition: bool, failures: list[str]) -> None:
    if not condition:
        failures.append(name)


def main() -> int:
    failures: list[str] = []
    fixture = production_shape_fixture()
    raw = fixture["payload"]
    canonical = normalize_us_market_context(raw)
    legacy = normalize_us_market_context({"spy": {"change_pct": .1}, "qqq": {}, "soxx": {}})
    research = {"sec": {"ok": False}, "official_sources": {}, "fundamentals": {}, "earnings": {}, "material_news": {"items": []}}
    bundle = build_bundle("NVDA", research, raw, OBSERVED)
    refs = {item.get("source_reference") for item in bundle["evidence"]}
    check("us_production_shape_valid", canonical["normalization_status"] == "VALID", failures)
    check("us_semantic_values", canonical_ticker(canonical, "SOXX")["change_pct"] == 1.42, failures)
    check("us_wrong_shape_rejected", legacy["normalization_status"] == "FAILED" and legacy["failure_reason"] == "SCHEMA_MISMATCH", failures)
    check("us_rre_consumes_context", {"SPY", "QQQ", "SOXX"}.issubset(refs), failures)
    check("us_sector_not_flattened", bundle["research_intelligence_v2"]["market_sector_context"]["sector"] == "bullish", failures)
    check("us_context_provenance", all((item.get("provenance") or {}).get("canonical_market_context") == "us_market_context_v2" for item in bundle["evidence"] if item.get("source_reference") in {"SPY", "QQQ", "SOXX"}), failures)

    short = validate_history_candidate(history(19, end="2026-07-24"), source="existing_historical_csv", target_date="2026-08-11")
    valid = validate_history_candidate(history(60, end="2026-08-10"), source="shioaji_kbars", target_date="2026-08-11")
    provider_short = validate_history_candidate(history(19, end="2026-08-10"), source="shioaji_kbars", target_date="2026-08-11")
    bad_geometry_frame = history(60, end="2026-08-10"); bad_geometry_frame.loc[3, "high"] = bad_geometry_frame.loc[3, "low"] - 1
    bad_geometry = validate_history_candidate(bad_geometry_frame, source="yfinance:2330.TW", target_date="2026-08-11")
    duplicate_frame = pd.concat([history(60, end="2026-08-10"), history(60, end="2026-08-10").tail(1)], ignore_index=True)
    duplicate = validate_history_candidate(duplicate_frame, source="existing_historical_csv", target_date="2026-08-11")
    future = validate_history_candidate(history(60, end="2026-08-12"), source="yfinance:2330.TW", target_date="2026-08-11")
    check("tw_stale_19_rejected", not short["admission_success"] and {"STALE", "INSUFFICIENT_LOOKBACK"}.issubset(short["reason_codes"]), failures)
    check("tw_valid_60_admitted", valid["status"] == "VALID" and valid["admission_success"], failures)
    check("shioaji_success_not_admission", provider_short["fetch_success"] and not provider_short["admission_success"] and provider_short["status"] == "INSUFFICIENT_LOOKBACK", failures)
    check("invalid_geometry_rejected", bad_geometry["status"] == "INVALID_GEOMETRY", failures)
    check("duplicate_rejected", duplicate["status"] == "DUPLICATE_DATE", failures)
    check("future_bar_rejected", future["status"] == "FUTURE_DATA", failures)
    check("public_admission_no_dataframe", "normalized" not in public_admission(valid), failures)

    master = load_instrument_master()
    metadata = [instrument_metadata("TW", symbol) for symbol in TW_SYMBOLS]
    etfs = [row for row in metadata if row["instrument_type"] == "etf"]
    companies = [row for row in metadata if row["instrument_type"] == "company"]
    check("instrument_master_complete", len(metadata) == 9 and all(row["status"] == "AVAILABLE" for row in metadata), failures)
    check("taxonomy_corrected_6873", instrument_metadata("TW", "6873")["industry"] == "能源服務", failures)
    check("taxonomy_corrected_2305", instrument_metadata("TW", "2305")["industry"] == "光電業", failures)
    check("etf_applicability", all(row["fundamentals_applicability"] == "NOT_APPLICABLE" for row in etfs), failures)
    check("company_applicability", all(row["fundamentals_applicability"] == "APPLICABLE" for row in companies), failures)
    check("adr_only_mapped", instrument_metadata("TW", "2330")["adr_symbol"] == "TSM" and all(row["adr_applicability"] == "NOT_APPLICABLE" for row in metadata if row["symbol"] != "2330"), failures)
    check("taxonomy_provenance", all(row.get("source") and row.get("effective_date") for row in metadata), failures)

    timeline = {
        "prediction_generated_at": "2026-08-11T07:00:01+08:00",
        "prediction_data_cutoff": "2026-08-11T07:00:00+08:00",
        "last_input_market_timestamp": "2026-08-11T06:59:59+08:00",
        "first_outcome_observation_timestamp": "2026-08-11T09:00:00+08:00",
        "outcome_data_cutoff": "2026-08-11T13:30:00+08:00",
        "review_generated_at": "2026-08-11T15:00:00+08:00",
    }
    check("no_lookahead_valid", validate_no_lookahead_v2(timeline)["status"] == "PASS", failures)
    contaminated = dict(timeline); contaminated["last_input_market_timestamp"] = "2026-08-11T13:30:00+08:00"
    check("future_input_rejected", "INPUT_AFTER_PREDICTION_CUTOFF" in validate_no_lookahead_v2(contaminated)["reason_codes"], failures)
    later_intraday = dict(timeline); later_intraday["prediction_data_cutoff"] = "2026-08-11T10:00:00+08:00"; later_intraday["first_outcome_observation_timestamp"] = "2026-08-11T09:30:00+08:00"
    check("later_intraday_rejected", "OUTCOME_NOT_AFTER_PREDICTION" in validate_no_lookahead_v2(later_intraday)["reason_codes"], failures)
    no_offset = dict(timeline); no_offset["prediction_generated_at"] = "2026-08-11T07:00:01"
    malformed = dict(timeline); malformed["prediction_generated_at"] = "not-a-time"
    check("timezone_required", any("TIMEZONE_REQUIRED" in code for code in validate_no_lookahead_v2(no_offset)["reason_codes"]), failures)
    check("malformed_timestamp_rejected", any("MALFORMED_TIMESTAMP" in code for code in validate_no_lookahead_v2(malformed)["reason_codes"]), failures)

    completeness = completeness_v2(market_data="COMPLETE", technical="COMPLETE", research="PARTIAL", decision_input="SUFFICIENT", prediction_input="SUFFICIENT", research_score=43, missing_categories=["macro", "news"])
    degraded = semantic_degradation(quote_total=9, quote_available=9, history_claimed_valid=9, technical_executable=0, completeness=completeness)
    disconnected = semantic_degradation(provider_market_values=True, research_market_available=False)
    health = intelligence_health(runtime_status="SUCCESS", data_quality_status="DEGRADED", research_status="DEGRADED", prediction_status="AVAILABLE", decision_status="NO_TRADE", degradation=degraded)
    check("completeness_split", completeness["market_data_completeness"] == "COMPLETE" and completeness["research_evidence_completeness"] == "PARTIAL" and not completeness["universal_data_complete"], failures)
    check("quote_technical_degradation", "HISTORY_VALID_BUT_TECHNICAL_EMPTY" in degraded["reason_codes"], failures)
    check("market_consumer_degradation", "PROVIDER_DATA_CONSUMER_DISCONNECTED" in disconnected["reason_codes"], failures)
    check("runtime_intelligence_separate", health["runtime_status"] == "SUCCESS" and health["intelligence_status"] == "DEGRADED" and not health["runtime_success_is_intelligence_success"], failures)
    check("failure_taxonomy", {"SCHEMA_MISMATCH", "STALE", "INSUFFICIENT_LOOKBACK", "INVALID_GEOMETRY", "FUTURE_DATA", "CONSUMER_DISCONNECTED"}.issubset(FAILURE_REASONS), failures)
    check("fixture_evidence_level", fixture.get("fixture_class") == "PRODUCTION_SHAPE_FIXTURE", failures)
    check("fixture_schema_identity", fixture.get("raw_schema_identity") == "yfinance_us_context_items_v1" and fixture.get("raw_schema_version") == 1, failures)
    check("fixture_raw_provider_shape", isinstance((fixture.get("payload") or {}).get("items"), dict) and {"SPY", "QQQ", "SOXX"}.issubset(fixture["payload"]["items"]), failures)

    result = {
        "validator": "validate_ai_dev_203_cross_market_contract_guardrails_v1",
        "task_id": "AI-DEV-203", "status": "PASS" if not failures else "FAIL",
        "evidence_level": "PRODUCTION_SHAPE_FIXTURE", "checks": 36,
        "failures": failures,
        "acceptance": {
            "us_market_context": canonical, "legacy_shape": legacy,
            "tw_stale_19": public_admission(short), "tw_valid_60": public_admission(valid),
            "shioaji_short_success": public_admission(provider_short),
            "semantic_degradation": degraded, "runtime_intelligence_health": health,
            "instrument_master_version": master["version"],
        },
        "safety": {"network": False, "writes": False, "notifications": False, "trading": False},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
