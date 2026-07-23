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
SCHEMA_VERSION = "tw_intraday_close_lifecycle_v1"
TW_WINDOWS = ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")
OBSERVED_WINDOWS = TW_WINDOWS[1:]
PLAN_STATUSES = ("no_trade", "watch", "active")
TRIGGER_STATUSES = ("not_applicable", "not_triggered", "triggered", "invalidated")
INTRADAY_ACTIONS = ("hold", "wait_volume", "reduce", "exit", "no_trade")
OVERNIGHT_ACTIONS = ("hold", "hold_with_protection", "watch", "reduce", "exit", "no_trade")
TRADE_OUTCOMES = ("win", "loss", "not_triggered", "no_trade", "open_at_close", "pending_evidence")
PREDICTION_RESULTS = ("hit", "partial_hit", "miss", "not_applicable")
EVIDENCE_STATUSES = ("complete", "partial", "missing", "not_applicable")
RISK_STATES = ("normal", "target_near", "stop_near", "both_near", "invalidated", "not_applicable")
TARGET_NEAR_THRESHOLD_PCT = 1.5
STOP_NEAR_THRESHOLD_PCT = 1.5

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
    "wait_volume": "等待量能確認", "exit": "退出／停止原策略",
    "hold_with_protection": "可留倉但需保護", "open_at_close": "收盤時交易尚未結束",
    "pending_evidence": "證據不足", "win": "交易命中", "loss": "交易失敗",
    "both_near": "雙向臨界", "not_started": "尚未開始", "closed": "已結束",
    "not_applicable": "不適用", "active": "正式交易計畫",
    "unknown": "尚未判定", "neutral": "中性", "downtrend": "偏空趨勢",
    "uptrend": "偏多趨勢", "strong_uptrend": "強勢多頭",
}

PRE_OPEN_ACTION_GATE = {"minimum_reward_risk": 1.0}
NEWS_DIRECTIONS = {"bullish", "neutral", "bearish", "unavailable"}


