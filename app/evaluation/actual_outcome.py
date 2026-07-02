"""Repo-local actual outcome loader for prediction evaluation V1."""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import Any
from app.evaluation.schemas import ACTUAL_OUTCOME_SCHEMA_VERSION, ActualOutcome
ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_DIR = ROOT / "data" / "historical"
def _parse_date(value: str) -> date | None:
    try: return date.fromisoformat(str(value)[:10])
    except ValueError: return None
def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""): return None
        return float(value)
    except (TypeError, ValueError): return None
def _stock_file(stock_id: str, historical_dir: Path = HISTORICAL_DIR) -> Path:
    normalized = str(stock_id).zfill(4) if str(stock_id).isdigit() and len(str(stock_id)) < 4 else str(stock_id)
    return historical_dir / f"{normalized}_daily.csv"
def load_historical_rows(stock_id: str, historical_dir: Path = HISTORICAL_DIR) -> list[dict[str, Any]]:
    path = _stock_file(stock_id, historical_dir)
    if not path.exists(): return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            parsed = _parse_date(str(row.get("date", row.get("\ufeffdate", ""))))
            if parsed is None: continue
            rows.append({"date": parsed.isoformat(), "open": _as_float(row.get("open")), "high": _as_float(row.get("high")), "low": _as_float(row.get("low")), "close": _as_float(row.get("close")), "volume": _as_float(row.get("volume"))})
    return sorted(rows, key=lambda item: item["date"])
def _return_from_index(rows: list[dict[str, Any]], index: int, lookback: int) -> float | None:
    prev = index - lookback
    if prev < 0: return None
    current = _as_float(rows[index].get("close")); previous = _as_float(rows[prev].get("close"))
    if current is None or previous in (None, 0): return None
    return round((current - previous) / previous, 6)
def pending_actual_outcome(stock_id: str, target_date: str, status: str = "pending") -> ActualOutcome:
    return ActualOutcome(ACTUAL_OUTCOME_SCHEMA_VERSION, str(stock_id), str(target_date), None, None, None, None, None, None, None, None, status)
def load_actual_outcome(stock_id: str, target_date: str, historical_dir: Path = HISTORICAL_DIR) -> ActualOutcome:
    parsed_target = _parse_date(target_date)
    if parsed_target is None: return pending_actual_outcome(stock_id, target_date, status="missing")
    rows = load_historical_rows(stock_id, historical_dir)
    if not rows: return pending_actual_outcome(stock_id, parsed_target.isoformat(), status="missing")
    dates = [row["date"] for row in rows]
    if parsed_target.isoformat() not in dates:
        latest_date = _parse_date(dates[-1]) if dates else None
        return pending_actual_outcome(stock_id, parsed_target.isoformat(), status="pending" if latest_date is None or parsed_target > latest_date else "missing")
    index = dates.index(parsed_target.isoformat()); row = rows[index]
    if any(row.get(key) is None for key in ["open", "high", "low", "close", "volume"]): return pending_actual_outcome(stock_id, parsed_target.isoformat(), status="insufficient_data")
    return ActualOutcome(ACTUAL_OUTCOME_SCHEMA_VERSION, str(stock_id), parsed_target.isoformat(), row["open"], row["high"], row["low"], row["close"], row["volume"], _return_from_index(rows, index, 1), _return_from_index(rows, index, 5), _return_from_index(rows, index, 20), "completed")
