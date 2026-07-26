"""Immutable source-plan binding and deterministic US 06:30 trade review.

The evaluator is pure apart from the explicit archive read performed by
``resolve_source_trade_plan``.  It never selects by mtime and never writes an
archive, runtime, notification, or public artifact.
"""
from __future__ import annotations

from typing import Any, Iterable

from app.us_stock.three_window_lifecycle import resolve_source_trade_plan

TRADE_REVIEW_OUTCOMES = ("win", "loss", "not_triggered", "no_trade", "pending_evidence")


def _number(value: Any) -> float | None:
    try:
        return round(float(value), 6) if value is not None else None
    except (TypeError, ValueError):
        return None


def _range(value: Any) -> tuple[float | None, float | None]:
    if not isinstance(value, dict):
        return None, None
    low, high = _number(value.get("low")), _number(value.get("high"))
    return (min(low, high), max(low, high)) if low is not None and high is not None else (None, None)


def _rows(bars: Any) -> list[dict[str, Any]]:
    if bars is None:
        return []
    if isinstance(bars, list):
        return [dict(row) for row in bars if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    try:
        for index, row in bars.sort_index().iterrows():
            rows.append({"time": index.isoformat() if hasattr(index, "isoformat") else str(index), "open": row.get("Open"), "high": row.get("High"), "low": row.get("Low"), "close": row.get("Close")})
    except Exception:
        return []
    return rows


def _finish(outcome: str, *, source: dict[str, Any], entry_triggered: bool | None, entry_price: float | None,
            entry_time: Any, target_outcome: str, stop_outcome: str, high_after: float | None,
            low_after: float | None, evidence_resolution: str, reason: str) -> dict[str, Any]:
    direction = str(source.get("direction") or "").lower()
    short = "bearish" in direction or direction == "short"
    mfe_pct = mae_pct = None
    if entry_triggered and entry_price not in (None, 0) and high_after is not None and low_after is not None:
        if short:
            mfe_pct = round((entry_price - low_after) / entry_price * 100, 4)
            mae_pct = round((entry_price - high_after) / entry_price * 100, 4)
        else:
            mfe_pct = round((high_after - entry_price) / entry_price * 100, 4)
            mae_pct = round((low_after - entry_price) / entry_price * 100, 4)
    canonical = {"win": "hit", "loss": "fail", "not_triggered": "not_triggered", "no_trade": "no_trade", "pending_evidence": "pending"}[outcome]
    na = outcome in {"not_triggered", "no_trade"}
    return {
        "trade_review_outcome": outcome, "trade_outcome": canonical, "canonical_outcome": canonical,
        "entry_triggered": entry_triggered, "entry_outcome": "triggered" if entry_triggered else "not_triggered" if entry_triggered is False else "not_applicable",
        "entry_trigger_price": entry_price, "entry_trigger_time": entry_time,
        "target_outcome": "not_applicable" if na else target_outcome,
        "stop_outcome": "not_applicable" if na else stop_outcome,
        "mfe_pct": "not_applicable" if na else mfe_pct, "mae_pct": "not_applicable" if na else mae_pct,
        "mfe": "不適用" if na else (f"{mfe_pct:+.2f}%" if mfe_pct is not None else "待補證據"),
        "mae": "不適用" if na else (f"{mae_pct:+.2f}%" if mae_pct is not None else "待補證據"),
        "actual_status": "complete", "formal_no_trade": outcome == "no_trade",
        "canonical_no_trade_evidence": outcome == "no_trade", "evidence_resolution": evidence_resolution,
        "outcome_reason": reason,
    }


def evaluate_trade_outcome(source: dict[str, Any] | None, quote: dict[str, Any], bars: Any = None) -> dict[str, Any]:
    if not source:
        return {"trade_review_outcome": "pending_evidence", "trade_outcome": "pending", "canonical_outcome": "pending", "entry_triggered": None, "target_outcome": "pending", "stop_outcome": "pending", "mfe": "待補證據", "mae": "待補證據", "mfe_pct": None, "mae_pct": None, "actual_status": "unavailable", "pending_reason": "source_trade_plan_missing", "evidence_resolution": "none"}
    eligibility = source.get("eligibility") or {}
    if eligibility.get("no_trade") or (eligibility.get("watch_only") and not eligibility.get("actionable")) or source.get("trade_plan_status") in {"no_trade", "watch_only"}:
        return _finish("no_trade", source=source, entry_triggered=None, entry_price=None, entry_time=None, target_outcome="not_applicable", stop_outcome="not_applicable", high_after=None, low_after=None, evidence_resolution="source_plan", reason="來源 20:00 setup 明確不建立交易")
    entry_low, entry_high = _range(source.get("entry")); target_low, target_high = _range(source.get("target")); stop = _number(source.get("stop"))
    actual_high, actual_low = _number(quote.get("day_high")), _number(quote.get("day_low"))
    direction = str(source.get("direction") or "").lower(); short = "bearish" in direction or direction == "short"
    if None in (entry_low, entry_high, target_low, target_high, stop, actual_high, actual_low):
        return {**_finish("pending_evidence", source=source, entry_triggered=None, entry_price=None, entry_time=None, target_outcome="pending", stop_outcome="pending", high_after=None, low_after=None, evidence_resolution="incomplete", reason="交易計畫或實際行情欄位不足"), "pending_reason": "trade_plan_or_actual_incomplete"}
    rows = [row for row in _rows(bars) if str(row.get("time") or "")[:10] == str(source.get("source_effective_date") or "")]
    entry_price = round((entry_low + entry_high) / 2, 6)
    if rows:
        entered = False; entry_time = None; high_after = low_after = None
        target_level = target_high if short else target_low
        for row in rows:
            high, low = _number(row.get("high")), _number(row.get("low"))
            if high is None or low is None: continue
            if not entered and low <= entry_high and high >= entry_low:
                entered = True; entry_time = row.get("time")
            if not entered: continue
            high_after = high if high_after is None else max(high_after, high)
            low_after = low if low_after is None else min(low_after, low)
            target_hit = low <= target_level if short else high >= target_level
            stop_hit = high >= stop if short else low <= stop
            if target_hit and stop_hit:
                return _finish("pending_evidence", source=source, entry_triggered=True, entry_price=entry_price, entry_time=entry_time, target_outcome="pending", stop_outcome="pending", high_after=high_after, low_after=low_after, evidence_resolution="intraday_bar_ambiguous", reason="同一根行情同時跨越目標與停損，無法判定先後")
            if target_hit:
                return _finish("win", source=source, entry_triggered=True, entry_price=entry_price, entry_time=entry_time, target_outcome="hit", stop_outcome="not_hit", high_after=high_after, low_after=low_after, evidence_resolution="intraday_bars", reason="進場後先達正式目標")
            if stop_hit:
                return _finish("loss", source=source, entry_triggered=True, entry_price=entry_price, entry_time=entry_time, target_outcome="not_hit", stop_outcome="hit", high_after=high_after, low_after=low_after, evidence_resolution="intraday_bars", reason="進場後先觸及正式停損")
        if not entered:
            return _finish("not_triggered", source=source, entry_triggered=False, entry_price=None, entry_time=None, target_outcome="not_applicable", stop_outcome="not_applicable", high_after=None, low_after=None, evidence_resolution="intraday_bars", reason="完整盤中行情未進入正式進場區")
        return _finish("pending_evidence", source=source, entry_triggered=True, entry_price=entry_price, entry_time=entry_time, target_outcome="not_hit", stop_outcome="not_hit", high_after=high_after, low_after=low_after, evidence_resolution="intraday_bars", reason="已進場但尚未達目標或停損，依政策列為待補證據")
    touched = actual_low <= entry_high and actual_high >= entry_low
    if not touched:
        return _finish("not_triggered", source=source, entry_triggered=False, entry_price=None, entry_time=None, target_outcome="not_applicable", stop_outcome="not_applicable", high_after=None, low_after=None, evidence_resolution="daily_ohlc", reason="日內高低未進入正式進場區")
    target_level = target_high if short else target_low
    target_hit = actual_low <= target_level if short else actual_high >= target_level
    stop_hit = actual_high >= stop if short else actual_low <= stop
    if target_hit and stop_hit:
        return _finish("pending_evidence", source=source, entry_triggered=True, entry_price=entry_price, entry_time=None, target_outcome="pending", stop_outcome="pending", high_after=actual_high, low_after=actual_low, evidence_resolution="daily_ohlc_ambiguous", reason="日線同時跨越目標與停損，缺少時序證據")
    outcome = "win" if target_hit else "loss" if stop_hit else "pending_evidence"
    return _finish(outcome, source=source, entry_triggered=True, entry_price=entry_price, entry_time=None, target_outcome="hit" if target_hit else "not_hit", stop_outcome="hit" if stop_hit else "not_hit", high_after=actual_high, low_after=actual_low, evidence_resolution="daily_ohlc", reason="日線只有單一邊界觸發" if outcome != "pending_evidence" else "已進場但日線未達目標或停損")


def next_session_action(outcome: str) -> str:
    return {
        "win": "保留有效 setup，檢查是否過度延伸。",
        "loss": "降低優先級，檢討失效原因。",
        "not_triggered": "保留觀察或取消 setup。",
        "no_trade": "不建立後續交易追蹤。",
        "pending_evidence": "補足行情時序證據後再判定。",
    }.get(outcome, "補足行情時序證據後再判定。")
