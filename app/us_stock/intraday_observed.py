"""Observed US intraday evidence and deterministic tactical decisions.

This module is intentionally limited to ``US/us_intraday_2300``.  It converts
the quote already acquired by the live pipeline into one structured payload;
renderers and notification formatters must not re-classify the observations.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, time
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
TAIPEI = ZoneInfo("Asia/Taipei")
WINDOW = "us_intraday_2300"
SCHEMA_VERSION = "us_intraday_observed_market_v1"
ENTRY_STATES = {
    "not_reached", "inside_zone", "triggered", "passed_without_safe_entry",
    "invalidated", "unavailable",
}
DATA_STATES = {"complete", "partial", "stale", "unavailable", "invalid", "market_closed"}
TACTICAL_STATES = {
    "maintain_watch", "entry_triggered_hold", "wait_for_volume", "cancel_chase",
    "reduce_risk", "stop_invalidated", "target_near", "no_trade", "data_unavailable",
}


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=TAIPEI)


def resolve_market_session(reference: datetime) -> dict[str, Any]:
    """Resolve the observed phase using New York local time (including DST)."""
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=TAIPEI)
    ny = reference.astimezone(NEW_YORK)
    if ny.weekday() >= 5:
        phase = "market_closed"
    elif ny.time() < time(4):
        phase = "market_closed"
    elif ny.time() < time(9, 30):
        phase = "pre_market"
    elif ny.time() < time(16):
        phase = "regular_session"
    elif ny.time() < time(20):
        phase = "after_hours"
    else:
        phase = "market_closed"
    elapsed = 0
    if phase == "regular_session":
        elapsed = max(0, min(390, (ny.hour * 60 + ny.minute) - (9 * 60 + 30)))
    return {
        "market_timezone": "America/New_York",
        "reference_new_york": ny.replace(microsecond=0).isoformat(),
        "session_date": ny.date().isoformat(),
        "session_phase": phase,
        "regular_session_elapsed_minutes": elapsed,
        "dst_active": bool(ny.dst() and ny.dst().total_seconds()),
    }


def _volume_baseline(history: Any, elapsed_minutes: int) -> tuple[float | None, str]:
    """Conservative documented fallback: median daily volume × elapsed fraction."""
    try:
        values = [float(value) for value in history["Volume"].dropna().tail(21).tolist()]
    except (KeyError, TypeError, AttributeError, ValueError):
        return None, "insufficient_history"
    # The last daily row can be today's partial bar.  Use preceding observations.
    if len(values) >= 6:
        values = values[:-1]
    if len(values) < 5 or elapsed_minutes <= 0:
        return None, "insufficient_history"
    return round(median(values) * min(1.0, elapsed_minutes / 390.0), 2), "daily_median_prorated_by_elapsed_session_minutes"


def _gap_state(previous: float | None, opened: float | None, current: float | None) -> tuple[float | None, float | None, float | None, str]:
    if previous in (None, 0) or opened is None or current is None:
        return None, None, None, "unavailable"
    gap_open = (opened - previous) / previous * 100
    gap_current = (current - previous) / previous * 100
    if abs(gap_open) < 0.15:
        return round(gap_open, 4), round(gap_current, 4), 100.0, "flat_open"
    fill = max(0.0, min(100.0, (opened - current) / (opened - previous) * 100))
    if gap_open > 0:
        state = "gap_up_full_fill" if current <= previous else "gap_up_partial_fill" if current < opened else "gap_up_follow_through"
    else:
        state = "gap_down_full_fill" if current >= previous else "gap_down_partial_fill" if current > opened else "gap_down_follow_through"
    return round(gap_open, 4), round(gap_current, 4), round(fill, 2), state


def _entry_state(current: float | None, low: float | None, high: float | None, day_low: float | None, day_high: float | None, stop: float | None) -> str:
    if current is None or low is None or high is None:
        return "unavailable"
    if stop is not None and current <= stop:
        return "invalidated"
    if low <= current <= high:
        return "inside_zone"
    if current < low:
        return "not_reached"
    if day_low is not None and day_low <= high and (day_high is None or day_high >= low):
        return "triggered"
    return "passed_without_safe_entry"


def _distance(current: float | None, level: float | None) -> float | None:
    if current in (None, 0) or level is None:
        return None
    return round((level - current) / current * 100, 4)


def _source_hash(card: dict[str, Any]) -> str:
    payload = {key: value for key, value in card.items() if key != "source_payload_hash"}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_intraday_card(
    *, entry: dict[str, Any], quote: dict[str, Any], history: Any,
    tactical: dict[str, Any], session: dict[str, Any], fetch_error: str | None = None,
    pre_open_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = _number(quote.get("last_price"))
    previous = _number(quote.get("previous_close"))
    opened = _number(quote.get("regular_market_open"))
    volume = _number(quote.get("volume"))
    as_of = _iso_datetime(quote.get("market_data_as_of"))
    reference = _iso_datetime(session.get("reference_taipei")) or datetime.now(TAIPEI)
    missing = [name for name, value in (("current_price", current), ("regular_session_open", opened), ("previous_close", previous), ("session_volume", volume), ("market_data_as_of", as_of)) if value is None]
    phase = str(session.get("session_phase") or "data_unavailable")
    observed_market_state = str(quote.get("market_state") or "unknown").upper()
    if observed_market_state in {"CLOSED", "MARKET_CLOSED"}:
        phase = "market_closed"
    observed_age_minutes = None if as_of is None else (reference.astimezone(as_of.tzinfo) - as_of).total_seconds() / 60
    stale_minutes = None if observed_age_minutes is None else max(0.0, observed_age_minutes)
    if phase == "market_closed":
        data_status = "market_closed"
    elif missing:
        data_status = "unavailable" if current is None or as_of is None else "partial"
    elif observed_age_minutes is not None and observed_age_minutes < -5:
        data_status = "invalid"
        missing.append("market_data_time_after_batch_reference")
    elif quote.get("last_price_source") == "yfinance_daily_history.Close":
        data_status = "stale"
        if "current_price_from_daily_bar" not in missing:
            missing.append("current_price_from_daily_bar")
    elif stale_minutes is not None and stale_minutes > 20:
        data_status = "stale"
    else:
        data_status = "complete"

    pre_setup = (pre_open_snapshot or {}).get("pre_open_setup") if isinstance(pre_open_snapshot, dict) else None
    # New 20:00 snapshots contain the full setup.  Legacy snapshots may retain
    # only action; fill missing keys from the same deterministic strategy as an
    # explicit compatibility path, never from another symbol/window/date.
    setup = {**tactical, **pre_setup} if isinstance(pre_setup, dict) else tactical
    entry_zone = setup.get("entry_zone") if isinstance(setup.get("entry_zone"), dict) else {}
    target = setup.get("target_zone_1") if isinstance(setup.get("target_zone_1"), dict) else {}
    entry_low, entry_high = _number(entry_zone.get("low")), _number(entry_zone.get("high"))
    stop = _number(setup.get("stop_reference") or setup.get("stop"))
    target_level = _number(target.get("low") if target else setup.get("target_1"))
    gap_open, gap_current, gap_fill, gap_state = _gap_state(previous, opened, current)
    baseline, baseline_method = _volume_baseline(history, int(session.get("regular_session_elapsed_minutes") or 0))
    ratio = None if volume is None or baseline in (None, 0) else round(volume / baseline, 4)
    volume_state = "source_unavailable" if volume is None else "insufficient_history" if ratio is None else "strong" if ratio >= 1.3 else "confirmed" if ratio >= 1.0 else "neutral" if ratio >= 0.7 else "weak"
    trigger = _entry_state(current, entry_low, entry_high, _number(quote.get("day_low")), _number(quote.get("day_high")), stop)
    stop_distance = _distance(current, stop)
    target_distance = _distance(current, target_level)
    chase = str(tactical.get("chase_risk") or "unknown")

    if data_status in {"unavailable", "stale", "invalid", "market_closed"}:
        adjustment, reason = "data_unavailable", "盤中行情不完整、過舊或市場未開盤，本次無法安全判定盤中策略。"
    elif trigger == "invalidated":
        adjustment, reason = "stop_invalidated", f"目前價 {current:.2f} 已低於停損 {stop:.2f}。"
    elif target_distance is not None and 0 <= target_distance <= 1.0:
        adjustment, reason = "target_near", f"目前價 {current:.2f} 距目標僅 {target_distance:.2f}%。"
    elif trigger == "passed_without_safe_entry" or (chase == "high" and entry_high is not None and current is not None and current > entry_high):
        adjustment, reason = "cancel_chase", f"目前價 {current:.2f} 已高於安全進場上緣 {entry_high:.2f}，避免追價。"
    elif trigger in {"triggered", "inside_zone"} and volume_state in {"strong", "confirmed"}:
        adjustment, reason = "entry_triggered_hold", f"價格已進入／通過進場區，量能為基準 {ratio:.2f} 倍。"
    elif trigger in {"triggered", "inside_zone"}:
        adjustment, reason = "wait_for_volume", f"價格已到進場區，但量能狀態為 {volume_state}。"
    elif stop_distance is not None and -1.0 <= stop_distance <= 0:
        adjustment, reason = "reduce_risk", f"目前價距停損僅 {abs(stop_distance):.2f}%。"
    else:
        adjustment, reason = "maintain_watch", f"目前價 {current:.2f} 尚未形成需取消或減碼的條件。"

    setup_id = f"{session.get('session_date')}:{str(entry.get('symbol') or '').upper()}:daily_tactical"
    card = {
        "schema_version": SCHEMA_VERSION, "symbol": str(entry.get("symbol") or "").upper(),
        "name": entry.get("name"), "market": "US", "window": WINDOW,
        "trading_date": session.get("session_date"), "session_date": session.get("session_date"),
        "market_timezone": "America/New_York", "session_phase": phase,
        "observed_market_state": observed_market_state, "setup_id": setup_id,
        "previous_close": previous, "regular_session_open": opened, "current_price": current,
        "market_data_as_of": as_of.isoformat() if as_of else None,
        "market_data_freshness_minutes": round(stale_minutes, 2) if stale_minutes is not None else None,
        "gap_open_pct": gap_open, "gap_current_pct": gap_current, "gap_fill_pct": gap_fill,
        "gap_state": gap_state, "gap_follow_through_state": gap_state,
        "session_volume": volume, "volume_baseline": baseline, "volume_baseline_method": baseline_method,
        "volume_ratio": ratio, "volume_confirmation_state": volume_state,
        "entry_low": entry_low, "entry_high": entry_high, "entry_trigger_state": trigger,
        "entry_trigger_price": current if trigger in {"inside_zone", "triggered"} else None,
        "entry_trigger_time": as_of.isoformat() if as_of and trigger in {"inside_zone", "triggered"} else None,
        "stop_level": stop, "target_level": target_level,
        "distance_to_stop_pct": stop_distance, "distance_to_target_pct": target_distance,
        "pre_open_action": setup.get("action") or tactical.get("action"),
        "pre_open_setup_source": (pre_open_snapshot or {}).get("snapshot_path") or "current_strategy_compatibility",
        "intraday_action": adjustment, "tactical_adjustment": adjustment, "adjustment_reason": reason,
        "chase_risk": chase, "gap_risk": tactical.get("gap_risk"), "event_risk": tactical.get("event_risk"),
        "liquidity_status": "available" if volume is not None else "unavailable",
        "data_status": data_status, "missing_fields": missing, "fetch_error": fetch_error,
        "source": quote.get("market_data_source") or "Yahoo Finance / yfinance",
        "source_price_field": quote.get("last_price_source"),
    }
    card["source_payload_hash"] = _source_hash(card)
    return card


def summarize_intraday(cards: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [card for card in cards if card.get("data_status") in {"complete", "partial"}]
    return {
        "tracking_count": len(cards), "structured_card_count": len(cards),
        "triggered_count": sum(c.get("entry_trigger_state") == "triggered" for c in usable),
        "inside_zone_count": sum(c.get("entry_trigger_state") == "inside_zone" for c in usable),
        "not_reached_count": sum(c.get("entry_trigger_state") == "not_reached" for c in usable),
        "cancel_chase_count": sum(c.get("tactical_adjustment") == "cancel_chase" for c in usable),
        "volume_confirmed_count": sum(c.get("volume_confirmation_state") in {"strong", "confirmed"} for c in usable),
        "gap_follow_through_count": sum(str(c.get("gap_state")).endswith("follow_through") for c in usable),
        "data_unavailable_count": sum(c.get("data_status") in {"unavailable", "stale", "invalid"} for c in cards),
        "near_stop_count": sum(c.get("distance_to_stop_pct") is not None and -1 <= c["distance_to_stop_pct"] <= 0 for c in usable),
        "near_target_count": sum(c.get("distance_to_target_pct") is not None and 0 <= c["distance_to_target_pct"] <= 1 for c in usable),
    }


def validate_intraday_payload(payload: dict[str, Any]) -> list[str]:
    if payload.get("market") != "US" or payload.get("window") != WINDOW:
        return []
    cards = payload.get("structured_intraday_cards")
    tracking = int(payload.get("runtime_watchlist_validation", {}).get("enabled_stock_count") or 0)
    errors: list[str] = []
    if not isinstance(cards, list):
        return ["structured_intraday_cards_missing"]
    if tracking > 0 and len(cards) != tracking:
        errors.append("tracking_structured_card_count_mismatch")
    symbols = [str(card.get("symbol") or "") for card in cards if isinstance(card, dict)]
    if len(symbols) != len(set(symbols)):
        errors.append("duplicate_symbol")
    phase = str(payload.get("session_context", {}).get("session_phase") or "")
    for card in cards:
        if not isinstance(card, dict):
            errors.append("invalid_card")
            continue
        if card.get("entry_trigger_state") not in ENTRY_STATES:
            errors.append("invalid_entry_trigger_state")
        if card.get("data_status") not in DATA_STATES:
            errors.append("invalid_data_status")
        if card.get("tactical_adjustment") not in TACTICAL_STATES:
            errors.append("invalid_tactical_adjustment")
        if phase == "regular_session" and card.get("data_status") == "complete":
            for key in ("current_price", "market_data_as_of", "entry_trigger_state"):
                if card.get(key) is None:
                    errors.append(f"complete_card_missing_{key}")
    if phase == "regular_session" and cards and all(card.get("data_status") in {"unavailable", "stale", "invalid"} for card in cards):
        errors.append("all_intraday_market_data_unavailable")
    return sorted(set(errors))
