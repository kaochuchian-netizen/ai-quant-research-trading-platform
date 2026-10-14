"""AI-DEV-270C immutable, replayable TW one-minute Kbars evidence.

This module is offline-only.  It deliberately does not schedule acquisition,
persist production data, or feed the 15:00/17:00 evaluators.
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


SCHEMA_VERSION = "tw_intraday_1m_artifact_v2"
MARKET = "TW"
TIMEZONE = "Asia/Taipei"
INTERVAL = "1m"
BAR_TIMESTAMP_CONVENTION = "BAR_END_TIMESTAMP_HALF_OPEN_1M"
STATUSES = {"COMPLETE", "SPARSE_UNVERIFIED", "PARTIAL", "UNAVAILABLE"}
FULL_SESSION_PROOF_KIND = "AUTHORITATIVE_FULL_SESSION_GRID_V1"
PARTIAL_PROOF_KIND = "AUTHORITATIVE_ACQUISITION_INCOMPLETE_V1"
OBSERVED_PATH_SCHEMA_VERSION = "tw_intraday_observed_path_evidence_v1"


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


def decode_shioaji_kbars_timestamp(raw_timestamp: Any) -> str:
    """Decode Shioaji Kbars' integer-ns *local wall-clock* representation.

    Shioaji's documented Python example casts ``ts`` to ``Datetime(ns)`` and
    emits TW labels such as 09:01.  It is not a UTC epoch conversion.  The
    epoch arithmetic below is intentionally timezone-free, then the resulting
    wall-clock value is explicitly localized to Asia/Taipei.
    """
    if isinstance(raw_timestamp, bool):
        raise ValueError("SHIOAJI_KBARS_TIMESTAMP")
    if isinstance(raw_timestamp, str):
        if not raw_timestamp.isdigit():
            raise ValueError("SHIOAJI_KBARS_TIMESTAMP")
        raw_timestamp = int(raw_timestamp)
    if not isinstance(raw_timestamp, int) or raw_timestamp < 0:
        raise ValueError("SHIOAJI_KBARS_TIMESTAMP")
    if raw_timestamp % 1_000_000_000:
        raise ValueError("SHIOAJI_KBARS_TIMESTAMP_PRECISION")
    try:
        wall_clock = datetime(1970, 1, 1) + timedelta(seconds=raw_timestamp // 1_000_000_000)
    except OverflowError:
        raise ValueError("SHIOAJI_KBARS_TIMESTAMP") from None
    if wall_clock.second or wall_clock.microsecond:
        raise ValueError("SHIOAJI_KBARS_TIMESTAMP_PRECISION")
    return wall_clock.replace(tzinfo=ZoneInfo(TIMEZONE)).isoformat()


def expected_minutes(calendar: dict[str, Any], trading_session: str) -> list[str]:
    """Return bar-end labels: 09:01..13:30 for a 09:00..13:30 session."""
    validate_calendar(calendar, MARKET)
    record = session(calendar, MARKET, trading_session)
    opening = aware(record["open_at"]).astimezone(ZoneInfo(TIMEZONE))
    closing = aware(record["close_at"]).astimezone(ZoneInfo(TIMEZONE))
    values: list[str] = []
    cursor = opening + timedelta(minutes=1)
    while cursor <= closing:
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
    timestamp = row.get("bar_timestamp") or row.get("timestamp")
    if not isinstance(timestamp, str):
        raise ValueError("BAR_TIMESTAMP")
    parsed = _minute(timestamp)
    normalized = parsed.isoformat()
    if normalized not in allowed or parsed.date().isoformat() != trading_session:
        raise ValueError("BAR_OUTSIDE_SESSION")
    if parsed > available_at:
        raise ValueError("BAR_INCOMPLETE_OR_FUTURE")
    opening = _number(row["open"], "open", positive=True)
    high = _number(row["high"], "high", positive=True)
    low = _number(row["low"], "low", positive=True)
    close = _number(row["close"], "close", positive=True)
    volume = _number(row["volume"], "volume")
    if volume < 0 or high < low or high < max(opening, close) or low > min(opening, close):
        raise ValueError("BAR_GEOMETRY")
    source_timestamp = row.get("source_timestamp", normalized)
    if not isinstance(source_timestamp, str) or not source_timestamp:
        raise ValueError("BAR_SOURCE_TIMESTAMP")
    return {"symbol": symbol, "bar_timestamp": normalized, "source_timestamp": source_timestamp,
            "open": opening, "high": high, "low": low, "close": close, "volume": volume}


def _completeness(*, ordered: list[dict[str, Any]], missing: list[str], expected: list[str], proof: dict[str, Any] | None) -> str:
    if not ordered:
        return "UNAVAILABLE"
    if proof is None:
        return "SPARSE_UNVERIFIED"
    if not isinstance(proof, dict) or set(proof) != {"kind", "source", "source_digest", "verified_label_count"}:
        raise ValueError("COMPLETENESS_PROOF")
    if (not isinstance(proof["source"], str) or not proof["source"] or not isinstance(proof["source_digest"], str)
            or len(proof["source_digest"]) != 64 or any(char not in "0123456789abcdefABCDEF" for char in proof["source_digest"])):
        raise ValueError("COMPLETENESS_PROOF")
    if proof["kind"] == FULL_SESSION_PROOF_KIND:
        if missing or not isinstance(proof["verified_label_count"], int) or isinstance(proof["verified_label_count"], bool) or proof["verified_label_count"] != len(expected):
            raise ValueError("COMPLETE_PROOF_MISMATCH")
        return "COMPLETE"
    if proof["kind"] == PARTIAL_PROOF_KIND:
        if not missing or not isinstance(proof["verified_label_count"], int) or isinstance(proof["verified_label_count"], bool) or proof["verified_label_count"] < len(ordered):
            raise ValueError("PARTIAL_PROOF_MISMATCH")
        return "PARTIAL"
    raise ValueError("COMPLETENESS_PROOF")


def build_artifact(rows: Iterable[dict[str, Any]], *, symbol: str, trading_session: str,
                   calendar: dict[str, Any], source: dict[str, str], available_at: str,
                   provenance: dict[str, Any] | None = None, completeness_proof: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate and canonicalize untrusted provider rows into v2 evidence."""
    validate_calendar(calendar, MARKET)
    record = session(calendar, MARKET, trading_session)
    symbol = str(symbol).zfill(4)
    available = aware(available_at).astimezone(ZoneInfo(TIMEZONE))
    if available < aware(record["open_at"]):
        raise ValueError("AVAILABLE_BEFORE_SESSION")
    if not isinstance(source, dict) or set(source) != {"name", "revision", "source_digest"} or not all(isinstance(source[key], str) and source[key] for key in source):
        raise ValueError("SOURCE_PROVENANCE")
    expected = expected_minutes(calendar, trading_session)
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        bar = _canonical_bar(row, symbol=symbol, trading_session=trading_session, allowed=set(expected), available_at=available)
        prior = indexed.get(bar["bar_timestamp"])
        if prior is not None and prior != bar:
            raise ValueError("CONFLICTING_DUPLICATE_BAR")
        indexed[bar["bar_timestamp"]] = bar
    ordered = [indexed[timestamp] for timestamp in sorted(indexed)]
    missing = [timestamp for timestamp in expected if timestamp not in indexed]
    status = _completeness(ordered=ordered, missing=missing, expected=expected, proof=completeness_proof)
    core = {
        "schema_version": SCHEMA_VERSION, "market": MARKET, "symbol": symbol,
        "trading_session": trading_session, "timezone": TIMEZONE, "interval": INTERVAL,
        "bar_timestamp_convention": BAR_TIMESTAMP_CONVENTION,
        "calendar_identity": calendar["content_hash"], "calendar_version": calendar["version"],
        "source": dict(source), "available_at": available.isoformat(), "provenance": dict(provenance or {}),
        "expected_bar_labels": expected, "expected_bar_count": len(expected),
        "observed_bar_labels": [row["bar_timestamp"] for row in ordered], "observed_bar_count": len(ordered),
        "absent_bar_labels": missing, "absent_bar_count": len(missing),
        "coverage_ratio": len(ordered) / len(expected), "completeness": status,
        "completeness_proof": completeness_proof, "bars": ordered,
    }
    return {**core, "content_hash": digest(core)}


