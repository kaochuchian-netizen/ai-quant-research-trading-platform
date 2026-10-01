"""Offline reference operations for the 257 design, never imported by producers.

The provider minute grid and flat-band parameter still require activation review.
No fetching, persistence, strategy changes or production classification occurs here.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def canonical_bars(rows, *, expected_timestamps, as_of):
    cutoff = datetime.fromisoformat(as_of)
    if cutoff.tzinfo is None:
        raise ValueError("NAIVE_AS_OF")
    expected = list(expected_timestamps)
    if not expected or len(expected) != len(set(expected)):
        raise ValueError("INVALID_EXPECTED_GRID")
    parsed = [datetime.fromisoformat(t) for t in expected]
    if any(t.tzinfo is None for t in parsed) or parsed != sorted(parsed):
        raise ValueError("INVALID_EXPECTED_GRID")
    indexed = {}
    for row in rows:
        if set(row) != {"timestamp", "open", "high", "low", "close", "volume"}:
            raise ValueError("BAR_SCHEMA")
        time = datetime.fromisoformat(row["timestamp"])
        if time.tzinfo is None or time > cutoff or row["timestamp"] not in expected:
            raise ValueError("BAR_TIME")
        try:
            if any(isinstance(row[k], bool) for k in ("open", "high", "low", "close", "volume")):
                raise ValueError("BAR_NUMBER")
            o, h, l, c, v = [Decimal(str(row[k])) for k in ("open", "high", "low", "close", "volume")]
            if not all(x.is_finite() for x in (o,h,l,c,v)) or min(o,h,l,c) <= 0 or v < 0 or h < max(o,l,c) or l > min(o,h,c):
                raise ValueError("BAR_GEOMETRY")
        except InvalidOperation:
            raise ValueError("BAR_NUMBER") from None
        prior = indexed.get(row["timestamp"])
        if prior is not None and prior != row:
            raise ValueError("CONFLICTING_DUPLICATE")
        indexed[row["timestamp"]] = dict(row)
    missing = [t for t in expected if t not in indexed]
    ordered = [indexed[t] for t in expected if t in indexed]
    return {"bars": ordered, "missing_timestamps": missing,
            "coverage": len(ordered)/len(expected), "input_digest": digest(ordered),
            "status": "DATA_AVAILABLE" if not missing else "DATA_MISSING"}


def classify_observed_path(evidence, *, previous_close, flat_band, parameter_version):
    """Explicit design parameter only; no default band and no production use."""
    if evidence.get("status") != "DATA_AVAILABLE" or evidence.get("missing_timestamps") or not evidence.get("bars"):
        return {"status": "INSUFFICIENT_EVIDENCE", "trend": None}
    if digest(evidence["bars"]) != evidence.get("input_digest"):
        raise ValueError("INPUT_DIGEST_MISMATCH")
    band, previous = Decimal(str(flat_band)), Decimal(str(previous_close))
    if not parameter_version or not band.is_finite() or not previous.is_finite() or band < 0 or previous <= 0:
        raise ValueError("UNAPPROVED_OR_INVALID_PARAMETER")
    opening = Decimal(str(evidence["bars"][0]["open"]))
    close = Decimal(str(evidence["bars"][-1]["close"]))
    trend = ("OPEN_LOW_RISE" if opening < previous-band and close > opening+band else
             "OPEN_HIGH_FALL" if opening > previous+band and close < opening-band else
             "BULLISH" if close > opening+band else "BEARISH" if close < opening-band else "SIDEWAYS")
    return {"schema_version": "tw_observed_path_trend_v1", "status": "OFFLINE_DESIGN_ONLY",
            "trend": trend, "input_digest": evidence["input_digest"],
            "parameter_version": parameter_version, "flat_band": str(band),
            "previous_close": str(previous), "production_eligible": False}