def canonical_news_direction(value: Any, detail: Any = None) -> str:
    raw = str(value or "").strip().lower().replace("偏多", "bullish").replace("偏空", "bearish").replace("中性", "neutral")
    if raw in NEWS_DIRECTIONS:
        return raw
    text = str(detail or "")
    if any(token in text for token in ("消息面方向：偏多", "新聞方向：偏多", "強烈偏多")):
        return "bullish"
    if any(token in text for token in ("消息面方向：偏空", "新聞方向：偏空", "強烈偏空")):
        return "bearish"
    if any(token in text for token in ("消息面方向：中性", "新聞方向：中性")):
        return "neutral"
    return "unavailable"


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
    reward_risk = number(tactical.get("reward_risk"))
    readiness = (
        "no_trade" if no_trade else "entry_ready" if safe_levels and data_quality in {"complete", "partial"}
        and reward_risk is not None and reward_risk >= PRE_OPEN_ACTION_GATE["minimum_reward_risk"]
        and tactical.get("chase_risk") != "high" else "watch" if safe_levels else "unavailable"
    )
    missing = set(str(item) for item in result.get("missing_fields", []) if item)
    for name, value in (("entry", entry_low), ("stop", stop_level), ("target_1", target_1)):
        if value is None and not no_trade:
            missing.add(name)
    if missing and readiness == "entry_ready":
        readiness = "watch"
    normalized_data_status = "partial" if missing or data_quality in {"partial", "limited"} else "unavailable" if data_quality == "insufficient" else "complete"
    news_text = sanitize_text(result.get("news_summary"), "新聞分析暫時無法取得")
    news_unavailable = "news" in missing or "暫時無法取得" in news_text or "尚未取得" in news_text
    result.update({
        "schema_version": "tw_pre_open_structured_decision_v2",
        "setup_id": setup, "parent_setup_id": None, "strategy_type": strategy_type,
        "source_window": "pre_open_0700", "source_revision": source_revision,
        "entry_readiness": readiness, "entry_low": entry_low, "entry_high": entry_high,
        "entry_zone": tactical.get("entry_zone"), "stop_level": stop_level,
        "target_1": target_1, "target_2": target_2,
        "target_level": tactical.get("target_1"), "risk_reward": reward_risk,
        "action": sanitize_text(tactical.get("action") or result.get("action")),
        "entry_condition": sanitize_text((tactical.get("playbook") or {}).get("entry_condition")),
        "chase_risk": str(tactical.get("chase_risk") or result.get("chase_risk") or "unavailable"),
        "event_risk": str(tactical.get("event_risk") or result.get("event_risk") or "unavailable"),
        "no_trade_reason": sanitize_text("；".join(tactical.get("risk_reasons") or []), "不適用") if no_trade else None,
        "do_not_trade_reason": sanitize_text("；".join(tactical.get("risk_reasons") or []), "不適用") if no_trade else None,
        "data_status": normalized_data_status,
        "availability_status": normalized_data_status,
        "missing_fields": sorted(missing),
        "technical_summary": localize(result.get("technical_summary")),
        "chip_summary": sanitize_text(result.get("chip_summary")),
        "adr_context": sanitize_text(result.get("adr_context")),
        "overnight_context": sanitize_text(result.get("overnight_context")),
        "news_summary": news_text,
        "news_status": "unavailable" if news_unavailable else "available",
        "news_source_class": "unavailable" if news_unavailable else str(result.get("news_source_class") or "general_media"),
        "news_direction": "unavailable" if news_unavailable else canonical_news_direction(result.get("news_direction"), news_text),
        "news_confidence": None if news_unavailable else result.get("news_confidence"),
        "news_strategy_impact": "no_material_effect" if news_unavailable else result.get("news_strategy_impact"),
        "reasoning": sanitize_text("；".join(tactical.get("reasons") or []) or result.get("reasoning")),
        "risk_summary": sanitize_text("；".join(tactical.get("risk_reasons") or []) or result.get("risk_summary")),
        "strategies": {"daily_tactical": dict(tactical)},
        "prediction_status": "no_trade" if no_trade else "active" if safe_levels else "unavailable",
        "predicted_direction": tactical.get("direction"),
        "predicted_low": entry_low,
        "predicted_high": target_1,
        "prediction_method": "tw_daily_tactical_entry_to_target_corridor_v1",
        "opportunity_group": "no_trade" if no_trade else "opportunity" if readiness == "entry_ready" else "watch" if readiness == "watch" else "unavailable",
        "decision_category": "no_trade" if no_trade else "top_opportunity" if readiness == "entry_ready" else "watch_only" if readiness == "watch" else "unavailable",
        "actionable": readiness == "entry_ready", "watch_only": readiness == "watch", "no_trade": no_trade,
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


def _plan_status(setup: dict[str, Any], *, no_trade: bool) -> str:
    if no_trade:
        return "no_trade"
    if setup.get("entry_readiness") == "entry_ready" or setup.get("actionable") is True:
        return "active"
    if all(number(setup.get(key)) is not None for key in ("entry_low", "entry_high", "stop_level", "target_1")):
        return "active"
    return "watch"


def _canonical_trigger(raw: Any, *, plan_status: str) -> str:
    if plan_status == "no_trade":
        return "not_applicable"
    value = str(raw or "")
    if value in {"triggered", "inside_zone"}:
        return "triggered"
    if value == "invalidated":
        return "invalidated"
    if value in {"not_reached", "passed_without_safe_entry"}:
        return "not_triggered"
    return "not_triggered"


def _risk_state(*, plan_status: str, trigger_status: str, near_target: bool, near_stop: bool) -> str:
    if plan_status == "no_trade":
        return "not_applicable"
    if trigger_status == "invalidated":
        return "invalidated"
    if near_target and near_stop:
        return "both_near"
    if near_target:
        return "target_near"
    if near_stop:
        return "stop_near"
    return "normal"


def _prediction_result(setup: dict[str, Any], actual_low: float | None, actual_high: float | None, *, no_trade: bool) -> str:
    if no_trade:
        return "not_applicable"
    predicted_low = number(setup.get("predicted_low"))
    predicted_high = number(setup.get("predicted_high"))
    if None in (predicted_low, predicted_high, actual_low, actual_high):
        return "not_applicable"
    assert predicted_low is not None and predicted_high is not None and actual_low is not None and actual_high is not None
    if actual_low <= predicted_low <= actual_high and actual_low <= predicted_high <= actual_high:
        return "hit"
    if max(predicted_low, actual_low) <= min(predicted_high, actual_high):
        return "partial_hit"
    return "miss"


def _identity_transition(window: str, card: dict[str, Any], state: str) -> dict[str, Any]:
    return {
        "source_window": window,
        "source_snapshot_id": card.get("source_snapshot_id"),
        "revision": card.get("source_revision"),
        "source_hash": card.get("parent_source_payload_hash") or card.get("source_payload_hash"),
        "effective_date": card.get("trading_date"),
        "symbol": card.get("symbol") or card.get("stock_id"),
        "state": state,
    }


def normalize_lifecycle_card(card: dict[str, Any], window: str) -> dict[str, Any]:
    """Project legacy immutable cards into the canonical lifecycle for presentation.

    The function is pure and never mutates archived payloads.
    """
    item = dict(card)
    tactical = ((item.get("strategies") or {}).get("daily_tactical") or {}) if isinstance(item.get("strategies"), dict) else {}
    no_trade = bool(
        item.get("plan_status") == "no_trade"
        or item.get("entry_readiness") == "no_trade"
        or item.get("intraday_action") == "no_trade"
        or item.get("holding_decision") == "no_trade"
        or tactical.get("setup_type") == "no_trade"
    )
    plan_status = str(item.get("plan_status") or _plan_status(item, no_trade=no_trade))
    trigger_status = str(item.get("trigger_status") or _canonical_trigger(item.get("entry_trigger_state"), plan_status=plan_status))
    near_target = bool(item.get("near_target"))
    near_stop = bool(item.get("near_stop"))
    risk_state = str(item.get("risk_state") or _risk_state(
        plan_status=plan_status, trigger_status=trigger_status, near_target=near_target, near_stop=near_stop,
    ))
    raw_action = str(item.get("intraday_action") or "")
    intraday_action = str(item.get("canonical_intraday_action") or (
        "no_trade" if plan_status == "no_trade" else
        "exit" if trigger_status == "invalidated" or raw_action in {"stop_invalidated", "cancel_chase"} else
        "reduce" if raw_action == "reduce_risk" or near_stop else
        "hold" if raw_action in {"entry_triggered_hold", "target_near"} else
        "wait_volume"
    ))
    overnight_action = str(item.get("overnight_action") or (
        "no_trade" if plan_status == "no_trade" else
        "exit" if trigger_status == "invalidated" or intraday_action == "exit" else
        "hold_with_protection" if risk_state == "both_near" else
        "reduce" if intraday_action == "reduce" else
        "hold" if intraday_action == "hold" else "watch"
    ))
    item.update({
        "plan_status": plan_status,
        "trigger_status": trigger_status,
        "canonical_intraday_action": intraday_action,
        "overnight_action": overnight_action,
        "risk_state": risk_state,
        "target_near_threshold_pct": number(item.get("target_near_threshold_pct")) or TARGET_NEAR_THRESHOLD_PCT,
        "stop_near_threshold_pct": number(item.get("stop_near_threshold_pct")) or STOP_NEAR_THRESHOLD_PCT,
        "volume_ratio_basis": item.get("volume_ratio_basis") or item.get("volume_baseline_method") or "historical_20d_daily_mean_prorated_by_session_elapsed_v1",
        "lookback_sessions": int(item.get("lookback_sessions") or 20),
        "evidence_status": item.get("evidence_status") or (
            "not_applicable" if plan_status == "no_trade" else
            "complete" if item.get("data_status") == "complete" else
            "partial" if item.get("data_status") == "partial" else "missing"
        ),
    })
    if plan_status == "no_trade":
        item.update({
            "entry_trigger_state": "not_applicable", "trigger_status": "not_applicable",
            "distance_to_stop_pct": None, "distance_to_target_1_pct": None,
            "distance_to_target_2_pct": None, "near_stop": False, "near_target": False,
            "risk_state": "not_applicable",
        })
    if window == "post_close_1500":
        actual_complete = item.get("actual_status") == "complete" or all(
            number(item.get(key)) is not None for key in ("actual_open", "actual_high", "actual_low", "actual_close")
        )
        legacy = str(item.get("canonical_outcome") or item.get("outcome") or "")
        trade_outcome = str(item.get("trade_outcome") or (
            "no_trade" if plan_status == "no_trade" else
            "win" if legacy == "hit" else "loss" if legacy == "fail" else
            "not_triggered" if legacy == "not_triggered" else
            "open_at_close" if actual_complete and trigger_status == "triggered" else "pending_evidence"
        ))
        prediction_result = str(
            (item.get("prediction_evaluation") or {}).get("range_result")
            if isinstance(item.get("prediction_evaluation"), dict) else ""
        ) or str(item.get("prediction_range_result") or _prediction_result(
            item, number(item.get("actual_low")), number(item.get("actual_high")), no_trade=plan_status == "no_trade",
        ))
        item.update({
            "trade_outcome": trade_outcome,
            "prediction_evaluation": {"range_result": prediction_result},
            "prediction_range_result": prediction_result,
            "trade_status": item.get("trade_status") or (
                "not_applicable" if trade_outcome == "no_trade" else "not_started" if trade_outcome == "not_triggered"
                else "open" if trade_outcome == "open_at_close" else "closed" if trade_outcome in {"win", "loss"} else "not_started"
            ),
            "evidence_status": "not_applicable" if plan_status == "no_trade" else "complete" if actual_complete else "missing",
        })
        if plan_status == "no_trade":
            item.update({
                "predicted_direction": "not_applicable", "predicted_low": None, "predicted_high": None,
                "entry_triggered": None, "target_1_hit": None, "target_2_hit": None, "stop_hit": None,
                "mfe_pct": "not_applicable", "mae_pct": "not_applicable",
                "mfe": {"status": "not_applicable"}, "mae": {"status": "not_applicable"},
            })
        elif item.get("entry_triggered"):
            resolution = "minute_5" if item.get("evidence_resolution") in {"minute_5", "intraday_bars"} else "intraday_high_low"
            item["mfe"] = item.get("mfe") if isinstance(item.get("mfe"), dict) else {
                "absolute": None, "pct": number(item.get("mfe_pct")), "unit": "pct",
                "reference_price": number(item.get("mfe_reference_price")),
                "reference_type": "first_entry_trigger", "resolution": resolution,
            }
            item["mae"] = item.get("mae") if isinstance(item.get("mae"), dict) else {
                "absolute": None, "pct": number(item.get("mae_pct")), "unit": "pct",
                "reference_price": number(item.get("mae_reference_price")),
                "reference_type": "first_entry_trigger", "resolution": resolution,
            }
    return item


def build_observed_card(
    *, window: str, setup_card: dict[str, Any], quote: dict[str, Any] | None,
    trading_date: str, generated_at: str, source_snapshot_id: str | None,
    source_revision: int, source_payload_hash: str | None,
    prior_card: dict[str, Any] | None = None,
    lifecycle_timeline: list[dict[str, Any]] | None = None,
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
    near_stop = distance_stop is not None and abs(distance_stop) <= STOP_NEAR_THRESHOLD_PCT
    near_target = distance_t1 is not None and abs(distance_t1) <= TARGET_NEAR_THRESHOLD_PCT
    plan_status = _plan_status(setup_card, no_trade=no_trade)
    trigger_status = _canonical_trigger(trigger, plan_status=plan_status)
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
    canonical_action = (
        "no_trade" if no_trade else "exit" if action in {"stop_invalidated", "cancel_chase"} else
        "reduce" if action == "reduce_risk" else "hold" if action in {"entry_triggered_hold", "target_near"} else
        "wait_volume"
    )
    risk_state = _risk_state(
        plan_status=plan_status, trigger_status=trigger_status, near_target=near_target, near_stop=near_stop,
    )
    overnight = (
        "no_trade" if no_trade else "exit" if trigger_status == "invalidated" or canonical_action == "exit" else
        "hold_with_protection" if risk_state == "both_near" else "reduce" if canonical_action == "reduce" else
        "hold" if canonical_action == "hold" else "watch"
    )
    holding = overnight
    evidence_status = "not_applicable" if no_trade else "complete" if data_status == "complete" else "partial" if data_status == "partial" else "missing"
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
        "source_timezone": quote.get("source_timezone") or "Asia/Taipei",
        "source_record_time_kind": quote.get("source_record_time_kind") or "exchange_local_datetime",
        "normalized_timezone": quote.get("normalized_timezone") or "Asia/Taipei",
        "freshness_status": "fresh" if observed_at else "unavailable",
        "entry_low": entry_low, "entry_high": entry_high, "entry_trigger_state": trigger,
        "plan_status": plan_status, "trigger_status": trigger_status,
        "entry_trigger_price": trigger_price, "entry_trigger_time": observed_at if trigger in {"triggered", "invalidated", "inside_zone"} else None,
        "volume_baseline": baseline, "volume_baseline_method": "historical_20d_daily_mean_prorated_by_session_elapsed_v1",
        "volume_ratio_basis": "historical_20d_daily_mean_prorated_by_session_elapsed_v1",
        "lookback_sessions": 20, "volume_ratio_as_of": observed_at,
        "volume_ratio": ratio, "volume_confirmation_state": volume_state,
        "stop_level": stop, "target_1": target1, "target_2": target2,
        "distance_to_stop_pct": distance_stop, "distance_to_target_1_pct": distance_t1,
        "distance_to_target_2_pct": distance_t2, "near_stop": near_stop, "near_target": near_target,
        "pre_open_action": setup_card.get("action"), "intraday_action": action,
        "canonical_intraday_action": canonical_action,
        "action_change_reason": reason, "holding_decision": holding, "holding_reason": reason,
        "overnight_action": overnight, "risk_state": risk_state,
        "target_near_threshold_pct": TARGET_NEAR_THRESHOLD_PCT,
        "stop_near_threshold_pct": STOP_NEAR_THRESHOLD_PCT,
        "chase_risk": setup_card.get("chase_risk"), "overnight_gap_risk": setup_card.get("gap_risk"),
        "event_risk": setup_card.get("event_risk"), "tomorrow_watch_status": holding in {"hold", "watch"},
        "data_status": data_status, "evidence_status": evidence_status,
        "missing_fields": sorted(missing), "strategies": {"daily_tactical": dict(tactical)},
        "decision_state": {
            "hold_candidate": holding in {"hold", "hold_with_protection"}, "avoid_hold": holding in {"reduce", "exit"},
            "no_trade": no_trade, "late_session_risk": holding in {"hold_with_protection", "reduce", "exit"},
            "tomorrow_watch": holding in {"hold", "watch"}, "near_target": near_target,
            "near_stop": near_stop, "setup_triggered": trigger in {"triggered", "inside_zone"},
            "setup_invalidated": trigger == "invalidated",
        },
    }
    timeline = [dict(item) for item in (lifecycle_timeline or []) if isinstance(item, dict)]
    if not timeline:
        timeline.append(_identity_transition("pre_open_0700", result, plan_status))
    if prior_card:
        previous = normalize_lifecycle_card(prior_card, str(prior_card.get("window") or "intraday_1305"))
        timeline.append(_identity_transition(
            str(previous.get("window") or "intraday_1305"), previous,
            str(previous.get("overnight_action") or previous.get("canonical_intraday_action") or previous.get("trigger_status")),
        ))
    current_state = canonical_action if window == "intraday_1305" else overnight if window == "pre_close_1335" else "pending_evaluation"
    timeline.append({
        "source_window": window, "source_snapshot_id": None, "revision": None,
        "source_hash": None, "effective_date": trading_date, "symbol": symbol,
        "state": current_state, "identity_status": "awaiting_snapshot_admission",
    })
    result["lifecycle_timeline"] = timeline
    if window == "post_close_1500":
        result.update(evaluate_post_close(result, setup_card))
        result["lifecycle_timeline"][-1]["state"] = result["trade_outcome"]
    without_hash = dict(result)
    result["source_payload_hash"] = stable_hash(without_hash)
    return result


def evaluate_post_close(observed: dict[str, Any], setup: dict[str, Any]) -> dict[str, Any]:
    actual_open, actual_high = number(observed.get("session_open")), number(observed.get("session_high"))
    actual_low, actual_close = number(observed.get("session_low")), number(observed.get("current_price"))
    actual_complete = None not in (actual_open, actual_high, actual_low, actual_close)
    no_trade = setup.get("entry_readiness") == "no_trade" or setup.get("strategy_type") == "no_trade"
    trigger_state = str(observed.get("trigger_status") or _canonical_trigger(
        observed.get("entry_trigger_state"), plan_status="no_trade" if no_trade else _plan_status(setup, no_trade=False),
    ))
    triggered = trigger_state in {"triggered", "invalidated"}
    entry = number(observed.get("entry_trigger_price"))
    stop, target1, target2 = number(observed.get("stop_level")), number(observed.get("target_1")), number(observed.get("target_2"))
    target1_hit = bool(triggered and actual_high is not None and target1 is not None and actual_high >= target1)
    target2_hit = bool(triggered and actual_high is not None and target2 is not None and actual_high >= target2)
    stop_hit = bool(triggered and actual_low is not None and stop is not None and actual_low <= stop)
    if no_trade:
        trade_outcome = "no_trade"
    elif not actual_complete:
        trade_outcome = "pending_evidence"
    elif not triggered:
        trade_outcome = "not_triggered"
    elif stop_hit:
        trade_outcome = "loss"
    elif target1_hit:
        trade_outcome = "win"
    else:
        trade_outcome = "open_at_close"
    mfe = None if not triggered or entry in (None, 0) or actual_high is None else round((actual_high - entry) / entry * 100, 4)
    mae = None if not triggered or entry in (None, 0) or actual_low is None else round((actual_low - entry) / entry * 100, 4)
    direction = setup.get("predicted_direction")
    direction_hit = None if not actual_complete or direction not in {"bullish", "bearish", "neutral"} else (
        actual_close > actual_open if direction == "bullish" else actual_close < actual_open if direction == "bearish" else abs(actual_close - actual_open) / actual_open <= 0.005
    )
    prediction_status = str(setup.get("prediction_status") or "unavailable")
    prediction_result = _prediction_result(setup, actual_low, actual_high, no_trade=no_trade)
    evidence_status = "not_applicable" if no_trade else "complete" if actual_complete else "missing"
    trade_status = "not_applicable" if no_trade else "not_started" if trade_outcome == "not_triggered" else "open" if trade_outcome == "open_at_close" else "closed" if trade_outcome in {"win", "loss"} else "not_started"
    canonical_outcome = {
        "win": "hit", "loss": "fail", "not_triggered": "not_triggered",
        "no_trade": "no_trade", "open_at_close": "pending", "pending_evidence": "pending",
    }[trade_outcome]
    mfe_contract = {
        "absolute": None if mfe is None or entry is None else round((actual_high or entry) - entry, 4),
        "pct": mfe, "unit": "pct", "reference_price": entry,
        "reference_type": "first_entry_trigger", "resolution": "intraday_high_low",
    } if triggered else {"status": "not_applicable"}
    mae_contract = {
        "absolute": None if mae is None or entry is None else round((actual_low or entry) - entry, 4),
        "pct": mae, "unit": "pct", "reference_price": entry,
        "reference_type": "first_entry_trigger", "resolution": "intraday_high_low",
    } if triggered else {"status": "not_applicable"}
    return {
        "actual_open": actual_open, "actual_high": actual_high, "actual_low": actual_low,
        "actual_close": actual_close, "actual_volume": observed.get("session_volume"),
        "actual_status": "complete" if actual_complete else "unavailable",
        "actual_missing_reason": None if actual_complete else "observed_post_close_ohlcv_unavailable",
        "prediction_status": prediction_status, "prediction_evaluation": {"range_result": prediction_result},
        "prediction_range_result": prediction_result,
        "prediction_missing_reason": None if prediction_status in {"active", "no_trade"} else "upstream_prediction_missing",
        "predicted_direction": setup.get("predicted_direction"), "predicted_low": setup.get("predicted_low"),
        "predicted_high": setup.get("predicted_high"), "prediction_source_window": "pre_open_0700",
        "prediction_snapshot_id": observed.get("source_snapshot_id"), "prediction_revision": observed.get("source_revision"),
        "prediction_payload_hash": observed.get("parent_source_payload_hash"),
        "entry_triggered": triggered, "entry_trigger_price": entry,
        "target_1_hit": target1_hit, "target_2_hit": target2_hit, "stop_hit": stop_hit,
        "direction_hit": direction_hit, "canonical_outcome": canonical_outcome, "outcome": canonical_outcome,
        "trade_outcome": trade_outcome, "trade_status": trade_status, "evidence_status": evidence_status,
        "mfe_reference_price": entry if triggered else None, "mae_reference_price": entry if triggered else None,
        "mfe_pct": mfe if triggered else "not_applicable", "mae_pct": mae if triggered else "not_applicable",
        "mfe": mfe_contract, "mae": mae_contract,
        "false_breakout": bool(triggered and stop_hit and actual_high is not None and entry is not None and actual_high > entry),
        "review_snapshot": {
            "status": trade_outcome, "canonical_outcome": canonical_outcome,
            "trade_outcome": trade_outcome, "prediction_range_result": prediction_result,
            "entry_result": "not_applicable" if no_trade else "triggered" if triggered else "not_triggered" if actual_complete else "pending_evidence",
            "target_1_result": "not_applicable" if no_trade else "hit" if target1_hit else "not_hit" if actual_complete else "pending_evidence",
            "target_2_result": "not_applicable" if no_trade else "hit" if target2_hit else "not_hit" if actual_complete else "pending_evidence",
            "stop_result": "not_applicable" if no_trade else "hit" if stop_hit else "not_hit" if actual_complete else "pending_evidence",
            "direction_result": prediction_result,
            "actual_range": {"low": actual_low, "high": actual_high}, "mfe": mfe if triggered else "not_applicable",
            "mae": mae if triggered else "not_applicable", "false_breakout": bool(triggered and stop_hit),
        },
    }


def aggregate_cards(window: str, cards: list[dict[str, Any]]) -> dict[str, Any]:
    cards = [normalize_lifecycle_card(card, window) for card in cards if isinstance(card, dict)]
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
        "plan_status_counts": {name: sum(card.get("plan_status") == name for card in cards) for name in PLAN_STATUSES},
        "plan_status_symbols": {name: [str(card.get("symbol")) for card in cards if card.get("plan_status") == name] for name in PLAN_STATUSES},
        "trigger_status_counts": {name: sum(card.get("trigger_status") == name for card in cards) for name in TRIGGER_STATUSES},
        "intraday_action_counts": {name: sum(card.get("canonical_intraday_action") == name for card in cards) for name in INTRADAY_ACTIONS},
        "intraday_action_symbols": {name: [str(card.get("symbol")) for card in cards if card.get("canonical_intraday_action") == name] for name in INTRADAY_ACTIONS},
        "risk_state_counts": {name: sum(card.get("risk_state") == name for card in cards) for name in RISK_STATES},
        "risk_state_symbols": {name: [str(card.get("symbol")) for card in cards if card.get("risk_state") == name] for name in RISK_STATES},
        "target_near_threshold_pct": TARGET_NEAR_THRESHOLD_PCT,
        "stop_near_threshold_pct": STOP_NEAR_THRESHOLD_PCT,
        "volume_ratio_contract": {
            "basis": "historical_20d_daily_mean_prorated_by_session_elapsed_v1",
            "lookback_sessions": 20,
            "public_description": "近 20 個交易日日均量，依本批次已經過交易時段比例折算",
        },
        "evidence_status_counts": {name: sum(card.get("evidence_status") == name for card in cards) for name in EVIDENCE_STATUSES},
    }
    if window == "pre_close_1335":
        priority_order = {"exit": 0, "reduce": 1, "hold_with_protection": 2, "hold": 3, "watch": 4, "no_trade": 5}
        ranking = sorted(cards, key=lambda card: (priority_order.get(str(card.get("overnight_action")), 9), abs(number(card.get("distance_to_stop_pct")) or 999), str(card.get("symbol"))))
        groups = {name: [str(card.get("symbol")) for card in ranking if card.get("overnight_action") == name] for name in OVERNIGHT_ACTIONS}
        priority = [str(card.get("symbol")) for card in ranking if card.get("overnight_action") in {"exit", "reduce", "hold_with_protection", "hold"}]
        base.update({
            "overnight_action_counts": {name: len(groups[name]) for name in OVERNIGHT_ACTIONS},
            "overnight_action_symbols": groups, "priority_groups": groups, "priority_symbols": priority,
            "summary_market_data_time": aggregate_card_timestamp(cards),
            "next_session_actions": {str(card.get("symbol")): next_session_action(card) for card in cards},
            "tomorrow_groups": {
                "priority_watch": groups["hold"] + groups["hold_with_protection"] + groups["watch"],
                "general_tracking": groups["no_trade"],
                "stop_original_strategy": groups["exit"] + groups["reduce"],
            },
        })
    if window == "post_close_1500":
        trade = Counter(str(card.get("trade_outcome") or {
            "hit": "win", "fail": "loss", "pending": "open_at_close",
        }.get(str(card.get("canonical_outcome") or ""), card.get("canonical_outcome") or "pending_evidence")) for card in cards)
        prediction = Counter(str((card.get("prediction_evaluation") or {}).get("range_result") or card.get("prediction_range_result") or "not_applicable") for card in cards)
        trade_distribution = {key: int(trade.get(key, 0)) for key in TRADE_OUTCOMES}
        prediction_distribution = {key: int(prediction.get(key, 0)) for key in PREDICTION_RESULTS}
        legacy = {
            "hit": trade_distribution["win"], "fail": trade_distribution["loss"],
            "not_triggered": trade_distribution["not_triggered"], "no_trade": trade_distribution["no_trade"],
            "pending": trade_distribution["open_at_close"] + trade_distribution["pending_evidence"],
        }
        base.update({
            "prediction_evaluation_counts": prediction_distribution,
            "trade_outcome_counts": trade_distribution, "outcome_counts": legacy,
            "trade_outcome_symbols": {name: [str(card.get("symbol")) for card in cards if str(card.get("trade_outcome") or {"hit": "win", "fail": "loss", "pending": "open_at_close"}.get(str(card.get("canonical_outcome") or ""), card.get("canonical_outcome"))) == name] for name in TRADE_OUTCOMES},
            "review_card_count": len(cards),
            "completed_review_count": sum(trade_distribution[key] for key in TRADE_OUTCOMES if key not in {"open_at_close", "pending_evidence"}),
            "open_at_close_count": trade_distribution["open_at_close"],
            "pending_review_count": trade_distribution["pending_evidence"], "review_universe_count": len(cards),
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
    cards = [normalize_lifecycle_card(card, "intraday_1305") for card in payload.get("structured_intraday_cards") or [] if isinstance(card, dict)]
    summary = aggregate_cards("intraday_1305", cards)
    groups = summary["intraday_action_symbols"]
    ranked = sorted(cards, key=lambda card: ({"exit": 0, "reduce": 1, "wait_volume": 2, "hold": 3, "no_trade": 4}.get(str(card.get("canonical_intraday_action")), 8), str(card.get("symbol"))))
    lines = [
        "【Stock AI】13:05 台股盤中追蹤", f"行情時間：{format_timestamp(payload.get('source_data_time'))}",
        f"正式交易計畫 {summary['plan_status_counts']['active'] + summary['plan_status_counts']['watch']}｜無交易 {summary['plan_status_counts']['no_trade']}",
        f"已觸發 {summary['trigger_status_counts']['triggered']}｜策略失效 {summary['trigger_status_counts']['invalidated']}",
        f"等待量能 {_names(groups['wait_volume'])}｜降低風險 {_names(groups['reduce'])}｜退出原策略 {_names(groups['exit'])}",
        f"接近目標 {_names(summary['risk_state_symbols']['target_near'] + summary['risk_state_symbols']['both_near'])}｜接近停損 {_names(summary['risk_state_symbols']['stop_near'] + summary['risk_state_symbols']['both_near'])}",
        "重點變化：",
    ]
    for card in ranked[:3]:
        lines.append(f"- {card.get('symbol')}：目前 {card.get('current_price') if card.get('current_price') is not None else '尚未取得'}｜{localize(card.get('entry_trigger_state'))}｜{safe_public_text(card.get('action_change_reason'))}")
    lines += ["完整報告：", canonical_url, "僅供研究參考，非交易指令。"]
    return "\n".join(lines)


def render_intraday_line(payload: dict[str, Any], canonical_url: str) -> str:
    cards = [normalize_lifecycle_card(card, "intraday_1305") for card in payload.get("structured_intraday_cards") or [] if isinstance(card, dict)]
    summary = aggregate_cards("intraday_1305", cards)
    groups = summary["intraday_action_symbols"]
    risk = summary["risk_state_symbols"]
    return "\n".join([
        "【Stock AI】13:05 台股盤中",
        f"正式交易計畫 {summary['plan_status_counts']['active'] + summary['plan_status_counts']['watch']}｜無交易 {summary['plan_status_counts']['no_trade']}",
        f"已觸發 {summary['trigger_status_counts']['triggered']}｜策略失效 {summary['trigger_status_counts']['invalidated']}",
        f"等待量能：{_names(groups['wait_volume'])}",
        f"降低風險：{_names(groups['reduce'])}",
        f"退出原策略：{_names(groups['exit'])}",
        f"接近目標：{_names(risk['target_near'] + risk['both_near'])}",
        f"接近停損：{_names(risk['stop_near'] + risk['both_near'])}",
        "完整報告：", canonical_url,
    ])


def _names(values: list[str] | None) -> str:
    return "、".join(values or []) or "無"
