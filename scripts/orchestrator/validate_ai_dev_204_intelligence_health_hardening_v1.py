#!/usr/bin/env python3
"""AI-DEV-204 semantic acceptance and mutation matrix (pure, deterministic)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.market.instrument_master import instrument_metadata, validate_instrument_master_coverage
from app.market.tw_history_admission import expected_completed_session, validate_history_candidate
from app.runtime.intelligence_quality import (
    decision_input_readiness, intelligence_health, intelligence_readiness_v1,
    resolve_outcome_timestamp, semantic_degradation, validate_intelligence_readiness,
    validate_no_lookahead_v2,
)
from app.runtime.validator_registry import evaluate_validator_entry, load_validator_registry, validate_validator_registry
from app.us_stock.market_context_contract import normalize_us_market_context


def history(periods: int, end: str) -> pd.DataFrame:
    close = pd.Series([100.0 + index * .2 for index in range(periods)])
    return pd.DataFrame({
        "date": pd.bdate_range(end=end, periods=periods), "open": close,
        "high": close + 1, "low": close - 1, "close": close + .2,
        "volume": [1000 + index for index in range(periods)],
    })


def us_production_fixture() -> dict:
    return {
        "fixture_class": "PRODUCTION_SHAPE_FIXTURE",
        "raw_schema_identity": "yfinance_us_context_items_v1", "raw_schema_version": 1,
        "payload": {"items": {ticker: {
            "label": ticker, "ok": True, "last_price": 100 + move,
            "previous_close": 100, "change_pct": move, "error": None,
            "source_timestamp": "2026-08-07T20:00:00+08:00",
            "premarket": {"price": 100 + move, "change_pct": move, "timestamp": "2026-08-07T20:00:00+08:00", "source": "yfinance", "freshness": "fresh", "availability": "available"},
        } for ticker, move in {"SPY": .05, "QQQ": .08, "SOXX": 1.42}.items()}},
    }


def check(name: str, condition: bool, checks: dict[str, bool]) -> None:
    checks[name] = bool(condition)


def readiness(*, total: int, market: int, history_count: int, technical: int, research: int, baseline: int, full: int, decision_rows: list[dict]) -> dict:
    return intelligence_readiness_v1(
        runtime_status="SUCCESS", total_symbols=total, market_ready=market,
        history_ready=history_count, technical_ready=technical, research_ready=research,
        baseline_prediction_ready=baseline, full_prediction_ready=full,
        decision_required_inputs=decision_rows,
    )


def main() -> int:
    checks: dict[str, bool] = {}
    decisions_missing = [{"required_inputs": {"market_data": True, "technical_evidence": False, "research_evidence": False}}]
    decisions_ready = [{"required_inputs": {"market_data": True, "technical_evidence": True, "research_evidence": True}}]

    # A/B: decision health is derived from declared inputs, never hard-coded.
    decision_a = decision_input_readiness(decisions_missing)
    decision_b = decision_input_readiness(decisions_ready)
    check("A_decision_not_hardcoded", decision_a["readiness"] == "INSUFFICIENT" and decision_a["ready_symbols"] == 0, checks)
    check("B_decision_derived_sufficient", decision_b["readiness"] == "SUFFICIENT" and decision_b["ready_symbols"] == 1, checks)

    # C-F: baseline/full distinction and denominator-preserving aggregation.
    baseline_only = readiness(total=1, market=1, history_count=1, technical=0, research=0, baseline=1, full=0, decision_rows=decisions_missing)
    full_ready = readiness(total=1, market=1, history_count=1, technical=1, research=1, baseline=1, full=1, decision_rows=decisions_ready)
    one_of_nine = readiness(total=9, market=9, history_count=1, technical=1, research=1, baseline=1, full=1, decision_rows=decisions_ready + decisions_missing * 8)
    nine_of_nine = readiness(total=9, market=9, history_count=9, technical=9, research=9, baseline=9, full=9, decision_rows=decisions_ready * 9)
    check("C_baseline_not_full", baseline_only["baseline_prediction"]["readiness_class"] == "BASELINE_EVALUABLE" and baseline_only["full_prediction"]["readiness_class"] == "INSUFFICIENT", checks)
    check("D_full_prediction_ready", full_ready["baseline_prediction"]["status"] == "COMPLETE" and full_ready["full_prediction"]["readiness_class"] == "FULL_READY", checks)
    check("E_one_of_nine_partial", one_of_nine["baseline_prediction"]["status"] == "PARTIAL" and one_of_nine["baseline_prediction"]["ready_symbols"] == 1 and one_of_nine["baseline_prediction"]["total_applicable_symbols"] == 9, checks)
    check("F_nine_of_nine_complete", nine_of_nine["full_prediction"]["status"] == "COMPLETE" and nine_of_nine["decision_input"]["status"] == "SUFFICIENT", checks)

    # G/H: expected gaps are not structural; consumer disconnect is.
    optional = semantic_degradation(optional_source_gaps=["ANALYST_NOT_CONFIGURED"])
    disconnected = semantic_degradation(provider_market_values=True, research_market_available=False)
    check("G_optional_gap_not_structural", optional["status"] == "HEALTHY_WITH_GAPS" and optional["findings"][0]["category"] == "OPTIONAL_SOURCE_UNAVAILABLE", checks)
    check("H_consumer_disconnect_structural", disconnected["status"] == "DEGRADED" and disconnected["findings"][0]["category"] == "CONSUMER_DISCONNECTED", checks)

    # I-K: session-aware freshness and future-data rejection.
    friday = validate_history_candidate(history(60, "2026-08-14"), source="fixture", target_date="2026-08-17")
    holidays = {f"2026-02-{day:02d}" for day in range(16, 21)}
    long_holiday = validate_history_candidate(history(60, "2026-02-13"), source="fixture", target_date="2026-02-23", holiday_dates=holidays)
    future = validate_history_candidate(history(60, "2026-08-17"), source="fixture", target_date="2026-08-17")
    check("I_weekend_freshness", friday["status"] == "VALID" and friday["expected_latest_session"] == "2026-08-14", checks)
    check("J_long_holiday_freshness", long_holiday["status"] == "VALID" and expected_completed_session("2026-02-23", holiday_dates=holidays).isoformat() == "2026-02-13", checks)
    check("K_future_bar_rejected", future["status"] == "FUTURE_DATA", checks)

    # L/M: actual evidence wins; fallback remains explicit.
    actual_time = resolve_outcome_timestamp({"first_observation_timestamp": "2026-08-11T09:03:00+08:00", "first_bar_timestamp": "2026-08-11T09:01:00+08:00"}, session_fallback="2026-08-11T09:00:00+08:00")
    fallback_time = resolve_outcome_timestamp({}, session_fallback="2026-08-11T09:00:00+08:00")
    check("L_actual_timestamp_preferred", actual_time["timestamp_method"] == "ACTUAL_EVIDENCE" and actual_time["timestamp"].endswith("09:03:00+08:00"), checks)
    check("M_fallback_explicit", fallback_time["timestamp_method"] == "SESSION_FALLBACK" and fallback_time["reason_code"], checks)

    # N/O: formal universe subset and applicability.
    formal = validate_instrument_master_coverage("TW")
    missing_symbol = validate_instrument_master_coverage("TW", ["2330", "TEST_MISSING"])
    etf = instrument_metadata("TW", "00878")
    check("N_formal_watchlist_covered", formal["status"] == "PASS" and missing_symbol["status"] == "FAIL", checks)
    check("O_etf_not_applicable", etf["instrument_type"] == "etf" and etf["fundamentals_applicability"] == "NOT_APPLICABLE", checks)

    # P: production-shape assertion fails on a real schema mutation.
    fixture = us_production_fixture()
    canonical = normalize_us_market_context(fixture["payload"])
    mutated = {"legacy_items": fixture["payload"]["items"]}
    rejected = normalize_us_market_context(mutated)
    check("P_production_shape_mutation_rejected", canonical["normalization_status"] == "VALID" and rejected["normalization_status"] == "FAILED" and rejected["failure_reason"] == "SCHEMA_MISMATCH", checks)

    # Q/R: lifecycle registry fails closed and superseded validators link replacement.
    registry = load_validator_registry(); entries = {row["validator_id"]: row for row in registry["validators"]}
    def raising_runner(_path: Path) -> dict:
        raise RuntimeError("fixture exception")
    active_exception = evaluate_validator_entry(entries["ai_dev_203_contract_guardrails"], raising_runner)
    superseded = evaluate_validator_entry(entries["ai_dev_115a_preopen_incident"])
    check("Q_active_exception_fails", active_exception["status"] == "FAIL" and active_exception["reason"] == "ACTIVE_VALIDATOR_EXCEPTION", checks)
    check("R_superseded_has_replacement", superseded["status"] == "SUPERSEDED" and superseded["replacement"] == "tw_0700_missing_batch_recovery_v1", checks)

    # S: process success cannot promote degraded intelligence.
    degraded_ready = readiness(total=1, market=1, history_count=0, technical=0, research=0, baseline=0, full=0, decision_rows=decisions_missing)
    gap = semantic_degradation(insufficient_data=["INSUFFICIENT_LOOKBACK"])
    health = intelligence_health(runtime_status="SUCCESS", data_quality_status="DEGRADED", research_status="INSUFFICIENT", prediction_status="INSUFFICIENT", decision_status="INSUFFICIENT", degradation=gap, readiness=degraded_ready)
    check("S_runtime_does_not_promote", health["runtime_status"] == "SUCCESS" and health["intelligence_status"] == "DEGRADED" and not health["runtime_success_is_intelligence_success"], checks)

    # Required mutations: each bad state must be rejected by a semantic gate.
    fake_decision = json.loads(json.dumps(baseline_only)); fake_decision["decision_input"]["status"] = "SUFFICIENT"
    fake_universe = json.loads(json.dumps(one_of_nine)); fake_universe["baseline_prediction"]["status"] = "COMPLETE"
    fake_full = json.loads(json.dumps(baseline_only)); fake_full["full_prediction"].update({"status": "COMPLETE", "ready_symbols": 1, "readiness_class": "FULL_READY"})
    check("negative_hardcoded_decision_rejected", validate_intelligence_readiness(fake_decision)["status"] == "FAIL", checks)
    check("negative_one_of_nine_complete_rejected", validate_intelligence_readiness(fake_universe)["status"] == "FAIL", checks)
    check("negative_baseline_as_full_rejected", validate_intelligence_readiness(fake_full)["status"] == "FAIL", checks)
    timeline = {
        "prediction_generated_at":"2026-08-11T07:00:01+08:00", "prediction_data_cutoff":"2026-08-11T07:00:00+08:00",
        "last_input_market_timestamp":"2026-08-11T06:59:59+08:00", "first_outcome_observation_timestamp":"2026-08-11T09:03:00+08:00",
        "outcome_data_cutoff":"2026-08-11T13:30:00+08:00", "review_generated_at":"2026-08-11T15:00:00+08:00",
        "timestamp_method":"ACTUAL_EVIDENCE", "prediction_effective_trading_date":"2026-08-11", "outcome_effective_trading_date":"2026-08-11",
    }
    future_timeline = dict(timeline); future_timeline["last_input_market_timestamp"] = "2026-08-11T13:30:00+08:00"
    naive_timeline = dict(timeline); naive_timeline["first_outcome_observation_timestamp"] = "2026-08-11T09:03:00"
    wrong_date = dict(timeline); wrong_date["outcome_effective_trading_date"] = "2026-08-12"
    check("negative_future_data_rejected", validate_no_lookahead_v2(future_timeline)["status"] == "FAIL", checks)
    check("negative_naive_timestamp_rejected", validate_no_lookahead_v2(naive_timeline)["status"] == "FAIL", checks)
    check("negative_wrong_session_rejected", "TRADING_DATE_MISMATCH" in validate_no_lookahead_v2(wrong_date)["reason_codes"], checks)
    check("validator_registry_integrity", validate_validator_registry()["status"] == "PASS", checks)

    failures = [name for name, passed in checks.items() if not passed]
    result = {
        "validator": "validate_ai_dev_204_intelligence_health_hardening_v1",
        "task_id": "AI-DEV-204", "status": "PASS" if not failures else "FAIL",
        "evidence_level": "PRODUCTION_SHAPE_FIXTURE_AND_SYNTHETIC_NEGATIVE",
        "checks": checks, "failures": failures,
        "acceptance_cases": {letter: "PASS" for letter in "ABCDEFGHIJKLMNOPQRS"} if not failures else {},
        "safety": {"network": False, "writes": False, "notifications": False, "trading": False},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
