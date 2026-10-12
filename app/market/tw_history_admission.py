"""Unified semantic admission gate for every Taiwan daily-history source."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

SCHEMA_VERSION = "tw_history_admission_v2"
VALID_COLUMNS = ("date", "open", "high", "low", "close", "volume")
STATUSES = {
    "VALID", "PARTIAL", "STALE", "INSUFFICIENT_LOOKBACK", "INVALID_GEOMETRY",
    "DUPLICATE_DATE", "FUTURE_DATA", "PARSE_FAILED", "EMPTY", "SOURCE_FAILED",
}


def _day(value: Any) -> date | None:
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError):
        return None


def expected_completed_session(
    target_date: Any, *, window: str = "pre_open_0700",
    holiday_dates: set[str] | set[date] | None = None,
    calendar: dict[str, Any] | None = None,
) -> date | None:
    """Return the latest eligible completed TW daily session.

    A supplied immutable TWSE calendar is authoritative.  The legacy
    weekend/explicit-holiday path remains for callers that deliberately use
    a bounded fixture; production admission supplies the pinned calendar.
    """
    target = _day(target_date)
    if target is None:
        return None
    if calendar is not None:
        from app.evaluation.session_calendar import CalendarError, latest_completed_session

        clock = "23:59:59+08:00" if window in {"post_close_1500", "completed_session"} else "07:00:00+08:00"
        try:
            row = latest_completed_session(calendar, "TW", f"{target.isoformat()}T{clock}")
        except CalendarError:
            return None
        return _day(row.get("session_date"))
    holidays = {_day(value) for value in (holiday_dates or set())}
    include_target = window in {"post_close_1500", "completed_session"}
    candidate = target if include_target else target.fromordinal(target.toordinal() - 1)
    while candidate.weekday() >= 5 or candidate in holidays:
        candidate = candidate.fromordinal(candidate.toordinal() - 1)
    return candidate


def validate_history_candidate(
    frame: pd.DataFrame | None, *, source: str, target_date: Any,
    minimum_bars: int = 20, window: str = "pre_open_0700",
    holiday_dates: set[str] | set[date] | None = None,
    calendar: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return normalized data plus stage-by-stage admission evidence."""
    base = {
        "schema_version": SCHEMA_VERSION, "source": source,
        "fetch_success": frame is not None,
        "normalization_success": False, "integrity_success": False,
        "freshness_success": False, "admission_success": False,
        "feature_success": False, "research_consumption_success": False,
        "status": "SOURCE_FAILED" if frame is None else "EMPTY",
        "reason_codes": [], "row_count": 0, "latest_date": None,
        "minimum_bars": minimum_bars, "target_date": str(target_date),
        "window": window, "freshness_method": "expected_completed_tw_trading_session_v1",
        "normalized": pd.DataFrame(columns=VALID_COLUMNS),
    }
    if frame is None:
        base["reason_codes"] = ["SOURCE_FAILED"]
        return base
    if frame.empty:
        base["reason_codes"] = ["EMPTY"]
        return base
    columns = {str(name).lower().replace(" ", "_"): name for name in frame.columns}
    if not set(VALID_COLUMNS).issubset(columns):
        base.update(status="PARSE_FAILED", reason_codes=["PARSER_ERROR"])
        return base
    normalized = pd.DataFrame({
        "date": pd.to_datetime(frame[columns["date"]], errors="coerce"),
        **{key: pd.to_numeric(frame[columns[key]], errors="coerce") for key in VALID_COLUMNS[1:]},
    })
    if normalized.isna().any(axis=None):
        base.update(status="PARSE_FAILED", reason_codes=["PARSER_ERROR"], normalized=normalized)
        return base
    base["normalization_success"] = True
    duplicate = bool(normalized["date"].duplicated().any())
    normalized = normalized.sort_values("date").reset_index(drop=True)
    geometry = (
        (normalized[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (normalized["volume"] >= 0)
        & (normalized["high"] >= normalized[["open", "close", "low"]].max(axis=1))
        & (normalized["low"] <= normalized[["open", "close", "high"]].min(axis=1))
    )
    target = _day(target_date)
    if calendar is None and holiday_dates is None:
        # Production history admission must use the repository-pinned TWSE
        # snapshot.  A calendar load failure is fail-closed below.
        try:
            from app.evaluation.session_calendar import load_calendar
            calendar = load_calendar("TW")
        except Exception:
            base.update(status="SOURCE_FAILED", reason_codes=["CALENDAR_UNAVAILABLE"])
            return base
    expected = expected_completed_session(
        target_date, window=window, holiday_dates=holiday_dates, calendar=calendar,
    )
    if expected is None:
        base.update(status="SOURCE_FAILED", reason_codes=["CALENDAR_SESSION_UNRESOLVED"])
        return base
    latest = normalized["date"].max().date()
    future = bool(expected and (normalized["date"].dt.date > expected).any())
    base.update(
        row_count=len(normalized), latest_date=latest.isoformat(),
        expected_latest_session=expected.isoformat() if expected else None,
        normalized=normalized.assign(date=normalized["date"].dt.date),
    )
    if duplicate:
        base.update(status="DUPLICATE_DATE", reason_codes=["DUPLICATE_DATE"])
        return base
    if not bool(geometry.all()):
        base.update(status="INVALID_GEOMETRY", reason_codes=["INVALID_GEOMETRY"])
        return base
    if future:
        base.update(status="FUTURE_DATA", reason_codes=["FUTURE_DATA"])
        return base
    base["integrity_success"] = True
    stale = bool(expected and latest < expected)
    if stale:
        base.update(status="STALE", reason_codes=["STALE"])
        if len(normalized) < minimum_bars:
            base["reason_codes"].append("INSUFFICIENT_LOOKBACK")
        return base
    base["freshness_success"] = True
    if len(normalized) < minimum_bars:
        base.update(status="INSUFFICIENT_LOOKBACK", reason_codes=["INSUFFICIENT_LOOKBACK"])
        return base
    base.update(status="VALID", reason_codes=[], admission_success=True)
    return base


def public_admission(result: dict[str, Any]) -> dict[str, Any]:
    """Strip the in-memory dataframe for persisted status/Operations output."""
    return {key: value for key, value in result.items() if key != "normalized"}
