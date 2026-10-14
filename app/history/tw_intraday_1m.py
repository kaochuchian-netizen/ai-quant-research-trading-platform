"""AI-DEV-270A deterministic TW 1-minute OHLCV artifact foundation.

This module has no scheduler, credentials, network client, delivery, or
evaluation-pipeline integration.  A caller may pass an already-authenticated
Shioaji API only to the bounded acquisition adapter; persistence and replay
remain separate and work without the provider.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from app.evaluation.prediction_regression_contract import aware
from app.evaluation.session_calendar import session, validate_calendar


SCHEMA_VERSION = "tw_intraday_1m_artifact_v1"
MARKET = "TW"
TIMEZONE = "Asia/Taipei"
INTERVAL = "1m"
BAR_TIMESTAMP_CONVENTION = "BAR_OPEN_TIMESTAMP_HALF_OPEN_1M"
STATUSES = {"COMPLETE", "PARTIAL", "UNAVAILABLE"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"BAR_{field.upper()}")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"BAR_{field.upper()}") from None
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError(f"BAR_{field.upper()}")
    return result


def _minute(value: str) -> datetime:
    parsed = aware(value)
    local = parsed.astimezone(ZoneInfo(TIMEZONE))
    if local.second or local.microsecond:
        raise ValueError("BAR_TIMESTAMP_PRECISION")
    return local


def expected_minutes(calendar: dict[str, Any], trading_session: str) -> list[str]:
    """Return the authoritative half-open session grid; no weekday heuristic."""
    validate_calendar(calendar, MARKET)
    record = session(calendar, MARKET, trading_session)
    opening = aware(record["open_at"]).astimezone(ZoneInfo(TIMEZONE))
    closing = aware(record["close_at"]).astimezone(ZoneInfo(TIMEZONE))
    values: list[str] = []
    cursor = opening
    while cursor < closing:
        values.append(cursor.isoformat())
        cursor += timedelta(minutes=1)
    if not values:
        raise ValueError("EMPTY_SESSION_GRID")
    return values


def _canonical_bar(row: dict[str, Any], *, symbol: str, trading_session: str, allowed: set[str], available_at: datetime) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("BAR_SCHEMA")
    allowed_keys = {"symbol", "timestamp", "bar_timestamp", "source_timestamp", "open", "high", "low", "close", "volume"}
    if not set(row) <= allowed_keys or not {"open", "high", "low", "close", "volume"} <= set(row):
        raise ValueError("BAR_SCHEMA")
    row_symbol = str(row.get("symbol") or symbol).zfill(4)
    if row_symbol != symbol:
        raise ValueError("BAR_SYMBOL")
    timestamp = row.get("bar_timestamp") or row.get("timestamp") or row.get("source_timestamp")
    if not isinstance(timestamp, str):
        raise ValueError("BAR_TIMESTAMP")
    parsed = _minute(timestamp)
    normalized = parsed.isoformat()
    if normalized not in allowed or parsed.date().isoformat() != trading_session:
        raise ValueError("BAR_OUTSIDE_SESSION")
    if parsed + timedelta(minutes=1) > available_at:
        raise ValueError("BAR_INCOMPLETE_OR_FUTURE")
    opening = _number(row["open"], "open", positive=True)
    high = _number(row["high"], "high", positive=True)
    low = _number(row["low"], "low", positive=True)
    close = _number(row["close"], "close", positive=True)
    volume = _number(row["volume"], "volume")
    if volume < 0 or high < low or high < max(opening, close) or low > min(opening, close):
        raise ValueError("BAR_GEOMETRY")
    return {"symbol": symbol, "bar_timestamp": normalized, "source_timestamp": normalized,
            "open": opening, "high": high, "low": low, "close": close, "volume": volume}


def build_artifact(
    rows: Iterable[dict[str, Any]], *, symbol: str, trading_session: str,
    calendar: dict[str, Any], source: dict[str, str], available_at: str,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and canonicalize raw provider rows into immutable 1-minute evidence."""
    validate_calendar(calendar, MARKET)
    record = session(calendar, MARKET, trading_session)
    symbol = str(symbol).zfill(4)
    available = aware(available_at).astimezone(ZoneInfo(TIMEZONE))
    if available < aware(record["open_at"]):
        raise ValueError("AVAILABLE_BEFORE_SESSION")
    if not isinstance(source, dict) or set(source) != {"name", "revision", "source_digest"}:
        raise ValueError("SOURCE_PROVENANCE")
    if not all(isinstance(source[key], str) and source[key] for key in source):
        raise ValueError("SOURCE_PROVENANCE")
    allowed = set(expected_minutes(calendar, trading_session))
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        bar = _canonical_bar(row, symbol=symbol, trading_session=trading_session, allowed=allowed, available_at=available)
        prior = indexed.get(bar["bar_timestamp"])
        if prior is not None and prior != bar:
            raise ValueError("CONFLICTING_DUPLICATE_BAR")
        indexed[bar["bar_timestamp"]] = bar
    ordered = [indexed[timestamp] for timestamp in sorted(indexed)]
    missing = [timestamp for timestamp in expected_minutes(calendar, trading_session) if timestamp not in indexed]
    status = "COMPLETE" if not missing else "PARTIAL" if ordered else "UNAVAILABLE"
    core = {
        "schema_version": SCHEMA_VERSION, "market": MARKET, "symbol": symbol,
        "trading_session": trading_session, "timezone": TIMEZONE, "interval": INTERVAL,
        "bar_timestamp_convention": BAR_TIMESTAMP_CONVENTION,
        "calendar_identity": calendar["content_hash"], "calendar_version": calendar["version"],
        "source": dict(source), "available_at": available.isoformat(),
        "provenance": dict(provenance or {}), "expected_bar_count": len(allowed),
        "observed_bar_count": len(ordered), "missing_bar_timestamps": missing,
        "completeness": status, "bars": ordered,
    }
    return {**core, "content_hash": digest(core)}


