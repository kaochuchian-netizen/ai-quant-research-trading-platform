"""Safe shared presentation normalization for financial values and dates."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

UNSAFE_FINANCIAL_TEXT = "正式資料尚無法安全標準化"


def normalize_date_presentation(value: Any, *, timezone_name: str | None = None) -> str:
    if value is None or value == "":
        return "資料尚未取得"
    if isinstance(value, datetime):
        current = value
        if current.tzinfo is None:
            if not timezone_name:
                return UNSAFE_FINANCIAL_TEXT
            current = current.replace(tzinfo=ZoneInfo(timezone_name))
        elif timezone_name:
            current = current.astimezone(ZoneInfo(timezone_name))
        return current.isoformat(timespec="minutes")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if text.startswith("datetime.date(") or text.startswith("datetime.datetime("):
        return UNSAFE_FINANCIAL_TEXT
    return text


def normalize_financial_value(
    value: Any, *, unit: str | None, currency: str | None, scale: Any = 1,
    source: str, period_end: Any = None, filing_date: Any = None,
) -> dict[str, Any]:
    raw = {"raw_value": value, "raw_unit": unit, "raw_currency": currency, "raw_scale": scale}
    try:
        number = Decimal(str(value))
        multiplier = Decimal(str(scale))
    except (InvalidOperation, ValueError, TypeError):
        number = None
        multiplier = None
    safe_currency = str(currency or "").upper()
    safe_unit = str(unit or "").lower()
    monetary = safe_unit in {"currency", "per_share"}
    currency_valid = safe_currency in {"USD", "TWD"} if monetary else safe_currency in {"", "USD", "TWD"}
    valid = number is not None and multiplier is not None and currency_valid and safe_unit in {"currency", "shares", "per_share", "ratio", "percent"}
    normalized = number * multiplier if valid else None
    return {
        **raw,
        "normalized_value": float(normalized) if normalized is not None else None,
        "normalized_unit": unit if valid else None,
        "normalized_currency": safe_currency if valid and monetary else None,
        "source": source,
        "period_end": normalize_date_presentation(period_end) if period_end else None,
        "filing_date": normalize_date_presentation(filing_date) if filing_date else None,
        "safe_to_present": valid,
        "presentation": str(float(normalized)) if valid else UNSAFE_FINANCIAL_TEXT,
    }
