"""Versioned observed-time evidence; no offset guessing or clock-based replay."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

VERSION = "tw_observed_timestamp_v1"
TW = ZoneInfo("Asia/Taipei")


def observed_time(raw, *, captured_at, session_date, source_timezone="Asia/Taipei"):
    result = {"schema_version": VERSION, "raw_timestamp": str(raw or ""),
              "captured_at": captured_at, "normalized_timestamp": None,
              "freshness_status": "unavailable", "reason": "MISSING_TIMESTAMP",
              "freshness_basis": "same_session_not_future_not_tick_recency",
              "age_seconds": None}
    try:
        captured = datetime.fromisoformat(captured_at)
        if captured.tzinfo is None:
            raise ValueError("naive_capture")
        if raw is None or raw == "":
            return result
        if isinstance(raw, bool):
            raise ValueError("boolean_timestamp")
        numeric = str(raw).isdigit()
        if numeric:
            value = int(raw)
            scale = {10: 1, 13: 1000, 16: 1000000, 19: 1000000000}.get(len(str(value)))
            if scale is None:
                raise ValueError("unknown_epoch_precision")
            seconds, remainder = divmod(value, scale)
            instant = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds, microseconds=remainder * 1000000 // scale)
        else:
            if not isinstance(raw, datetime) and len(str(raw)) < 19:
                raise ValueError("date_without_time")
            instant = raw if isinstance(raw, datetime) else datetime.fromisoformat(str(raw))
            if instant.tzinfo is None:
                if source_timezone != "Asia/Taipei":
                    raise ValueError("undeclared_naive_zone")
                instant = instant.replace(tzinfo=TW)
        local = instant.astimezone(TW)
        result["normalized_timestamp"] = local.isoformat()
        result["age_seconds"] = (captured - instant).total_seconds()
        if instant > captured:
            result.update(freshness_status="invalid", reason="FUTURE_TIMESTAMP")
        elif local.date().isoformat() != session_date:
            result.update(freshness_status="stale", reason="SESSION_DATE_MISMATCH")
        else:
            result.update(freshness_status="fresh", reason="SAME_SESSION_NOT_FUTURE")
    except (ValueError, TypeError, OverflowError):
        result.update(freshness_status="invalid", reason="MALFORMED_TIMESTAMP")
    return result
