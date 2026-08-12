"""Unified semantic admission gate for every Taiwan daily-history source."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

SCHEMA_VERSION = "tw_history_admission_v1"
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


def validate_history_candidate(
    frame: pd.DataFrame | None, *, source: str, target_date: Any,
    minimum_bars: int = 20, freshness_days: int = 7,
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
    latest = normalized["date"].max().date()
    future = bool(target and (normalized["date"].dt.date > target).any())
    base.update(row_count=len(normalized), latest_date=latest.isoformat(), normalized=normalized.assign(date=normalized["date"].dt.date))
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
    stale = bool(target and latest < target - timedelta(days=freshness_days))
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
