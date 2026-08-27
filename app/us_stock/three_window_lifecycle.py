"""Canonical US 20:00 -> 23:00 -> 06:30 source-plan continuity.

Only an admitted 20:00 snapshot may define a formal trade plan.  Later
windows may attach observed evidence, but must not regenerate plan geometry.
All helpers are deterministic and read-only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PLAN_STATUSES = {"active", "watch", "no_trade"}
DIRECTIONS = {"long", "short", "neutral", "not_applicable"}


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return round(result, 6) if result == result else None


def price_range(value: Any) -> tuple[float | None, float | None]:
    if not isinstance(value, dict):
        return None, None
    low, high = number(value.get("low")), number(value.get("high"))
    return (min(low, high), max(low, high)) if low is not None and high is not None else (None, None)


def canonical_direction(value: Any, *, plan_status: str = "active") -> str:
    if plan_status == "no_trade":
        return "not_applicable"
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in {"long", "bullish", "mildly_bullish", "uptrend", "strong_uptrend"}:
        return "long"
    if raw in {"short", "bearish", "mildly_bearish", "downtrend", "strong_downtrend"}:
        return "short"
    if raw in {"neutral", "sideways", "watch", "unavailable", "unknown", ""}:
        return "neutral" if plan_status == "watch" else "not_applicable"
    return "not_applicable"


def canonical_plan_status(eligibility: dict[str, Any], plan: dict[str, Any]) -> str:
    if eligibility.get("no_trade") is True:
        return "no_trade"
    if eligibility.get("actionable") is True and plan.get("status") == "active":
        return "active"
    return "watch"


def validate_trade_geometry(source: dict[str, Any]) -> list[str]:
    status = str(source.get("plan_status") or source.get("trade_plan_status") or "")
    if status != "active":
        return []
    direction = str(source.get("direction") or "")
    entry_low, entry_high = price_range(source.get("entry"))
    target_low, target_high = price_range(source.get("target"))
    stop = number(source.get("stop"))
    if None in (entry_low, entry_high, target_low, target_high, stop):
        return ["active_plan_geometry_incomplete"]
    if direction == "long":
        return [] if stop < entry_low and target_low > entry_high else ["invalid_long_geometry"]
    if direction == "short":
        return [] if stop > entry_high and target_high < entry_low else ["invalid_short_geometry"]
    return ["active_plan_direction_invalid"]


def directional_proximity(source: dict[str, Any], current_price: Any) -> dict[str, Any]:
    current = number(current_price)
    direction = str(source.get("direction") or "")
    stop = number(source.get("stop"))
    target_low, target_high = price_range(source.get("target"))
    if current in (None, 0) or direction not in {"long", "short"} or stop is None or None in (target_low, target_high):
        return {"stop_distance_pct": None, "target_distance_pct": None, "stop_hit": False, "target_hit": False}
    if direction == "short":
        stop_distance = (stop - current) / current * 100
        target_distance = (current - target_high) / current * 100
        stop_hit, target_hit = current >= stop, current <= target_high
    else:
        stop_distance = (current - stop) / current * 100
        target_distance = (target_low - current) / current * 100
        stop_hit, target_hit = current <= stop, current >= target_low
    return {
        "stop_distance_pct": round(stop_distance, 4),
        "target_distance_pct": round(target_distance, 4),
        "stop_hit": stop_hit,
        "target_hit": target_hit,
    }


def _source_card(wrapper: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    payload = wrapper.get("payload") if isinstance(wrapper.get("payload"), dict) else {}
    cards = ((payload.get("dashboard_ready_contract") or {}).get("cards") or [])
    return next((card for card in cards if isinstance(card, dict) and str(card.get("symbol") or "").upper() == symbol.upper()), None)


def resolve_source_trade_plan(archive_root: Path, session_date: str, symbol: str) -> dict[str, Any] | None:
    """Resolve the latest admitted 20:00 revision for the exact effective date."""
    folder = archive_root / "us" / "us_pre_market_2000" / session_date
    candidates: list[dict[str, Any]] = []
    for path in sorted(folder.glob("revision-*.json")):
        try:
            wrapper = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if wrapper.get("admitted") is not True or str(wrapper.get("effective_trading_date")) != session_date:
            continue
        card = _source_card(wrapper, symbol)
        if card:
            candidates.append({"wrapper": wrapper, "card": card, "path": path})
    if not candidates:
        return None
    selected = max(candidates, key=lambda item: (
        int(item["wrapper"].get("revision") or 0),
        str(item["wrapper"].get("admitted_at") or item["wrapper"].get("revision_created_at") or ""),
    ))
    wrapper, card = selected["wrapper"], selected["card"]
    eligibility = card.get("eligibility") if isinstance(card.get("eligibility"), dict) else {}
    plan = card.get("trade_plan") if isinstance(card.get("trade_plan"), dict) else {}
    tactical = card.get("daily_tactical_summary") if isinstance(card.get("daily_tactical_summary"), dict) else {}
    plan_status = canonical_plan_status(eligibility, plan)
    raw_entry = plan.get("entry") if plan_status == "active" else None
    raw_target = plan.get("target") if plan_status == "active" else None
    stop = plan.get("stop") if plan_status == "active" else None
    direction = canonical_direction(card.get("direction") or tactical.get("direction"), plan_status=plan_status)
    source = {
        "schema_version": "us_source_trade_plan_v1",
        "source_market": "us", "source_window": "us_pre_market_2000",
        "source_effective_date": session_date, "source_snapshot_id": wrapper.get("snapshot_id"),
        "source_revision": int(wrapper.get("revision") or 0),
        "source_hash": wrapper.get("source_payload_hash") or (wrapper.get("payload") or {}).get("source_payload_hash") or wrapper.get("snapshot_id"),
        "source_admitted_at": wrapper.get("admitted_at"), "source_path": str(selected["path"]),
        "symbol": symbol.upper(), "plan_status": plan_status, "trade_plan_status": plan_status,
        "direction": direction, "strategy_direction_raw": tactical.get("direction"),
        "setup_type": tactical.get("setup_type"), "eligibility": eligibility,
        "entry": {"low": price_range(raw_entry)[0], "high": price_range(raw_entry)[1]} if plan_status == "active" else None,
        "observation_zone": (plan.get("observation_zone") or tactical.get("entry_zone")) if plan_status != "active" else None,
        "stop": number(stop) if plan_status == "active" else None,
        "target": {"low": price_range(raw_target)[0], "high": price_range(raw_target)[1]} if plan_status == "active" else None,
        "event_risk": card.get("event_risk"), "sec_evidence": card.get("sec_evidence"),
        "news_evidence": card.get("news_evidence"), "relative_strength": card.get("relative_strength"),
        "forecast": json.loads(json.dumps(card.get("us_premarket_product_projection_v1") or {})),
        "confidence": card.get("confidence"),
        "market_context": card.get("market_context"), "action_rationale": card.get("action_rationale"),
        "invalidation_condition": f"跌破 {number(stop):.2f}" if plan_status == "active" and direction == "long" and number(stop) is not None else f"突破 {number(stop):.2f}" if plan_status == "active" and direction == "short" and number(stop) is not None else None,
    }
    source["geometry_errors"] = validate_trade_geometry(source)
    return source


def resolve_intraday_evidence(archive_root: Path, session_date: str, symbol: str) -> dict[str, Any] | None:
    """Resolve admitted 23:00 evidence without treating it as a plan source."""
    folder = archive_root / "us" / "us_intraday_2300" / session_date
    candidates: list[tuple[int, str, dict[str, Any], dict[str, Any]]] = []
    for path in sorted(folder.glob("revision-*.json")):
        try:
            wrapper = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if wrapper.get("admitted") is not True or str(wrapper.get("effective_trading_date")) != session_date:
            continue
        card = _source_card(wrapper, symbol)
        if card:
            candidates.append((int(wrapper.get("revision") or 0), str(wrapper.get("admitted_at") or ""), wrapper, card))
    if not candidates:
        return None
    _, _, wrapper, card = max(candidates, key=lambda item: (item[0], item[1]))
    source_plan = card.get("source_plan") if isinstance(card.get("source_plan"), dict) else card.get("source_trade_plan") or {}
    return {
        "source_window": "us_intraday_2300", "source_effective_date": session_date,
        "source_snapshot_id": wrapper.get("snapshot_id"), "source_revision": int(wrapper.get("revision") or 0),
        "source_hash": wrapper.get("source_payload_hash") or wrapper.get("snapshot_id"),
        "source_plan_snapshot_id": source_plan.get("source_snapshot_id"),
        "trigger_status": card.get("entry_trigger_state"), "volume_state": card.get("volume_confirmation_state"),
        "gap_state": card.get("gap_state"), "gap_current_pct": card.get("gap_current_pct"),
        "volume_ratio": card.get("volume_ratio"), "volume_confirmation_state": card.get("volume_confirmation_state"),
        "data_status": card.get("data_status"), "current_price": card.get("current_price"),
        "market_data_as_of": card.get("market_data_as_of"), "source": card.get("source"),
    }