def validate_artifact(value: dict[str, Any], *, calendar: dict[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "market", "symbol", "trading_session", "timezone", "interval",
                "bar_timestamp_convention", "calendar_identity", "calendar_version", "source", "available_at",
                "provenance", "expected_bar_count", "observed_bar_count", "missing_bar_timestamps", "completeness",
                "bars", "content_hash"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("ARTIFACT_SCHEMA")
    if value["schema_version"] != SCHEMA_VERSION or value["market"] != MARKET or value["timezone"] != TIMEZONE or value["interval"] != INTERVAL:
        raise ValueError("ARTIFACT_IDENTITY")
    if value["bar_timestamp_convention"] != BAR_TIMESTAMP_CONVENTION or value["completeness"] not in STATUSES:
        raise ValueError("ARTIFACT_CONVENTION")
    if value["content_hash"] != digest({key: item for key, item in value.items() if key != "content_hash"}):
        raise ValueError("ARTIFACT_DIGEST")
    if value["calendar_identity"] != calendar.get("content_hash") or value["calendar_version"] != calendar.get("version"):
        raise ValueError("CALENDAR_BINDING")
    rebuilt = build_artifact(value["bars"], symbol=value["symbol"], trading_session=value["trading_session"],
        calendar=calendar, source=value["source"], available_at=value["available_at"], provenance=value["provenance"])
    if rebuilt != value:
        raise ValueError("ARTIFACT_REPLAY")
    return value


def archive_path(root: Path | str, artifact: dict[str, Any]) -> Path:
    return Path(root) / "tw_intraday" / "1m" / artifact["trading_session"] / artifact["symbol"] / f"{artifact['content_hash']}.json"


def archive_artifact(artifact: dict[str, Any], *, root: Path | str, calendar: dict[str, Any]) -> Path:
    """Append-only local writer. An identical digest is idempotent; no latest alias exists."""
    validate_artifact(artifact, calendar=calendar)
    target = archive_path(root, artifact)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json(artifact) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") != encoded:
            raise ValueError("IMMUTABLE_ARCHIVE_COLLISION")
        return target
    temporary = target.with_suffix(".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(target)
    return target


def replay_artifact(*, root: Path | str, trading_session: str, symbol: str, content_hash: str, calendar: dict[str, Any]) -> dict[str, Any]:
    target = Path(root) / "tw_intraday" / "1m" / trading_session / str(symbol).zfill(4) / f"{content_hash}.json"
    if not target.is_file():
        raise FileNotFoundError("INTRADAY_ARTIFACT_MISSING")
    value = json.loads(target.read_text(encoding="utf-8"))
    if value.get("content_hash") != content_hash:
        raise ValueError("ARCHIVE_IDENTITY_MISMATCH")
    return validate_artifact(value, calendar=calendar)


def derive_path_metrics(artifact: dict[str, Any], *, calendar: dict[str, Any], reference_price: float | None = None,
                        predicted_range: tuple[float, float] | None = None, flat_band: float = 0.0) -> dict[str, Any]:
    """Offline path measurements. Partial evidence never becomes a trend classification."""
    validate_artifact(artifact, calendar=calendar)
    bars = artifact["bars"]
    if artifact["completeness"] != "COMPLETE" or not bars:
        return {"status": "INSUFFICIENT_EVIDENCE", "artifact_digest": artifact["content_hash"], "trend": None,
                "session_high": None, "session_low": None, "mfe": None, "mae": None, "range_touch": None}
    band = _number(flat_band, "flat_band")
    if band < 0:
        raise ValueError("FLAT_BAND")
    opening, closing = bars[0]["open"], bars[-1]["close"]
    high, low = max(row["high"] for row in bars), min(row["low"] for row in bars)
    direction = "UP" if closing > opening + band else "DOWN" if closing < opening - band else "FLAT"
    mfe = mae = None
    if reference_price is not None:
        ref = _number(reference_price, "reference_price", positive=True)
        mfe, mae = round(high - ref, 8), round(low - ref, 8)
    touch = None
    if predicted_range is not None:
        lower, upper = sorted((_number(predicted_range[0], "range_low", positive=True), _number(predicted_range[1], "range_high", positive=True)))
        hits = [row for row in bars if row["low"] <= upper and row["high"] >= lower]
        touch = {"touched": bool(hits), "first_touch_at": hits[0]["bar_timestamp"] if hits else None,
                 "occupancy_minutes": len(hits), "range": {"low": lower, "high": upper}}
    return {"status": "COMPLETE", "artifact_digest": artifact["content_hash"], "session_open": opening,
            "session_close": closing, "session_high": high, "session_low": low, "close_vs_open_direction": direction,
            "mfe": mfe, "mae": mae, "range_touch": touch}


def fetch_shioaji_1m_rows(api: Any, *, symbol: str, trading_session: str) -> list[dict[str, Any]]:
    """Provider adapter only: Shioaji kbars → untrusted raw 1-minute candidates.

    No login is performed here. Callers must separately establish provider
    support for same-session minute bars and pass the read-only API handle.
    """
    contract = api.Contracts.Stocks[str(symbol).zfill(4)]
    raw = api.kbars(contract, start=trading_session, end=trading_session)
    keys = (("ts", "Open", "High", "Low", "Close", "Volume"), ("ts", "open", "high", "low", "close", "volume"))
    selected = next((item for item in keys if all(hasattr(raw, key) for key in item)), None)
    if selected is None:
        raise ValueError("SHIOAJI_KBARS_SCHEMA")
    timestamps, opens, highs, lows, closes, volumes = (getattr(raw, key) for key in selected)
    if len({len(timestamps), len(opens), len(highs), len(lows), len(closes), len(volumes)}) != 1:
        raise ValueError("SHIOAJI_KBARS_LENGTH")
    return [{"symbol": str(symbol).zfill(4), "timestamp": item.isoformat() if hasattr(item, "isoformat") else str(item),
             "open": opening, "high": high, "low": low, "close": close, "volume": volume}
            for item, opening, high, low, close, volume in zip(timestamps, opens, highs, lows, closes, volumes)]
