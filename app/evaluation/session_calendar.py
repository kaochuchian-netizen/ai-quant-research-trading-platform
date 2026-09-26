"""AI-DEV-251D immutable, offline exchange-session prerequisites."""
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from app.evaluation.prediction_regression_contract import aware, canonical_json
from app.evaluation.offline_report_projection import digest

ROOT = Path(__file__).resolve().parents[2]
VERSION = "market_calendar_snapshot_v1"
ZONES = {"TW": "Asia/Taipei", "US": "America/New_York"}
STATES = {"NORMAL", "EARLY_CLOSE", "HOLIDAY", "WEEKEND", "SPECIAL_CLOSURE"}
class CalendarError(ValueError):
    pass

def validate_calendar(value, market):
    try:
        if not isinstance(value, dict):
            raise CalendarError("CALENDAR_MISSING")
        if value["schema_version"] != VERSION or value["market"] != market or value["timezone"] != ZONES[market]:
            raise CalendarError("CALENDAR_SCHEMA")
        if digest({k:v for k,v in value.items() if k != "content_hash"}) != value["content_hash"]:
            raise CalendarError("CALENDAR_DIGEST_MISMATCH")
        expected_identity = "TWSE" if market == "TW" else "NYSE"
        expected_host = "https://www.twse.com.tw/" if market == "TW" else "https://www.nyse.com/"
        if value["source"]["identity"] != expected_identity or not value["source"]["url"].startswith(expected_host) or len(value["source"]["document_sha256"]) != 64:
            raise CalendarError("CALENDAR_AUTHORITY_MISSING")
        if type(value["revision"]) is not int or value["revision"] < 1 or not value["version"]:
            raise CalendarError("CALENDAR_VERSION")
        start, end = date.fromisoformat(value["coverage_start"]), date.fromisoformat(value["coverage_end"])
        expected = [(start + timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
        if not expected or [r["session_date"] for r in value["days"]] != expected:
            raise CalendarError("CALENDAR_COVERAGE")
        for r in value["days"]:
            if r["state"] not in STATES:
                raise CalendarError("CALENDAR_STATE")
            if r["state"] in {"NORMAL", "EARLY_CLOSE"}:
                opening, closing = aware(r["open_at"]), aware(r["close_at"])
                if closing <= opening or any(t.astimezone(ZoneInfo(ZONES[market])).date().isoformat() != r["session_date"] for t in (opening,closing)):
                    raise CalendarError("CALENDAR_SESSION")
            elif r["open_at"] is not None or r["close_at"] is not None:
                raise CalendarError("CALENDAR_NON_SESSION")
        return value
    except CalendarError:
        raise
    except (KeyError, TypeError, ValueError):
        raise CalendarError("CALENDAR_MALFORMED") from None

def load_calendar(market, root=None):
    root = Path(root) if root else ROOT / "config/governance/market_calendars"
    try:
        manifest = json.loads((root / "manifest_v1.json").read_text())
        pin = manifest[market]
        value = json.loads((root / pin["file"]).read_text())
    except (OSError, ValueError, KeyError):
        raise CalendarError("CALENDAR_MISSING") from None
    validate_calendar(value, market)
    if value["content_hash"] != pin["content_hash"]:
        raise CalendarError("CALENDAR_PIN_MISMATCH")
    return value

def session(value, market, day):
    validate_calendar(value, market)
    if not value["coverage_start"] <= day <= value["coverage_end"]:
        raise CalendarError("CALENDAR_OUTSIDE_COVERAGE")
    record = next((r for r in value["days"] if r["session_date"] == day), None)
    if record is None:
        raise CalendarError("CALENDAR_SESSION_UNKNOWN")
    if record["state"] not in {"NORMAL", "EARLY_CLOSE"}:
        raise CalendarError("NON_TRADING_SESSION")
    return record

def evaluator_calendar(value, review_session, evaluated_at):
    market = value["market"]
    record = session(value, market, review_session)
    limit = aware(evaluated_at)
    if limit < aware(record["close_at"]):
        raise CalendarError("SESSION_INCOMPLETE")
    rows = [{"market": market, "session_date": r["session_date"], "open_at": r["open_at"], "close_at": r["close_at"]}
            for r in value["days"] if r["state"] in {"NORMAL", "EARLY_CLOSE"} and r["session_date"] <= review_session]
    return {"sessions": rows, "content_hash": digest(rows), "source_ref": value["content_hash"],
            "coverage_through": evaluated_at}
