"""Canonical TW four-window decision payloads.

Pure deterministic adapters only.  The module never fetches data, writes
production artifacts, sends notifications, or places orders.  Producers pass
the observed quote and the admitted 07:00 setup explicitly.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.reports.presentation_normalization import (
    aggregate_card_timestamp,
    format_timestamp,
    next_session_action,
    safe_public_text,
)

TAIPEI = ZoneInfo("Asia/Taipei")
SCHEMA_VERSION = "tw_four_window_decision_closure_v1"
TW_WINDOWS = ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")
OBSERVED_WINDOWS = TW_WINDOWS[1:]
OUTCOMES = ("hit", "fail", "not_triggered", "no_trade", "pending")

LOCALIZED = {
    "wait": "等待", "sideways": "盤整", "high": "高", "medium": "中",
    "low": "低", "normal": "一般", "insufficient_data": "資料不足",
    "pending": "待確認", "not_applicable": "不適用", "unavailable": "尚未取得",
    "complete": "完整", "partial": "部分可用", "stale": "資料過舊",
    "triggered": "已觸發", "inside_zone": "進入進場區", "not_reached": "尚未到達",
    "passed_without_safe_entry": "已偏離安全進場區", "invalidated": "已失效",
    "no_trade": "無交易", "hit": "命中", "fail": "失敗", "not_triggered": "未觸發",
    "strong": "量能強勁", "confirmed": "量能確認", "weak": "量能偏弱",
    "entry_ready": "進場條件完整", "watch": "觀察", "hold": "可留倉", "reduce": "降低風險",
    "avoid_overnight": "避免留倉", "data_unavailable": "資料無法取得",
    "cancel_chase": "取消追價", "target_near": "接近目標", "entry_triggered_hold": "已觸發，續抱觀察",
    "wait_for_volume": "等待量能確認", "reduce_risk": "降低風險", "maintain_watch": "維持觀察",
    "unknown": "尚未判定", "neutral": "中性", "downtrend": "偏空趨勢",
}


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _zone(value: Any) -> tuple[float | None, float | None]:
    if not isinstance(value, dict):
        return None, None
    low, high = number(value.get("low")), number(value.get("high"))
    if low is None or high is None:
        return None, None
    return min(low, high), max(low, high)


def _stop(value: Any) -> float | None:
    return number(value.get("price")) if isinstance(value, dict) else number(value)


def _target(value: Any) -> float | None:
    low, high = _zone(value)
    return None if low is None or high is None else round((low + high) / 2, 4)


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def canonical_setup_id(*, trading_date: str, symbol: str, strategy_type: str, source_revision: int) -> str:
    identity = ["TW", trading_date, str(symbol), strategy_type, "pre_open_0700", int(source_revision)]
    return "tw-" + stable_hash(identity)[:24]


def sanitize_text(value: Any, fallback: str = "本批次尚未取得") -> str:
    """Return human-readable public text without raw objects or provider errors."""
    if value in (None, "", [], {}):
        return fallback
    if isinstance(value, dict):
        if value.get("error") or value.get("error_type") or value.get("reason") in {"DEADLINE_EXCEEDED", "timeout"}:
            return "新聞分析暫時無法取得"
        preferred = []
        for key in ("summary", "market_summary", "status", "direction", "change_rate", "reason"):
            item = value.get(key)
            if item not in (None, "", [], {}):
                preferred.append(f"{key.replace('_', ' ')}：{sanitize_text(item)}")
        return "；".join(preferred[:4]) or fallback
    if isinstance(value, list):
        clean = [sanitize_text(item, "") for item in value]
        return "、".join(item for item in clean if item) or fallback
    text = str(value).strip()
    instruction = {
        "use deterministic entry_zone when present": "價格進入建議區間，且量價與風險條件符合",
        "setup not confirmed": "進場條件尚未確認",
    }
    if text in instruction:
        return instruction[text]
    lowered = text.lower()
    if "gemini error" in lowered or "deadline_exceeded" in lowered or "504" in lowered:
        return "新聞分析暫時無法取得"
    if text in LOCALIZED:
        return LOCALIZED[text]
    return text


def localize(value: Any) -> str:
    return LOCALIZED.get(str(value), sanitize_text(value))


def upgrade_pre_open_card(card: dict[str, Any], tactical: dict[str, Any] | None, *, source_revision: int = 1) -> dict[str, Any]:
    tactical = tactical if isinstance(tactical, dict) else {}
    result = dict(card)
    symbol = str(result.get("symbol") or result.get("stock_id") or "")
    trading_date = str(result.get("trading_date") or "")
    strategy_type = str(tactical.get("setup_type") or "unavailable")
    entry_low, entry_high = _zone(tactical.get("entry_zone"))
    target_1, target_2 = _target(tactical.get("target_1")), _target(tactical.get("target_2"))
    stop_level = _stop(tactical.get("stop_invalidation"))
    data_quality = str(tactical.get("data_quality") or result.get("availability_status") or "unavailable")
    setup = canonical_setup_id(
        trading_date=trading_date, symbol=symbol, strategy_type=strategy_type, source_revision=source_revision,
    )
    no_trade = strategy_type == "no_trade"
    safe_levels = all(value is not None for value in (entry_low, entry_high, stop_level, target_1))
    readiness = (
        "no_trade" if no_trade else "entry_ready" if safe_levels and data_quality in {"complete", "partial"}
        and number(tactical.get("reward_risk")) is not None and float(tactical["reward_risk"]) >= 0.8
        and tactical.get("chase_risk") != "high" else "watch" if safe_levels else "unavailable"
    )
    missing = set(str(item) for item in result.get("missing_fields", []) if item)
    for name, value in (("entry", entry_low), ("stop", stop_level), ("target_1", target_1)):
        if value is None and not no_trade:
            missing.add(name)
    if missing and readiness == "entry_ready":
        readiness = "watch"
    normalized_data_status = "partial" if missing or data_quality in {"partial", "limited"} else "unavailable" if data_quality == "insufficient" else "complete"
    result.update({
        "schema_version": "tw_pre_open_structured_decision_v2",
        "setup_id": setup, "parent_setup_id": None, "strategy_type": strategy_type,
        "source_window": "pre_open_0700", "source_revision": source_revision,
        "entry_readiness": readiness, "entry_low": entry_low, "entry_high": entry_high,
        "entry_zone": tactical.get("entry_zone"), "stop_level": stop_level,
        "target_1": target_1, "target_2": target_2,
        "target_level": tactical.get("target_1"), "risk_reward": number(tactical.get("reward_risk")),
        "action": sanitize_text(tactical.get("action") or result.get("action")),
        "entry_condition": sanitize_text((tactical.get("playbook") or {}).get("entry_condition")),
        "chase_risk": str(tactical.get("chase_risk") or result.get("chase_risk") or "unavailable"),
        "event_risk": str(tactical.get("event_risk") or result.get("event_risk") or "unavailable"),
        "no_trade_reason": sanitize_text("；".join(tactical.get("risk_reasons") or []), "不適用") if no_trade else None,
        "do_not_trade_reason": sanitize_text("；".join(tactical.get("risk_reasons") or []), "不適用") if no_trade else None,
        "data_status": normalized_data_status,
        "availability_status": normalized_data_status,
        "missing_fields": sorted(missing),
        "technical_summary": sanitize_text(result.get("technical_summary")),
        "chip_summary": sanitize_text(result.get("chip_summary")),
        "adr_context": sanitize_text(result.get("adr_context")),
        "overnight_context": sanitize_text(result.get("overnight_context")),
        "news_summary": sanitize_text(result.get("news_summary"), "新聞分析暫時無法取得"),
        "news_status": "unavailable" if "news" in missing else "available",
        "news_source_class": "general_media" if "news" not in missing else "unavailable",
        "reasoning": sanitize_text("；".join(tactical.get("reasons") or []) or result.get("reasoning")),
        "risk_summary": sanitize_text("；".join(tactical.get("risk_reasons") or []) or result.get("risk_summary")),
        "strategies": {"daily_tactical": dict(tactical)},
        "prediction_status": "no_trade" if no_trade else "active" if safe_levels else "unavailable",
        "predicted_direction": tactical.get("direction"),
        "predicted_low": entry_low,
        "predicted_high": target_1,
        "prediction_method": "tw_daily_tactical_entry_to_target_corridor_v1",
        "opportunity_group": "no_trade" if no_trade else "opportunity" if readiness == "entry_ready" else "watch" if readiness == "watch" else "unavailable",
        "risk_adjusted_score": round(float(result.get("risk_adjusted_score") or result.get("decision_score") or 0) + (10 if readiness == "entry_ready" else 0), 4),
    })
    without_hash = dict(result)
    without_hash.pop("source_payload_hash", None)
    result["source_payload_hash"] = stable_hash(without_hash)
    return result


def _quote_value(quote: dict[str, Any], *names: str) -> Any:
    for name in names:
        if quote.get(name) not in (None, ""):
            return quote[name]
    return None


def _volume_ratio(volume: float | None, tactical: dict[str, Any], window: str) -> tuple[float | None, str, float | None]:
    factors = tactical.get("technical_factors") if isinstance(tactical.get("technical_factors"), dict) else {}
    daily = number(factors.get("volume_ma20"))
    fractions = {"intraday_1305": 245 / 270, "pre_close_1335": 1.0, "post_close_1500": 1.0}
    baseline = None if daily is None else daily * fractions[window]
    ratio = None if volume is None or baseline in (None, 0) else round(volume / baseline, 4)
    state = "unavailable" if ratio is None else "strong" if ratio >= 1.25 else "confirmed" if ratio >= 1.0 else "normal" if ratio >= 0.7 else "weak"
    return ratio, state, None if baseline is None else round(baseline, 2)


def _trigger_state(low: float | None, high: float | None, current: float | None, entry_low: float | None, entry_high: float | None, stop: float | None) -> tuple[str, float | None]:
    if None in (low, high, current, entry_low, entry_high):
        return "unavailable", None
    assert low is not None and high is not None and current is not None and entry_low is not None and entry_high is not None
    touched = low <= entry_high and high >= entry_low
    if touched and stop is not None and low <= stop:
        return "invalidated", round(min(max(current, entry_low), entry_high), 4)
    if touched:
        return "triggered", round(min(max(current, entry_low), entry_high), 4)
    if high < entry_low:
        return "not_reached", None
    if low > entry_high:
        return "passed_without_safe_entry", None
    return "inside_zone", round(current, 4)


def build_observed_card(
    *, window: str, setup_card: dict[str, Any], quote: dict[str, Any] | None,
    trading_date: str, generated_at: str, source_snapshot_id: str | None,
    source_revision: int, source_payload_hash: str | None,
) -> dict[str, Any]:
    if window not in OBSERVED_WINDOWS:
        raise ValueError("unsupported_tw_observed_window")
    quote = quote if isinstance(quote, dict) else {}
    symbol = str(setup_card.get("symbol") or setup_card.get("stock_id") or "")
    tactical = ((setup_card.get("strategies") or {}).get("daily_tactical") or {}) if isinstance(setup_card.get("strategies"), dict) else {}
    entry_low = number(setup_card.get("entry_low")); entry_high = number(setup_card.get("entry_high"))
    stop = number(setup_card.get("stop_level")); target1 = number(setup_card.get("target_1")); target2 = number(setup_card.get("target_2"))
    current = number(_quote_value(quote, "close", "current_price"))
    session_open = number(_quote_value(quote, "open", "session_open"))
    high = number(_quote_value(quote, "high", "session_high"))
    low = number(_quote_value(quote, "low", "session_low"))
    volume = number(_quote_value(quote, "total_volume", "session_volume", "volume"))
    observed_at = _quote_value(quote, "snapshot_time", "market_data_as_of", "source_record_time")
    required = {"current_price": current, "market_data_as_of": observed_at, "session_open": session_open, "session_high": high, "session_low": low}
    missing = [key for key, value in required.items() if value in (None, "")]
    data_status = "complete" if not missing else "partial" if current is not None or observed_at else "unavailable"
    trigger, trigger_price = _trigger_state(low, high, current, entry_low, entry_high, stop)
    ratio, volume_state, baseline = _volume_ratio(volume, tactical, window)
    distance_stop = None if current in (None, 0) or stop is None else round((stop - current) / current * 100, 4)
    distance_t1 = None if current in (None, 0) or target1 is None else round((target1 - current) / current * 100, 4)
    distance_t2 = None if current in (None, 0) or target2 is None else round((target2 - current) / current * 100, 4)
    no_trade = setup_card.get("entry_readiness") == "no_trade" or tactical.get("setup_type") == "no_trade"
    near_stop = distance_stop is not None and abs(distance_stop) <= 1.5
    near_target = distance_t1 is not None and abs(distance_t1) <= 1.5
    if data_status == "unavailable":
        action, reason = "data_unavailable", "盤中行情來源暫時無法取得，本次無法安全判定策略"
    elif no_trade:
        action, reason = "no_trade", "07:00 setup 明確為無交易"
    elif trigger == "invalidated":
        action, reason = "stop_invalidated", "盤中價格已觸及失效／停損條件"
    elif trigger == "passed_without_safe_entry" or setup_card.get("chase_risk") == "high":
        action, reason = "cancel_chase", "價格已偏離安全進場區或追價風險過高"
    elif near_stop:
        action, reason = "reduce_risk", "目前價格接近停損／失效條件"
    elif near_target:
        action, reason = "target_near", "目前價格接近第一目標"
    elif trigger in {"triggered", "inside_zone"} and volume_state in {"strong", "confirmed"}:
        action, reason = "entry_triggered_hold", f"進場條件已觸發，量能為基準 {ratio:.2f} 倍" if ratio is not None else "進場條件已觸發"
    elif trigger in {"triggered", "inside_zone"}:
        action, reason = "wait_for_volume", "價格已到達進場區，但量能尚未確認"
    else:
        action, reason = "maintain_watch", "尚未到達進場條件，維持觀察"
    holding = (
        "unavailable" if data_status == "unavailable" else "no_trade" if no_trade else
        "reduce" if action in {"reduce_risk", "stop_invalidated"} else
        "avoid_overnight" if action == "cancel_chase" else "hold" if action in {"entry_triggered_hold", "target_near"} else "watch"
    )
    result = {
        "schema_version": SCHEMA_VERSION, "market": "TW", "window": window,
        "symbol": symbol, "stock_id": symbol, "name": setup_card.get("name") or setup_card.get("stock_name"),
        "stock_name": setup_card.get("stock_name") or setup_card.get("name"), "trading_date": trading_date,
        "setup_id": setup_card.get("setup_id"), "parent_setup_id": setup_card.get("setup_id"),
        "source_snapshot_id": source_snapshot_id, "source_revision": int(source_revision),
        "parent_source_payload_hash": source_payload_hash,
        "strategy_type": setup_card.get("strategy_type") or tactical.get("setup_type"),
        "current_price": current, "market_data_as_of": observed_at, "session_open": session_open,
        "session_high": high, "session_low": low, "session_volume": volume,
        "source_name": quote.get("source") or "shioaji_snapshot", "source_type": "observed_market_snapshot",
        "source_record_time": observed_at, "fetched_at": generated_at, "normalized_at": generated_at,
        "freshness_status": "fresh" if observed_at else "unavailable",
        "entry_low": entry_low, "entry_high": entry_high, "entry_trigger_state": trigger,
        "entry_trigger_price": trigger_price, "entry_trigger_time": observed_at if trigger in {"triggered", "invalidated", "inside_zone"} else None,
        "volume_baseline": baseline, "volume_baseline_method": "historical_20d_daily_mean_prorated_by_session_elapsed_v1",
        "volume_ratio": ratio, "volume_confirmation_state": volume_state,
        "stop_level": stop, "target_1": target1, "target_2": target2,
        "distance_to_stop_pct": distance_stop, "distance_to_target_1_pct": distance_t1,
        "distance_to_target_2_pct": distance_t2, "near_stop": near_stop, "near_target": near_target,
        "pre_open_action": setup_card.get("action"), "intraday_action": action,
        "action_change_reason": reason, "holding_decision": holding, "holding_reason": reason,
        "chase_risk": setup_card.get("chase_risk"), "overnight_gap_risk": setup_card.get("gap_risk"),
        "event_risk": setup_card.get("event_risk"), "tomorrow_watch_status": holding in {"hold", "watch"},
        "data_status": data_status, "missing_fields": sorted(missing), "strategies": {"daily_tactical": dict(tactical)},
        "decision_state": {
            "hold_candidate": holding == "hold", "avoid_hold": holding in {"reduce", "avoid_overnight"},
            "no_trade": no_trade, "late_session_risk": holding in {"reduce", "avoid_overnight"},
            "tomorrow_watch": holding in {"hold", "watch"}, "near_target": near_target,
            "near_stop": near_stop, "setup_triggered": trigger in {"triggered", "inside_zone"},
            "setup_invalidated": trigger == "invalidated",
        },
    }
    if window == "post_close_1500":
        result.update(evaluate_post_close(result, setup_card))
    without_hash = dict(result)
    result["source_payload_hash"] = stable_hash(without_hash)
    return result


def evaluate_post_close(observed: dict[str, Any], setup: dict[str, Any]) -> dict[str, Any]:
    actual_open, actual_high = number(observed.get("session_open")), number(observed.get("session_high"))
    actual_low, actual_close = number(observed.get("session_low")), number(observed.get("current_price"))
    actual_complete = None not in (actual_open, actual_high, actual_low, actual_close)
    no_trade = setup.get("entry_readiness") == "no_trade" or setup.get("strategy_type") == "no_trade"
    trigger_state = str(observed.get("entry_trigger_state") or "unavailable")
    triggered = trigger_state in {"triggered", "inside_zone", "invalidated"}
    entry = number(observed.get("entry_trigger_price"))
    stop, target1, target2 = number(observed.get("stop_level")), number(observed.get("target_1")), number(observed.get("target_2"))
    target1_hit = bool(triggered and actual_high is not None and target1 is not None and actual_high >= target1)
    target2_hit = bool(triggered and actual_high is not None and target2 is not None and actual_high >= target2)
    stop_hit = bool(triggered and actual_low is not None and stop is not None and actual_low <= stop)
    if no_trade:
        outcome = "no_trade"
    elif not actual_complete:
        outcome = "pending"
    elif not triggered:
        outcome = "not_triggered"
    elif stop_hit:
        outcome = "fail"
    elif target1_hit:
        outcome = "hit"
    else:
        outcome = "pending"
    mfe = None if not triggered or entry in (None, 0) or actual_high is None else round((actual_high - entry) / entry * 100, 4)
    mae = None if not triggered or entry in (None, 0) or actual_low is None else round((actual_low - entry) / entry * 100, 4)
    direction = setup.get("predicted_direction")
    direction_hit = None if not actual_complete or direction not in {"bullish", "bearish", "neutral"} else (
        actual_close > actual_open if direction == "bullish" else actual_close < actual_open if direction == "bearish" else abs(actual_close - actual_open) / actual_open <= 0.005
    )
    prediction_status = str(setup.get("prediction_status") or "unavailable")
    return {
        "actual_open": actual_open, "actual_high": actual_high, "actual_low": actual_low,
        "actual_close": actual_close, "actual_volume": observed.get("session_volume"),
        "actual_status": "complete" if actual_complete else "unavailable",
        "actual_missing_reason": None if actual_complete else "observed_post_close_ohlcv_unavailable",
        "prediction_status": prediction_status,
        "prediction_missing_reason": None if prediction_status in {"active", "no_trade"} else "upstream_prediction_missing",
        "predicted_direction": setup.get("predicted_direction"), "predicted_low": setup.get("predicted_low"),
        "predicted_high": setup.get("predicted_high"), "prediction_source_window": "pre_open_0700",
        "prediction_snapshot_id": observed.get("source_snapshot_id"), "prediction_revision": observed.get("source_revision"),
        "prediction_payload_hash": observed.get("parent_source_payload_hash"),
        "entry_triggered": triggered, "entry_trigger_price": entry,
        "target_1_hit": target1_hit, "target_2_hit": target2_hit, "stop_hit": stop_hit,
        "direction_hit": direction_hit, "canonical_outcome": outcome, "outcome": outcome,
        "mfe_reference_price": entry if triggered else None, "mae_reference_price": entry if triggered else None,
        "mfe_pct": mfe if triggered else "not_applicable", "mae_pct": mae if triggered else "not_applicable",
        "false_breakout": bool(triggered and stop_hit and actual_high is not None and entry is not None and actual_high > entry),
        "review_snapshot": {
            "status": outcome, "canonical_outcome": outcome,
            "entry_result": "triggered" if triggered else "not_triggered" if actual_complete else "pending",
            "target_1_result": "hit" if target1_hit else "not_hit" if actual_complete else "pending",
            "target_2_result": "hit" if target2_hit else "not_hit" if actual_complete else "pending",
            "stop_result": "hit" if stop_hit else "not_hit" if actual_complete else "pending",
            "direction_result": "hit" if direction_hit is True else "fail" if direction_hit is False else "pending",
            "actual_range": {"low": actual_low, "high": actual_high}, "mfe": mfe if triggered else "not_applicable",
            "mae": mae if triggered else "not_applicable", "false_breakout": bool(triggered and stop_hit),
        },
    }


def aggregate_cards(window: str, cards: list[dict[str, Any]]) -> dict[str, Any]:
    symbols = [str(card.get("symbol") or card.get("stock_id") or "") for card in cards]
    if len(symbols) != len(set(symbols)):
        raise ValueError("duplicate_tw_structured_symbol")
    base = {
        "tracking_count": len(cards), "structured_card_count": len(cards), "symbols": symbols,
        "data_complete_count": sum(card.get("data_status") == "complete" for card in cards),
        "data_partial_count": sum(card.get("data_status") == "partial" for card in cards),
        "data_unavailable_count": sum(card.get("data_status") == "unavailable" for card in cards),
        "triggered_count": sum(card.get("entry_trigger_state") in {"triggered", "inside_zone"} for card in cards),
        "invalidated_count": sum(card.get("entry_trigger_state") == "invalidated" for card in cards),
        "still_actionable_count": sum(card.get("intraday_action") in {"maintain_watch", "entry_triggered_hold", "wait_for_volume", "target_near"} for card in cards),
        "volume_confirmed_count": sum(card.get("volume_confirmation_state") in {"strong", "confirmed"} for card in cards),
        "no_trade_count": sum(card.get("intraday_action") == "no_trade" for card in cards),
        "near_stop_count": sum(card.get("near_stop") is True for card in cards),
        "near_target_count": sum(card.get("near_target") is True for card in cards),
    }
    if window == "pre_close_1335":
        priority_order = {"reduce": 0, "avoid_overnight": 1, "hold": 2, "watch": 3, "no_trade": 4, "unavailable": 5}
        ranking = sorted(cards, key=lambda card: (priority_order.get(str(card.get("holding_decision")), 9), abs(number(card.get("distance_to_stop_pct")) or 999), str(card.get("symbol"))))
        groups = {name: [str(card.get("symbol")) for card in ranking if card.get("holding_decision") == name] for name in priority_order}
        base.update({
            "priority_groups": groups,
            "priority_symbols": [str(card.get("symbol")) for card in ranking if card.get("holding_decision") in {"reduce", "avoid_overnight", "hold"}],
            "summary_market_data_time": aggregate_card_timestamp(cards),
            "next_session_actions": {str(card.get("symbol")): next_session_action(card) for card in cards},
        })
    if window == "post_close_1500":
        outcomes = Counter(str(card.get("canonical_outcome") or "pending") for card in cards)
        distribution = {key: int(outcomes.get(key, 0)) for key in OUTCOMES}
        base.update({
            "outcome_counts": distribution, "review_card_count": len(cards),
            "completed_review_count": sum(distribution[key] for key in OUTCOMES if key != "pending"),
            "pending_review_count": distribution["pending"], "review_universe_count": len(cards),
        })
    base["summary_hash"] = stable_hash(base)
    return base


def validate_payload(window: str, payload: dict[str, Any]) -> list[str]:
    key = {"intraday_1305": "structured_intraday_cards", "pre_close_1335": "structured_pre_close_cards", "post_close_1500": "structured_review_cards"}.get(window)
    if not key:
        return ["unsupported_window"]
    cards = payload.get(key) if isinstance(payload.get(key), list) else []
    errors: list[str] = []
    tracking = int(payload.get("tracking_stock_count") or payload.get("stock_count") or 0)
    if tracking and len(cards) != tracking:
        errors.append("tracking_structured_count_mismatch")
    symbols = [str(card.get("symbol") or card.get("stock_id") or "") for card in cards if isinstance(card, dict)]
    if len(symbols) != len(set(symbols)):
        errors.append("duplicate_symbol")
    if any(card.get("window") != window or card.get("market") != "TW" for card in cards if isinstance(card, dict)):
        errors.append("window_or_market_identity")
    if any(not card.get("setup_id") or card.get("parent_setup_id") != card.get("setup_id") for card in cards if isinstance(card, dict)):
        errors.append("setup_identity")
    if window in {"intraday_1305", "pre_close_1335"} and cards and all(card.get("current_price") is None for card in cards):
        errors.append("all_observed_market_data_unavailable")
    if window == "pre_close_1335" and cards and all(card.get("market_data_as_of") is None and card.get("near_stop") is False and card.get("near_target") is False for card in cards):
        errors.append("all_pre_close_proximity_unavailable")
    if window == "post_close_1500" and cards and all(card.get("actual_status") != "complete" for card in cards):
        errors.append("all_post_close_actual_ohlc_unavailable")
    summary = payload.get("tw_window_summary")
    try:
        expected = aggregate_cards(window, cards)
    except ValueError:
        expected = None
    if expected is not None and summary != expected:
        errors.append("summary_mismatch")
    return errors


def render_intraday_email(payload: dict[str, Any], canonical_url: str) -> str:
    summary = payload.get("tw_window_summary") or aggregate_cards("intraday_1305", payload.get("structured_intraday_cards") or [])
    cards = payload.get("structured_intraday_cards") or []
    ranked = sorted(cards, key=lambda card: ({"stop_invalidated": 0, "cancel_chase": 1, "entry_triggered_hold": 2, "target_near": 3}.get(str(card.get("intraday_action")), 8), str(card.get("symbol"))))
    lines = [
        "【Stock AI】13:05 台股盤中追蹤", f"行情時間：{format_timestamp(payload.get('source_data_time'))}",
        f"已觸發 {summary['triggered_count']}｜失效 {summary['invalidated_count']}｜仍可行動 {summary['still_actionable_count']}",
        f"量能確認 {summary['volume_confirmed_count']}｜行情不足 {summary['data_unavailable_count']}", "重點變化：",
    ]
    for card in ranked[:3]:
        lines.append(f"- {card.get('symbol')}：目前 {card.get('current_price') if card.get('current_price') is not None else '尚未取得'}｜{localize(card.get('entry_trigger_state'))}｜{safe_public_text(card.get('action_change_reason'))}")
    lines += ["完整報告：", canonical_url, "僅供研究參考，非交易指令。"]
    return "\n".join(lines)


def render_intraday_line(payload: dict[str, Any], canonical_url: str) -> str:
    summary = payload.get("tw_window_summary") or aggregate_cards("intraday_1305", payload.get("structured_intraday_cards") or [])
    return "\n".join([
        "【Stock AI】13:05 台股盤中", f"已觸發 {summary['triggered_count']}｜失效 {summary['invalidated_count']}｜仍可行動 {summary['still_actionable_count']}",
        f"量能確認 {summary['volume_confirmed_count']}｜行情不足 {summary['data_unavailable_count']}", "完整報告：", canonical_url,
    ])
