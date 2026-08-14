"""Pure TW prediction presentation, lineage and news-integrity contracts.

AI-DEV-217 deliberately keeps Research/Position, Daily Tactical and Decision
ownership separate.  This module projects already-computed evidence for PM
explainability; it never fetches, scores, ranks, publishes, notifies or trades.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from typing import Any

WINDOWS = ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")
DIRECTIONS = {"bullish", "bearish", "neutral", "range_bound", "insufficient_evidence"}
TIER4_MARKERS = ("cmoney", "股市爆料同學會", "同學風向", "貼文摘要", "準備噴", "forum", "community")
OFFICIAL_MARKERS = ("mops", "公開資訊觀測站", "twse", "tpex", "公司公告", "official", "investor relations", "公司官網")
MEDIA_MARKERS = ("reuters", "bloomberg", "工商時報", "經濟日報", "中央社", "財訊快報", "digitimes")
ETF_SYMBOLS = {"00878", "009816"}
ETF_EVENT_MARKERS = {
    "constituent_change": ("成分股", "成分調整"),
    "index_rebalance": ("指數調整", "rebalance", "換股"),
    "fund_flow": ("資金流", "申購", "贖回"),
    "distribution": ("配息", "股息", "收益分配"),
    "index_exposure": ("指數", "cpi", "市場曝險"),
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _hash(value: Any, prefix: str) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return prefix + hashlib.sha256(raw.encode()).hexdigest()[:24]


def validate_interval(low: Any, high: Any, *, name: str = "prediction") -> tuple[float | None, float | None]:
    lo, hi = _number(low), _number(high)
    if (lo is None) != (hi is None):
        raise ValueError(f"{name}_interval_incomplete")
    if lo is not None and hi is not None and lo > hi:
        raise ValueError(f"{name}_interval_reversed")
    return lo, hi


def classify_tw_news(item: dict[str, Any], *, symbol: str, instrument_type: str = "company") -> dict[str, Any]:
    headline = str(item.get("headline") or item.get("title") or "")
    publisher = str(item.get("publisher") or item.get("source_name") or "")
    source_url = str(item.get("source_url") or item.get("url") or "")
    text = f"{headline} {publisher} {source_url}".lower()
    original_tier = int(_number(item.get("source_tier")) or 4)
    sentiment_only = any(marker in text for marker in TIER4_MARKERS)
    if sentiment_only:
        tier, source_class = 4, "sentiment_only"
    elif item.get("official_source") is True or any(marker in text for marker in OFFICIAL_MARKERS):
        tier, source_class = 1, "official_primary"
    elif any(marker in text for marker in MEDIA_MARKERS):
        tier, source_class = 2, "reputable_media"
    else:
        tier, source_class = max(2, min(4, original_tier)), "general_news"
    etf_event = None
    if instrument_type == "etf" or symbol in ETF_SYMBOLS:
        for event, markers in ETF_EVENT_MARKERS.items():
            if any(marker in text for marker in markers):
                etf_event = event
                break
        subject_contract = "etf_specific"
    else:
        subject_contract = "company_specific"
    direction = str(item.get("direction") or "unavailable").lower()
    can_establish_direction = tier <= 2 and not sentiment_only and direction in {"bullish", "bearish"}
    result = deepcopy(item)
    result.update({
        "tw_news_tier": tier,
        "source_class": source_class,
        "research_role": "contextual" if sentiment_only or tier >= 3 else "substantive",
        "direction": direction if can_establish_direction else "unavailable" if sentiment_only else direction,
        "direction_status": "EVALUATED" if can_establish_direction else "NOT_EVALUATED",
        "can_establish_research_direction": can_establish_direction,
        "instrument_news_contract": subject_contract,
        "etf_event_type": etf_event,
        "classification_reason": "TIER4_SENTIMENT_RESTRICTED" if sentiment_only else f"SOURCE_TIER_{tier}",
    })
    return result


def finalized_tw_news_projection(card: dict[str, Any]) -> dict[str, Any]:
    symbol = str(card.get("symbol") or card.get("stock_id") or "")
    instrument = card.get("instrument_context_v2") if isinstance(card.get("instrument_context_v2"), dict) else {}
    instrument_type = str(instrument.get("instrument_type") or instrument.get("kind") or "company")
    news = card.get("news_evidence") if isinstance(card.get("news_evidence"), dict) else {}
    raw = [item for item in (news.get("evidence") or card.get("news_items") or []) if isinstance(item, dict)]
    classified = [classify_tw_news(item, symbol=symbol, instrument_type=instrument_type) for item in raw]
    current = [item for item in classified if str(item.get("freshness") or "fresh").lower() != "stale"]
    institutional = [item for item in current if int(item["tw_news_tier"]) <= 2]
    contextual = [item for item in current if int(item["tw_news_tier"]) >= 3]
    funnel = news.get("evidence_funnel") if isinstance(news.get("evidence_funnel"), dict) else {}
    stages = dict(funnel.get("stages") or {})
    retrieval = news.get("retrieval") if isinstance(news.get("retrieval"), dict) else {}
    retrieval_failed = bool(retrieval.get("failure_reason")) and not raw
    stale = len(classified) - len(current)
    selected = institutional[:3]
    state = (
        "AVAILABLE" if selected else
        "RETRIEVAL_FAILED" if retrieval_failed else
        "STALE_ONLY" if stale and stale == len(classified) else
        "DISCOVERED_BUT_FILTERED" if int(stages.get("DISCOVERED") or 0) else
        "NO_RELEVANT"
    )
    direction_items = [item for item in selected if item.get("can_establish_research_direction")]
    result = {
        "schema_version": "tw_finalized_news_projection_v1",
        "symbol": symbol,
        "instrument_news_contract": "etf_specific" if instrument_type == "etf" or symbol in ETF_SYMBOLS else "company_specific",
        "state": state,
        "reason_code": "LOW_TIER_OR_CONTEXT_ONLY" if contextual and not selected else state,
        "selected_items": selected,
        "context_items": contextual,
        "selected_count": len(selected),
        "context_count": len(contextual),
        "directional_count": len(direction_items),
        "bullish_count": sum(item.get("direction") == "bullish" for item in direction_items),
        "bearish_count": sum(item.get("direction") == "bearish" for item in direction_items),
        "source_funnel": {**funnel, "stages": {**stages, "RRE_USED": len(selected), "RENDERED": len(selected)}},
        "single_source_of_truth": True,
    }
    result["projection_id"] = _hash(result, "twnews_")
    return result


def _direction(card: dict[str, Any], snapshot: dict[str, Any]) -> str:
    raw = str(snapshot.get("direction_forecast") or card.get("predicted_direction") or "").lower()
    aliases = {"long": "bullish", "uptrend": "bullish", "short": "bearish", "downtrend": "bearish", "sideways": "range_bound", "insufficient_data": "insufficient_evidence", "unavailable": "insufficient_evidence"}
    value = aliases.get(raw, raw)
    return value if value in DIRECTIONS else "insufficient_evidence"


def _expected_path(direction: str, technical: str, *, conflict: bool) -> str:
    if conflict:
        return "短線與中期訊號衝突，維持觀察並等待情境觸發"
    return {
        "bullish": "震盪偏多",
        "bearish": "反彈但中期仍弱" if "downtrend" in technical else "弱勢整理",
        "neutral": "高檔震盪" if "uptrend" in technical else "區間震盪",
        "range_bound": "區間震盪",
        "insufficient_evidence": "無法形成可靠路徑",
    }[direction]


def _confidence(snapshot: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    score = _number(snapshot.get("confidence"))
    if score is None:
        news_confidence = card.get("news_confidence") if isinstance(card.get("news_confidence"), dict) else {}
        score = _number(news_confidence.get("score"))
    band = "insufficient" if score is None else "high" if score >= 75 else "medium" if score >= 50 else "low"
    return {"score": score, "band": band}


def _levels(card: dict[str, Any], low: float | None, high: float | None) -> dict[str, Any]:
    monitoring = card.get("monitoring_range") if isinstance(card.get("monitoring_range"), dict) else {}
    return {
        "support_1": _number(card.get("stop_level")) or _number(monitoring.get("low")) or low,
        "support_2": _number(card.get("entry_low")),
        "resistance_1": _number(card.get("target_1")) or _number(monitoring.get("high")) or high,
        "resistance_2": _number(card.get("target_2")),
    }


def _progress(direction: str, low: float | None, high: float | None, card: dict[str, Any]) -> dict[str, Any]:
    current, actual_low, actual_high = _number(card.get("current_price")), _number(card.get("session_low") or card.get("actual_low")), _number(card.get("session_high") or card.get("actual_high"))
    if current is None or low is None or high is None:
        status = "insufficient_data"
    elif current > high:
        status = "bullish_breakout"
    elif current < low:
        status = "bearish_breakdown"
    elif direction == "bullish" and actual_low is not None and actual_low < low:
        status = "partial_deviation"
    elif direction == "bearish" and actual_high is not None and actual_high > high:
        status = "partial_deviation"
    else:
        status = "on_track"
    midpoint = None if low is None or high is None else (low + high) / 2
    deviation = None if current is None or midpoint in (None, 0) else round((current - midpoint) / midpoint * 100, 4)
    return {"status": status, "current_price": current, "session_low": actual_low, "session_high": actual_high, "midpoint_deviation_pct": deviation, "range_breached": status in {"bullish_breakout", "bearish_breakdown"}}


def project_tw_prediction_card(card: dict[str, Any], window: str, *, strict: bool = True) -> dict[str, Any]:
    if window not in WINDOWS:
        raise ValueError("unsupported_tw_prediction_window")
    result = deepcopy(card)
    snapshot = result.get("prediction_snapshot_v2") if isinstance(result.get("prediction_snapshot_v2"), dict) else {}
    range_forecast = snapshot.get("range_forecast") if isinstance(snapshot.get("range_forecast"), dict) else {}
    raw_low = range_forecast.get("low", result.get("predicted_low"))
    raw_high = range_forecast.get("high", result.get("predicted_high"))
    try:
        low, high = validate_interval(raw_low, raw_high)
    except ValueError:
        if strict:
            raise
        low = high = None
    next_range = result.get("next_session_range") if isinstance(result.get("next_session_range"), dict) else {}
    next_low, next_high = validate_interval(next_range.get("low"), next_range.get("high"), name="next_session") if next_range else (None, None)
    direction = _direction(result, snapshot)
    technical = str(result.get("technical_direction") or result.get("technical_summary") or ((result.get("technical_data") or {}).get("direction")) or "").lower()
    explanation = str(result.get("reasoning") or result.get("action_change_reason") or "").lower()
    bearish_reason = bool(re.search(r"bearish|偏空|空頭|downtrend", explanation))
    bullish_reason = bool(re.search(r"bullish|偏多|多頭|uptrend", explanation))
    same_horizon_conflict = (direction == "bullish" and bearish_reason) or (direction == "bearish" and bullish_reason)
    explicit_conflict = bool(result.get("signal_conflict"))
    if strict and same_horizon_conflict and not explicit_conflict:
        raise ValueError("same_horizon_semantic_conflict")
    prediction_id = snapshot.get("prediction_identity") or result.get("prediction_id")
    if not prediction_id:
        prediction_id = _hash({"symbol": result.get("symbol") or result.get("stock_id"), "window": "pre_open_0700", "range": [low, high], "direction": direction}, "twpred_")
    progress = _progress(direction, low, high, result)
    news = finalized_tw_news_projection(result)
    tactical = ((result.get("strategies") or {}).get("daily_tactical") or {}) if isinstance(result.get("strategies"), dict) else {}
    research_stance = str(result.get("research_stance") or "insufficient_evidence")
    trigger_up = result.get("entry_condition") or (tactical.get("playbook") or {}).get("entry_condition") or (f"站上 {high}" if high is not None else "補足量價證據")
    trigger_down = result.get("invalidation_condition") or (tactical.get("playbook") or {}).get("invalidation_condition") or (f"跌破 {low}" if low is not None else "反向證據成立")
    presentation = {
        "schema_version": "tw_prediction_presentation_v1",
        "prediction_id": prediction_id,
        "origin_window": "pre_open_0700",
        "current_window": window,
        "direction": direction,
        "expected_path": _expected_path(direction, technical, conflict=same_horizon_conflict or explicit_conflict),
        "today_range": {"predicted_low": low, "predicted_high": high},
        "next_session_range": {"next_low": next_low, "next_high": next_high},
        "key_levels": _levels(result, low, high),
        "scenario_switch": {"bullish_trigger": trigger_up, "bearish_trigger": trigger_down, "invalidation_condition": trigger_down},
        "confidence": _confidence(snapshot, result),
        "evidence_summary": {
            "technical": result.get("technical_summary") or result.get("technical_direction"),
            "market": result.get("market_context"), "chip": result.get("chip_summary"),
            "news": news["state"], "event": result.get("event_summary") or result.get("event_risk"),
            "adr_overnight": result.get("adr_context") or result.get("overnight_context"),
        },
        "research_view": {"horizon": "position", "stance": research_stance},
        "daily_tactical": {"horizon": "today", "setup_type": tactical.get("setup_type") or result.get("strategy_type"), "direction": direction, "formal_trade_plan": result.get("plan_status") == "active" or result.get("entry_readiness") == "entry_ready"},
        "signal_conflict": same_horizon_conflict or explicit_conflict,
        "signal_conflict_explanation": "短線動能與同一時段敘述衝突，須先釐清後才能 admission" if same_horizon_conflict and not explicit_conflict else "短線動能與中期趨勢不同，兩個 horizon 分開呈現" if explicit_conflict else None,
        "intraday_prediction_status": progress,
        "close_expectation": "盤前預測仍有效" if progress["status"] == "on_track" else "盤前預測已偏離" if progress["status"] != "insufficient_data" else "缺少行情，無法判定盤前預測進度",
        "change_from_previous_window": result.get("action_change_reason") or "本時段沿用 07:00 prediction identity，等待新增證據",
        "news_projection_id": news["projection_id"],
        "decision_ownership_preserved": True,
    }
    result["finalized_tw_news_projection_v1"] = news
    result["prediction_presentation_v1"] = presentation
    result["prediction_id"] = prediction_id
    return result


def validate_news_surface_parity(card: dict[str, Any]) -> list[str]:
    canonical = finalized_tw_news_projection(card)
    errors: list[str] = []
    existing = card.get("finalized_tw_news_projection_v1")
    if isinstance(existing, dict):
        for key in ("state", "selected_count", "directional_count"):
            if existing.get(key) != canonical.get(key):
                errors.append(f"news_surface_parity_{key}")
    summary_count = card.get("news_selected_count")
    if summary_count is not None and int(summary_count) != canonical["selected_count"]:
        errors.append("news_summary_count_mismatch")
    return errors


def post_close_quality_review(cards: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for card in cards:
        projected = project_tw_prediction_card(card, "post_close_1500", strict=False)
        p = projected["prediction_presentation_v1"]
        evaluation = card.get("prediction_evaluation_v2") if isinstance(card.get("prediction_evaluation_v2"), dict) else card.get("prediction_evaluation") or {}
        rows.append({"symbol": str(card.get("symbol") or card.get("stock_id") or ""), "result": evaluation.get("range_result") or card.get("prediction_range_result"), "high_error": evaluation.get("high_error"), "low_error": evaluation.get("low_error"), "deviation": abs(_number(p["intraday_prediction_status"].get("midpoint_deviation_pct")) or 0), "why": card.get("prediction_explainability") or p["close_expectation"]})
    rank = {"hit": 3, "partial_hit": 2, "miss": 1, "not_applicable": 0, None: 0}
    best = max(rows, key=lambda row: (rank.get(row["result"], 0), -row["deviation"]), default=None)
    worst = min(rows, key=lambda row: (rank.get(row["result"], 0), -row["deviation"]), default=None)
    biggest = max(rows, key=lambda row: row["deviation"], default=None)
    return {"schema_version": "tw_post_close_prediction_quality_v1", "best_prediction": best, "worst_prediction": worst, "biggest_range_error": biggest, "biggest_direction_error": worst, "most_important_missed_evidence": "檢查最差預測的缺失 evidence 與 scenario trigger", "tomorrow_carry_forward_question": "哪些今日偏離需要在明日 07:00 重新建立假設？"}
