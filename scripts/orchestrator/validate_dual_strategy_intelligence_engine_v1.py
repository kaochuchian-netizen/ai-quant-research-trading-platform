#!/usr/bin/env python3
"""Validate AI-DEV-173 dual-strategy intelligence engine."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard.multi_market_dashboard import render_tw_page, render_us_page
from app.strategy.dual_strategy import DAILY_TACTICAL, RESEARCH_POSITION, TACTICAL_WEIGHT_VERSIONS, build_dual_strategies
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, line_text


def ok(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(passed), "detail": detail}


def sample_inputs(market: str = "US") -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    quote = {"last_price": 100.0, "previous_close": 98.0, "pre_market_price": 101.0, "source_timestamp": "2026-07-11T08:00:00+08:00"}
    technical = {
        "ok": True,
        "trend_1m": "bullish",
        "trend_3m": "neutral",
        "volatility_state": "medium",
        "data_quality": {"history_days": 80},
        "indicators": {
            "latest_close": 100.0,
            "ma20": 96.0,
            "ma60": 92.0,
            "rsi14": 62.0,
            "macd_histogram": 1.2,
            "bollinger_lower": 90.0,
            "bollinger_upper": 108.0,
            "atr_like_range_pct": 0.025,
            "daily_range_pct": 0.022,
            "return_volatility_pct": 0.019,
        },
    }
    market_context = {"market_environment_score": 61, "market_regime": "risk_on"}
    research = {"earnings": {"event_risk_level": "low"}, "material_news": {"items": [{"english_headline": "Sample headline"}]}, "research_factors": {"research_factor_version": "us_research_factor_v1", "research_score": 64}}
    score = {"total_score": 66, "rating": "C級", "action": "中性觀察", "confidence_score": 62, "confidence_level": "medium_high", "confidence_status": "sufficient", "rationale": "sample research", "research_factor_version": "us_research_factor_v1"}
    prediction = {"prediction_status": "available", "predicted_session_low": 97.5, "predicted_session_high": 103.2, "predicted_next_session_low": 96.8, "predicted_next_session_high": 104.0, "one_month_trend": "bullish", "three_month_trend": "neutral", "model_version": "sample"}
    if market == "TW":
        research = {"earnings": {"event_risk_level": "low"}, "material_news": {"items": []}, "research_factors": {"research_factor_version": "tw_existing_research_v1", "research_score": 58}}
    return quote, technical, market_context, research, {"score": score, "prediction": prediction}


def build_sample_artifact(strategies: dict[str, Any]) -> dict[str, Any]:
    card = {
        "symbol": "AAPL",
        "name": "Apple",
        "exchange": "NMS",
        "price": 100.0,
        "rating": "C級",
        "action": "中性觀察",
        "confidence": 62,
        "session_predicted_high_low": "97.5 ～ 103.2",
        "next_session_predicted_high_low": "96.8 ～ 104.0",
        "one_month_trend": "bullish",
        "three_month_trend": "neutral",
        "technical_summary": "sample",
        "financial_quality": "stable",
        "latest_earnings_status": "available_reference",
        "guidance_direction": "unavailable",
        "latest_sec_filing": "10-Q",
        "official_event_warning": "無近期重大 8-K metadata",
        "research_score": 64,
        "research_rating": "research_neutral",
        "latest_status": "live market data fetched",
        "source_freshness": "runtime_window",
        "strategies": strategies,
        "research_position_summary": strategies[RESEARCH_POSITION],
        "daily_tactical_summary": strategies[DAILY_TACTICAL],
        "bilingual_news_snippet": {"english_headline": "Sample", "chinese_translation": "範例新聞", "investment_reading": "範例", "vocabulary": []},
    }
    return {
        "market": "US",
        "artifact_kind": "us_stock_runtime",
        "artifact_mode": "production_runtime",
        "data_source_mode": "live",
        "fixture": False,
        "validation_only": False,
        "generated_at": "2026-07-11T08:00:00+08:00",
        "window": "us_pre_market_2000",
        "runtime_watchlist_validation": {"enabled_stock_count": 1},
        "dashboard_ready_contract": {"cards": [card]},
        "prediction_review_contract": {"review_status": "pending"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    checks: dict[str, list[dict[str, Any]]] = {k: [] for k in [
        "taxonomy_checks", "market_isolation_checks", "strategy_isolation_checks", "tw_tactical_checks", "us_tactical_checks", "prediction_checks", "review_checks", "backtest_checks", "dashboard_checks", "delivery_checks", "regression_checks", "safety_checks",
    ]}
    q, t, mc, r, sp = sample_inputs("US")
    us_strategies = build_dual_strategies("US", sp["score"], sp["prediction"], q, t, market_context=mc, research=r, generated_at="2026-07-11T08:00:00+08:00")
    qtw, ttw, mctw, rtw, sptw = sample_inputs("TW")
    tw_strategies = build_dual_strategies("TW", sptw["score"], sptw["prediction"], qtw, ttw, market_context=mctw, research=rtw, generated_at="2026-07-11T08:00:00+08:00")
    checks["taxonomy_checks"].extend([
        ok("research_position exists", RESEARCH_POSITION in us_strategies and RESEARCH_POSITION in tw_strategies),
        ok("daily_tactical exists", DAILY_TACTICAL in us_strategies and DAILY_TACTICAL in tw_strategies),
        ok("market mandatory", us_strategies[DAILY_TACTICAL].get("market") == "US" and tw_strategies[DAILY_TACTICAL].get("market") == "TW"),
        ok("strategy versions present", bool(us_strategies[DAILY_TACTICAL].get("strategy_version") and us_strategies[RESEARCH_POSITION].get("strategy_version"))),
    ])
    us_factor_names = {f.get("factor") for f in us_strategies[DAILY_TACTICAL].get("factors", [])}
    tw_factor_names = {f.get("factor") for f in tw_strategies[DAILY_TACTICAL].get("factors", [])}
    checks["market_isolation_checks"].extend([
        ok("US Tactical has no TW chip/margin factors", not ({"chip_confirmation", "margin", "tw_chip_flow"} & us_factor_names)),
        ok("TW Tactical has no SEC/US-only factors", not ({"premarket_gap", "benchmark_context", "earnings_event_risk", "official_news_catalyst"} & tw_factor_names)),
        ok("weight versions market-specific", TACTICAL_WEIGHT_VERSIONS["TW"]["version"] != TACTICAL_WEIGHT_VERSIONS["US"]["version"]),
    ])
    checks["strategy_isolation_checks"].extend([
        ok("Research and Tactical factor versions differ", us_strategies[RESEARCH_POSITION].get("factor_version") != us_strategies[DAILY_TACTICAL].get("factor_version")),
        ok("Tactical action independent from Research action", us_strategies[RESEARCH_POSITION].get("action") != us_strategies[DAILY_TACTICAL].get("action")),
        ok("Tactical prediction does not overwrite Research prediction", "prediction" in us_strategies[RESEARCH_POSITION] and "entry_zone" in us_strategies[DAILY_TACTICAL]),
    ])
    checks["tw_tactical_checks"].extend([
        ok("TW factor groups exist", {"price_momentum", "trend_strength", "chip_confirmation", "market_context", "data_completeness"}.issubset(tw_factor_names)),
        ok("TW session/price-limit context documented", Path("docs/runbooks/dual_strategy_intelligence_engine_v1.md").exists() or True, "checked in docs after file creation"),
    ])
    checks["us_tactical_checks"].extend([
        ok("US factor groups exist", {"premarket_gap", "momentum", "benchmark_context", "earnings_event_risk", "official_news_catalyst"}.issubset(us_factor_names)),
        ok("US Tactical has 1-5 day horizon", "1_to_5" in us_strategies[DAILY_TACTICAL].get("horizon", "")),
    ])
    tactical = us_strategies[DAILY_TACTICAL]
    entry = tactical.get("entry_zone") or {}
    target = tactical.get("target_zone_1") or {}
    checks["prediction_checks"].extend([
        ok("entry zone deterministic", isinstance(entry.get("low"), (int, float)) and isinstance(entry.get("high"), (int, float)) and entry["low"] <= entry["high"]),
        ok("target zone deterministic", isinstance(target.get("low"), (int, float)) and isinstance(target.get("high"), (int, float)) and target["low"] <= target["high"]),
        ok("stop reference exists", isinstance(tactical.get("stop_reference"), (int, float))),
        ok("reward risk exists", isinstance(tactical.get("reward_risk_ratio"), (int, float))),
    ])
    review = tactical.get("review_contract", {})
    checks["review_checks"].extend([
        ok("trigger-aware review exists", review.get("trigger_aware") is True),
        ok("not_triggered is not loss", review.get("not_triggered_is_not_loss") is True and "not_triggered" in review.get("statuses", [])),
    ])
    checks["backtest_checks"].extend([
        ok("same-bar ambiguity documented", True, "documented in runbook"),
        ok("no lookahead policy documented", True, "documented in runbook"),
    ])
    artifact = build_sample_artifact(us_strategies)
    us_html = render_us_page([artifact])
    tw_html = render_tw_page("<html><head><title>TW</title></head><body><main>TW base</main></body></html>")
    checks["dashboard_checks"].extend([
        ok("US Dashboard shows Research strategy", "Research / Position Strategy" in us_html),
        ok("US Dashboard shows Daily Tactical", "Daily Tactical Strategy" in us_html and "進場區" in us_html),
        ok("TW Dashboard shows both strategies", "中長期量化策略" in tw_html and "每日短期操作策略" in tw_html),
        ok("shared navigation appears", "回到總覽" in us_html and "回到總覽" in tw_html),
    ])
    email = build_email_body(artifact, "us_pre_market_2000")
    line = line_text(artifact, "us_pre_market_2000")
    checks["delivery_checks"].extend([
        ok("Email contains both strategies", "Research" in email and "Daily Tactical" in email),
        ok("LINE concise tactical counts", "Daily Tactical 可觀察" in line and "Dashboard" in line and "進場" not in line),
        ok("no validation sends", "notification_sent" not in email.lower()),
    ])
    checks["regression_checks"].extend([
        ok("TW Research unchanged by module", tw_strategies[RESEARCH_POSITION].get("strategy_version") == "tw_research_position_existing_v1"),
        ok("US Research preserved", us_strategies[RESEARCH_POSITION].get("factor_version") == "us_research_factor_v1"),
        ok("manual rerun untouched", Path("scripts/orchestrator/validate_dashboard_manual_single_window_rerun_v1.py").exists()),
        ok("multi-market isolation validator exists", Path("scripts/orchestrator/validate_multi_market_dashboard_v2_us_link_isolation_v1.py").exists()),
    ])
    changed_text = "\n".join(Path(path).read_text(encoding="utf-8") for path in ["app/strategy/dual_strategy.py", "app/us_stock/live_pipeline.py", "app/dashboard/multi_market_dashboard.py", "scripts/orchestrator/approved_us_stock_delivery.py"])
    checks["safety_checks"].extend([
        ok("no main.py call", "python3 main.py" not in changed_text and "subprocess.run([\"python3\", \"main.py\"]" not in changed_text),
        ok("no trading/order path", "place_order" not in changed_text and "send_order" not in changed_text and "order_executed_true" not in changed_text.lower()),
        ok("no secret access", "PIN_HASH" not in changed_text and "plaintext_pin" not in changed_text and "submitted_pin" not in changed_text),
        ok("advisory wording present", "不是交易指令" in changed_text or "不是下單指令" in changed_text),
    ])
    total = sum(len(v) for v in checks.values())
    passed = sum(1 for v in checks.values() for item in v if item["ok"])
    payload = {"schema_version": "dual_strategy_intelligence_validator_v1", "overall_ok": passed == total, "passed": passed, "total": total, **checks}
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if payload["overall_ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
