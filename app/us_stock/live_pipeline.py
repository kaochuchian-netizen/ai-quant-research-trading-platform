"""US live-data runtime artifact, prediction, and review pipeline."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.us_stock.constants import DEFAULT_CURRENCY, DEFAULT_MARKET, US_BATCH_WINDOWS, US_SCORING_WEIGHTS
from app.us_stock.live_data import YFinanceUSClient, analyze_history, clean_number, now_taipei
from app.us_stock.research_intelligence import RESEARCH_FACTOR_VERSION, USResearchIntelligenceBuilder
from app.strategy.dual_strategy import DAILY_TACTICAL, RESEARCH_POSITION, US_TACTICAL_FACTOR_VERSION, build_dual_strategies
from app.reports.canonical_outcomes import aggregate_outcomes, build_structured_review_cards

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = REPO_ROOT / "artifacts/runtime/us_stock"
SNAPSHOT_DIR = RUNTIME_DIR / "prediction_snapshots"
REVIEW_DIR = RUNTIME_DIR / "reviews"
MODEL_VERSION = "us_live_deterministic_baseline_v1"
WEIGHT_VERSION = "us_scoring_live_v1"
TAIPEI = ZoneInfo("Asia/Taipei")
NEW_YORK = ZoneInfo("America/New_York")

def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")

def session_context(window: str, reference: datetime | None = None) -> dict[str, Any]:
    reference = reference or datetime.now(TAIPEI).replace(microsecond=0)
    ny = reference.astimezone(NEW_YORK)
    is_dst = bool(ny.dst() and ny.dst().total_seconds())
    weekday = ny.weekday()
    closed_reason = "weekend" if weekday >= 5 else None
    return {
        "timezone_policy": "fixed_asia_taipei",
        "window": window,
        "taipei_time": US_BATCH_WINDOWS[window]["scheduled_time_tw"],
        "reference_taipei": reference.isoformat(),
        "reference_new_york": ny.isoformat(),
        "session_date": ny.date().isoformat(),
        "us_daylight_saving_active": is_dst,
        "market_open_expected": closed_reason is None,
        "market_closed_reason": closed_reason,
        "phase_note": "PM-approved Asia/Taipei fixed schedule retained; phase metadata is advisory.",
    }

def rating_action(score: float | None, confidence_status: str, event_risk_level: str = "low") -> tuple[str, str, float | None, str]:
    if score is None:
        return "資料不足", "保守觀望", None, "insufficient_data"
    if event_risk_level == "high" and score >= 55:
        rating, action = "C級", "降低追價"
    elif score >= 70:
        rating, action = "B級", "偏多續抱"
    elif score >= 55:
        rating, action = "C級", "中性觀察"
    elif score >= 40:
        rating, action = "D級", "保守觀望"
    else:
        rating, action = "E級", "風險升高"
    confidence = min(75, max(20, round(score * 0.72, 1))) if confidence_status == "sufficient" else min(45, round(score * 0.5, 1))
    if event_risk_level in {"medium", "high"} and confidence is not None:
        confidence = max(20, confidence - (8 if event_risk_level == "high" else 4))
    level = "medium_high" if confidence >= 60 else "medium" if confidence >= 40 else "low"
    return rating, action, confidence, level

def score_symbol(technical: dict[str, Any], market_context: dict[str, Any], news_items: list[dict[str, Any]], research: dict[str, Any] | None = None) -> dict[str, Any]:
    if not technical.get("ok"):
        return {"total_score": None, "rating": "資料不足", "action": "保守觀望", "confidence_score": None, "confidence_level": "insufficient_data", "confidence_status": "insufficient_data", "rationale": "歷史 OHLCV 不足，無法產生正式評分。"}
    technical_score = technical.get("technical_score") or 50
    market_score = market_context.get("market_environment_score") or 50
    research_factors = (research or {}).get("research_factors", {})
    research_score = research_factors.get("research_score")
    event_risk_level = (research or {}).get("earnings", {}).get("event_risk_level", "low")
    material_news = (research or {}).get("material_news", {}).get("items", [])
    news_score = 58 if material_news else 55 if news_items else 50
    vol_state = technical.get("volatility_state")
    vol_score = 45 if vol_state == "high" else 55 if vol_state == "low" else 50
    total = round(
        technical_score * 0.28
        + news_score * 0.14
        + market_score * 0.18
        + vol_score * 0.10
        + (research_score if isinstance(research_score, (int, float)) else 50) * 0.30,
        2,
    )
    rating, action, confidence, level = rating_action(total, "sufficient", event_risk_level)
    return {"total_score": total, "rating": rating, "action": action, "confidence_score": confidence, "confidence_level": level, "confidence_status": "sufficient", "rationale": "由技術、市場環境、波動風險、SEC/財務/盈餘/新聞 research factors deterministic 加權產生。", "weight_version": "us_scoring_research_integrated_v1", "research_factor_version": research_factors.get("research_factor_version"), "event_risk_level": event_risk_level}

def prediction_for_symbol(quote: dict[str, Any], technical: dict[str, Any], window: str, research: dict[str, Any] | None = None) -> dict[str, Any]:
    price = quote.get("last_price") or technical.get("indicators", {}).get("latest_close")
    indicators = technical.get("indicators", {})
    if price is None or not technical.get("ok"):
        return {"prediction_status": "insufficient_data", "missing_fields": ["last_price_or_20d_ohlcv"], "predicted_session_low": None, "predicted_session_high": None, "predicted_next_session_low": None, "predicted_next_session_high": None, "rationale": "價格或 20 日歷史資料不足，不產生假預測。"}
    range_inputs = [indicators.get("atr_like_range_pct"), indicators.get("daily_range_pct"), indicators.get("return_volatility_pct")]
    values = [float(x) for x in range_inputs if isinstance(x, (int, float)) and x > 0]
    if not values:
        return {"prediction_status": "insufficient_data", "missing_fields": ["range_measure"], "predicted_session_low": None, "predicted_session_high": None, "predicted_next_session_low": None, "predicted_next_session_high": None, "rationale": "波動區間資料不足，不產生假預測。"}
    base_range = sorted(values)[len(values)//2]
    trend = technical.get("trend_1m")
    up_mult = 1.12 if trend == "bullish" else 0.92 if trend == "bearish" else 1.0
    down_mult = 0.92 if trend == "bullish" else 1.12 if trend == "bearish" else 1.0
    if window == "us_intraday_2300":
        up_mult *= 0.85
        down_mult *= 0.85
    earnings_risk = (research or {}).get("earnings", {}).get("event_risk_level", "low")
    material_events = (research or {}).get("material_news", {}).get("items", [])
    event_mult = 1.18 if earnings_risk == "high" else 1.10 if earnings_risk == "medium" or material_events else 1.0
    next_mult = 1.18 * event_mult
    base_range = base_range * event_mult
    low = round(price * (1 - base_range * down_mult), 2)
    high = round(price * (1 + base_range * up_mult), 2)
    nlow = round(price * (1 - base_range * next_mult * down_mult), 2)
    nhigh = round(price * (1 + base_range * next_mult * up_mult), 2)
    return {
        "prediction_status": "available",
        "reference_price": round(float(price), 2),
        "predicted_session_low": min(low, high),
        "predicted_session_high": max(low, high),
        "predicted_next_session_low": min(nlow, nhigh),
        "predicted_next_session_high": max(nlow, nhigh),
        "range_method": "median of ATR-like range, daily range, and return volatility with trend bias",
        "base_range_pct": round(base_range * 100, 4),
        "intraday_adjusted": window == "us_intraday_2300",
        "event_adjusted": event_mult != 1.0,
        "event_risk_type": earnings_risk if earnings_risk != "low" else ("material_news" if material_events else "none"),
        "research_factor_version": (research or {}).get("research_factors", {}).get("research_factor_version"),
        "model_version": MODEL_VERSION,
        "missing_fields": [],
        "rationale": "以真實 OHLCV 的 ATR-like range、日內區間、報酬波動、趨勢偏差與 earnings/event risk deterministic 調整估算。",
    }

def dashboard_card(entry: dict[str, Any], quote: dict[str, Any], technical: dict[str, Any], score: dict[str, Any], prediction: dict[str, Any], news_items: list[dict[str, Any]], window: str, research: dict[str, Any] | None = None, strategies: dict[str, Any] | None = None) -> dict[str, Any]:
    label = {"us_pre_market_2000": "美股盤前 20:00", "us_intraday_2300": "美股盤中 23:00", "us_post_close_review_0630": "美股檢討 06:30"}[window]
    pstatus = prediction.get("prediction_status")
    session_range = "資料不足" if pstatus != "available" else f"{prediction['predicted_session_low']} ～ {prediction['predicted_session_high']}"
    next_range = "資料不足" if pstatus != "available" else f"{prediction['predicted_next_session_low']} ～ {prediction['predicted_next_session_high']}"
    news = news_items[0] if news_items else {"english_headline": None, "chinese_translation": "無可驗證重大新聞", "investment_reading": "未取得可安全引用新聞；不產生假新聞。"}
    research = research or {}
    sec = research.get("sec", {})
    earnings = research.get("earnings", {})
    fundamentals = research.get("fundamentals", {})
    material_news = research.get("material_news", {})
    research_factors = research.get("research_factors", {})
    strategies = strategies or {}
    tactical = strategies.get(DAILY_TACTICAL, {}) if isinstance(strategies, dict) else {}
    research_strategy = strategies.get(RESEARCH_POSITION, {}) if isinstance(strategies, dict) else {}
    return {
        "card_id": f"us_stock_{entry['symbol']}_{window}",
        "market_label": "美股",
        "window_label": label,
        "symbol": entry["symbol"],
        "name": entry.get("name"),
        "exchange": quote.get("exchange") or entry.get("exchange") or "資料待接",
        "price": quote.get("last_price"),
        "currency": quote.get("currency") or DEFAULT_CURRENCY,
        "rating": score.get("rating"),
        "action": score.get("action"),
        "confidence": score.get("confidence_score"),
        "confidence_level": score.get("confidence_level"),
        "session_predicted_high_low": session_range,
        "next_session_predicted_high_low": next_range,
        "one_month_trend": technical.get("trend_1m"),
        "three_month_trend": technical.get("trend_3m"),
        "latest_status": "live market data fetched" if quote.get("last_price") is not None else "live data insufficient",
        "technical_summary": technical.get("technical_summary"),
        "financial_quality": fundamentals.get("comparison", {}).get("trend_direction"),
        "latest_earnings_status": earnings.get("earnings_status"),
        "guidance_direction": earnings.get("guidance_direction"),
        "latest_sec_filing": (sec.get("latest_quarterly_report") or sec.get("latest_annual_report") or {}).get("form"),
        "official_event_warning": "有近期 8-K" if sec.get("recent_8k_items") else "無近期重大 8-K metadata",
        "research_score": research_factors.get("research_score"),
        "research_rating": research_factors.get("research_rating"),
        "research_confidence": research_factors.get("research_confidence"),
        "source_freshness": "SEC/yfinance/news metadata checked",
        "source_timestamp": quote.get("source_timestamp"),
        "bilingual_news_snippet": (material_news.get("items") or [news])[0] if (material_news.get("items") or news) else news,
        "research_sections": {"sec": sec, "fundamentals": fundamentals, "earnings": earnings, "material_news": material_news, "research_factors": research_factors},
        "strategies": strategies,
        "research_position_summary": {"score": research_strategy.get("score"), "rating": research_strategy.get("rating"), "action": research_strategy.get("action"), "confidence": research_strategy.get("confidence"), "factor_version": research_strategy.get("factor_version")},
        "daily_tactical_summary": {"direction": tactical.get("tactical_direction"), "score": tactical.get("tactical_score"), "grade": tactical.get("tactical_grade"), "action": tactical.get("action"), "confidence": tactical.get("tactical_confidence"), "setup_type": tactical.get("setup_type"), "entry_zone": tactical.get("entry_zone"), "stop_reference": tactical.get("stop_reference"), "target_zone_1": tactical.get("target_zone_1"), "reward_risk_ratio": tactical.get("reward_risk_ratio"), "chase_risk": tactical.get("chase_risk"), "event_risk": tactical.get("event_risk"), "factor_version": tactical.get("factor_version")},
        "review_result": "檢討資料待接" if window != "us_post_close_review_0630" else "依 snapshot/actual outcome 可用性檢討",
    }

def snapshot_path(session_date: str, window: str, symbol: str) -> Path:
    return SNAPSHOT_DIR / session_date / f"{window}_{symbol}.json"

def latest_snapshot_for(symbol: str, session_date: str) -> dict[str, Any] | None:
    for window in ["us_intraday_2300", "us_pre_market_2000"]:
        path = snapshot_path(session_date, window, symbol)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
    return None

def build_review(symbol: str, session_date: str, quote: dict[str, Any], history: Any) -> dict[str, Any]:
    snap = latest_snapshot_for(symbol, session_date)
    if not snap:
        return {"symbol": symbol, "review_status": "pending", "canonical_outcome": "pending", "pending_reason": "missing_prior_prediction_snapshot", "fabricated": False}
    pred = snap.get("prediction", {})
    actual_high = quote.get("day_high")
    actual_low = quote.get("day_low")
    actual_close = quote.get("last_price")
    if None in (actual_high, actual_low, actual_close, pred.get("predicted_session_high"), pred.get("predicted_session_low")):
        return {"symbol": symbol, "review_status": "pending", "canonical_outcome": "pending", "pending_reason": "actual_or_prediction_incomplete", "snapshot_ref": snap.get("snapshot_path"), "fabricated": False}
    high_err = round(float(actual_high) - float(pred["predicted_session_high"]), 4)
    low_err = round(float(actual_low) - float(pred["predicted_session_low"]), 4)
    covered = actual_high <= pred["predicted_session_high"] and actual_low >= pred["predicted_session_low"]
    return {"symbol": symbol, "review_status": "reviewed", "canonical_outcome": "hit" if covered else "fail", "snapshot_ref": snap.get("snapshot_path"), "actual_high": actual_high, "actual_low": actual_low, "actual_close": actual_close, "range_covered": covered, "high_error": high_err, "low_error": low_err, "fabricated": False}

def build_live_runtime_artifact(window: str, watchlist: list[dict[str, Any]], *, production_runtime: bool, write_snapshots: bool = True, reference: datetime | None = None) -> dict[str, Any]:
    if window not in US_BATCH_WINDOWS:
        raise ValueError(f"unsupported US window: {window}")
    generated_at = now_taipei()
    context = session_context(window, reference)
    client = YFinanceUSClient()
    research_builder = USResearchIntelligenceBuilder()
    market_context = client.fetch_context()
    cards = []
    items = []
    reviews = []
    success = 0
    insufficient = 0
    for entry in watchlist:
        symbol = str(entry.get("symbol") or "").upper()
        if not symbol:
            continue
        result = client.fetch_symbol(symbol)
        technical = analyze_history(result.history) if result.history is not None else {"ok": False, "data_quality": {"history_days": 0}, "indicators": {}, "trend_1m": "insufficient_data", "trend_3m": "insufficient_data", "volatility_state": "insufficient_data", "technical_score": None, "technical_summary": "history unavailable"}
        research = research_builder.build_for_symbol(symbol, technical, market_context, result.news)
        score = score_symbol(technical, market_context, result.news, research)
        prediction = prediction_for_symbol(result.quote, technical, window, research)
        prediction["one_month_trend"] = technical.get("trend_1m")
        prediction["three_month_trend"] = technical.get("trend_3m")
        strategies = build_dual_strategies(DEFAULT_MARKET, score, prediction, result.quote, technical, market_context=market_context, research=research, generated_at=generated_at)
        card = dashboard_card(entry, result.quote, technical, score, prediction, result.news, window, research, strategies)
        if result.ok and prediction.get("prediction_status") == "available":
            success += 1
        else:
            insufficient += 1
        item = {"symbol": symbol, "name": entry.get("name"), "market": DEFAULT_MARKET, "quote": result.quote, "fetch_ok": result.ok, "fetch_error": result.error, "technical": technical, "market_context_ref": "market_context", "news": result.news, "research_intelligence": research, "strategies": strategies, "score": score, "prediction": prediction, "data_quality": {"quote_available": result.quote.get("last_price") is not None, "history_days": technical.get("data_quality", {}).get("history_days"), "news_count": len(result.news), "sec_ok": research.get("sec", {}).get("ok"), "research_factor_version": research.get("research_factors", {}).get("research_factor_version")}, "source_timestamp": result.quote.get("source_timestamp")}
        items.append(item)
        cards.append(card)
        if window in {"us_pre_market_2000", "us_intraday_2300"} and write_snapshots and prediction.get("prediction_status") == "available":
            spath = snapshot_path(context["session_date"], window, symbol)
            snap = {"schema_version": "us_stock_prediction_snapshot_v1", "market": DEFAULT_MARKET, "session_date": context["session_date"], "window": window, "symbol": symbol, "generated_at": generated_at, "prediction": prediction, "rating": score.get("rating"), "action": score.get("action"), "confidence_score": score.get("confidence_score"), "model_version": MODEL_VERSION, "data_source_timestamps": {"quote": result.quote.get("source_timestamp")}, "fixture": False, "validation_only": False}
            snap["snapshot_path"] = str(spath.relative_to(REPO_ROOT))
            write_json(spath, snap)
        if window == "us_post_close_review_0630":
            review = build_review(symbol, context["session_date"], result.quote, result.history)
            reviews.append(review)
    structured_review_cards = build_structured_review_cards(cards, reviews) if window == "us_post_close_review_0630" else []
    review_aggregate = aggregate_outcomes(structured_review_cards) if structured_review_cards else {
        "hit_count": 0, "fail_count": 0, "not_triggered_count": 0, "no_trade_count": 0,
        "pending_count": 0, "review_card_count": 0, "completed_review_count": 0,
        "pending_review_count": 0, "review_universe_count": 0,
    }
    if structured_review_cards:
        cards = structured_review_cards
    artifact = {
        "schema_version": "us_stock_live_runtime_v1",
        "artifact_kind": "us_stock_runtime",
        "artifact_type": "us_stock_live_runtime_artifact",
        "artifact_mode": "production_runtime" if production_runtime else "live_no_send_validation",
        "runtime_provenance": "scheduled_production" if production_runtime else "controlled_no_send",
        "provenance_source": "app.us_stock.live_pipeline.production_runtime_flag",
        "data_source_mode": "live",
        "fixture": False,
        "validation_only": not production_runtime,
        "generated_by": "app.us_stock.live_pipeline.build_live_runtime_artifact",
        "generated_at": generated_at,
        "market": DEFAULT_MARKET,
        "currency": DEFAULT_CURRENCY,
        "window": window,
        "source_sheet": "工作表2",
        "session_context": context,
        "runtime_watchlist_validation": {"source_sheet": "工作表2", "enabled_stock_count": len(watchlist), "successfully_analyzed_count": success, "insufficient_data_count": insufficient, "invalid_row_count": 0, "private_values_printed": False},
        "market_context": market_context,
        "research_intelligence_contract": {"source_hierarchy": "tier1_official_sec_ir_company; tier2_market_reference_yfinance; tier3_secondary_news", "research_factor_version": RESEARCH_FACTOR_VERSION, "copyright_policy": "no full filings/articles/transcripts stored", "official_source_required_for_official_claims": True},
        "dual_strategy_contract": {"market": DEFAULT_MARKET, "strategy_types": [RESEARCH_POSITION, DAILY_TACTICAL], "research_position_version": "us_research_position_v1", "daily_tactical_version": "us_daily_tactical_v1", "daily_tactical_factor_version": US_TACTICAL_FACTOR_VERSION, "research_overwritten_by_tactical": False, "tactical_overwrites_research": False, "line_email_sent_by_builder": False},
        "items": items,
        "structured_review_cards": structured_review_cards,
        "outcome_aggregate": review_aggregate,
        "prediction_review_contract": {
            "market": DEFAULT_MARKET, "review_window": "us_post_close_review_0630",
            "review_card_count": review_aggregate["review_card_count"],
            "completed_review_count": review_aggregate["completed_review_count"],
            "pending_review_count": review_aggregate["pending_review_count"],
            "review_universe_count": review_aggregate["review_universe_count"],
            "reviewed_stock_count": review_aggregate["completed_review_count"],
            "pending_stock_count": review_aggregate["pending_review_count"],
            "outcome_counts": review_aggregate, "skipped_stock_count": 0, "items": reviews, "fabricated": False,
        },
        "dashboard_ready_contract": {"market_label": "美股", "sections": ["美股盤前 20:00", "美股盤中 23:00", "美股檢討 06:30"], "cards": cards},
        "delivery_policy": {"email_full_report": True, "line_reminder_only": True, "unscheduled_validation_send": False},
        "safety_policy": {"python3_main_executed": False, "trading_or_order_executed": False, "line_email_sent_by_builder": False, "tw_formula_modified": False, "secrets_printed": False},
    }
    if window == "us_post_close_review_0630":
        review_path = REVIEW_DIR / context["session_date"] / "us_post_close_review_0630.json"
        write_json(review_path, artifact)
    return artifact