def validate_artifact(value: dict[str, Any], *, calendar: dict[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "market", "symbol", "trading_session", "timezone", "interval", "bar_timestamp_convention", "calendar_identity", "calendar_version", "source", "available_at", "provenance", "expected_bar_labels", "expected_bar_count", "observed_bar_labels", "observed_bar_count", "absent_bar_labels", "absent_bar_count", "coverage_ratio", "completeness", "completeness_proof", "bars", "content_hash"}
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
    rebuilt = build_artifact(value["bars"], symbol=value["symbol"], trading_session=value["trading_session"], calendar=calendar, source=value["source"], available_at=value["available_at"], provenance=value["provenance"], completeness_proof=value["completeness_proof"])
    if rebuilt != value:
        raise ValueError("ARTIFACT_REPLAY")
    return value


def archive_path(root: Path | str, artifact: dict[str, Any]) -> Path:
    return Path(root) / "tw_intraday" / "1m" / "v2" / artifact["trading_session"] / artifact["symbol"] / f"{artifact['content_hash']}.json"


def archive_artifact(artifact: dict[str, Any], *, root: Path | str, calendar: dict[str, Any]) -> Path:
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
    target = Path(root) / "tw_intraday" / "1m" / "v2" / trading_session / str(symbol).zfill(4) / f"{content_hash}.json"
    if not target.is_file():
        raise FileNotFoundError("INTRADAY_ARTIFACT_MISSING")
    value = json.loads(target.read_text(encoding="utf-8"))
    if value.get("content_hash") != content_hash:
        raise ValueError("ARCHIVE_IDENTITY_MISMATCH")
    return validate_artifact(value, calendar=calendar)


def observed_path_evidence(artifact: dict[str, Any], *, calendar: dict[str, Any], flat_band: float = 0.0) -> dict[str, Any]:
    """Project immutable bars without overstating sparse-provider coverage.

    Kbars does not prove whether absent minutes were zero-trade minutes or an
    acquisition gap.  ``SPARSE_UNVERIFIED`` is therefore useful *observed*
    evidence only: the values below are explicitly named observed values and
    no first-touch, occupancy, MFE/MAE, or verified session extrema are
    emitted.  Consumers can retain the provenance while remaining fail closed
    for full-path claims.
    """
    value = validate_artifact(artifact, calendar=calendar)
    bars = value["bars"]
    base = {
        "schema_version": OBSERVED_PATH_SCHEMA_VERSION,
        "artifact_digest": value["content_hash"],
        "market": value["market"],
        "symbol": value["symbol"],
        "trading_session": value["trading_session"],
        "source": dict(value["source"]),
        "calendar_identity": value["calendar_identity"],
        "completeness": value["completeness"],
        "expected_bar_count": value["expected_bar_count"],
        "observed_bar_count": value["observed_bar_count"],
        "absent_bar_count": value["absent_bar_count"],
        "coverage_ratio": value["coverage_ratio"],
        "absent_bar_labels": list(value["absent_bar_labels"]),
        "missingness": "UNPROVEN_ABSENT_MINUTES" if value["completeness"] == "SPARSE_UNVERIFIED" else "NONE" if value["completeness"] == "COMPLETE" else "INCOMPLETE_OR_UNAVAILABLE",
    }
    if not bars:
        return {
            **base,
            "evidence_status": "UNAVAILABLE",
            "path_metrics_status": "INSUFFICIENT_EVIDENCE",
            "observed_open": None, "observed_close": None,
            "observed_high": None, "observed_low": None,
            "observed_close_vs_open_direction": None,
        }
    band = _number(flat_band, "flat_band")
    if band < 0:
        raise ValueError("FLAT_BAND")
    opening, closing = bars[0]["open"], bars[-1]["close"]
    direction = "UP" if closing > opening + band else "DOWN" if closing < opening - band else "FLAT"
    observed = {
        **base,
        "evidence_status": "COMPLETE_PATH" if value["completeness"] == "COMPLETE" else "OBSERVED_ONLY",
        "path_metrics_status": "AVAILABLE" if value["completeness"] == "COMPLETE" else "INSUFFICIENT_EVIDENCE",
        "observed_open": opening,
        "observed_close": closing,
        "observed_high": max(row["high"] for row in bars),
        "observed_low": min(row["low"] for row in bars),
        "observed_close_vs_open_direction": direction,
    }
    if value["completeness"] == "COMPLETE":
        metrics = derive_path_metrics(value, calendar=calendar, flat_band=flat_band)
        observed["verified_path_metrics"] = metrics
    return observed


def derive_path_metrics(artifact: dict[str, Any], *, calendar: dict[str, Any], reference_price: float | None = None, predicted_range: tuple[float, float] | None = None, flat_band: float = 0.0) -> dict[str, Any]:
    """Only a positively proven full path may yield path-dependent metrics."""
    validate_artifact(artifact, calendar=calendar)
    bars = artifact["bars"]
    if artifact["completeness"] != "COMPLETE" or not bars:
        return {"status": "INSUFFICIENT_EVIDENCE", "artifact_digest": artifact["content_hash"], "trend": None, "session_high": None, "session_low": None, "mfe": None, "mae": None, "range_touch": None}
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
        lower, upper = (_number(predicted_range[0], "range_low", positive=True), _number(predicted_range[1], "range_high", positive=True))
        if lower > upper:
            raise ValueError("PREDICTED_RANGE_REVERSED")
        hits = [row for row in bars if row["low"] <= upper and row["high"] >= lower]
        touch = {"touched": bool(hits), "first_touch_at": hits[0]["bar_timestamp"] if hits else None, "occupancy_minutes": len(hits), "range": {"low": lower, "high": upper}}
    return {"status": "COMPLETE", "artifact_digest": artifact["content_hash"], "session_open": opening, "session_close": closing, "session_high": high, "session_low": low, "close_vs_open_direction": direction, "mfe": mfe, "mae": mae, "range_touch": touch}


def fetch_shioaji_1m_rows(api: Any, *, symbol: str, trading_session: str) -> list[dict[str, Any]]:
    """Read-only Shioaji Kbars adapter with explicit numeric-ts decoding."""
    contract = api.Contracts.Stocks[str(symbol).zfill(4)]
    raw = api.kbars(contract, start=trading_session, end=trading_session)
    keys = (("ts", "Open", "High", "Low", "Close", "Volume"), ("ts", "open", "high", "low", "close", "volume"))
    selected = next((item for item in keys if all(hasattr(raw, key) for key in item)), None)
    if selected is None:
        raise ValueError("SHIOAJI_KBARS_SCHEMA")
    timestamps, opens, highs, lows, closes, volumes = (getattr(raw, key) for key in selected)
    if len({len(timestamps), len(opens), len(highs), len(lows), len(closes), len(volumes)}) != 1:
        raise ValueError("SHIOAJI_KBARS_LENGTH")
    values = []
    for item, opening, high, low, close, volume in zip(timestamps, opens, highs, lows, closes, volumes):
        if isinstance(item, (int, str)) and not isinstance(item, bool):
            timestamp = decode_shioaji_kbars_timestamp(item)
            source_timestamp = str(item)
        elif isinstance(item, datetime):
            timestamp = (item.replace(tzinfo=ZoneInfo(TIMEZONE)) if item.tzinfo is None else item.astimezone(ZoneInfo(TIMEZONE))).isoformat()
            source_timestamp = item.isoformat()
        else:
            raise ValueError("SHIOAJI_KBARS_TIMESTAMP")
        values.append({"symbol": str(symbol).zfill(4), "bar_timestamp": timestamp, "source_timestamp": source_timestamp, "open": opening, "high": high, "low": low, "close": close, "volume": volume})
    return values
