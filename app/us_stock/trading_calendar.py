"""Dependency-free US trading-date and session semantics.

The runtime schedule is expressed in Asia/Taipei, while product identity is an
NYSE/Nasdaq trading date.  This module is the canonical boundary between those
two clocks; renderers must never infer a trading date from wall-clock text.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    current = date(year, month, 1)
    return current + timedelta(days=(weekday - current.weekday()) % 7 + 7 * (nth - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    current = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return current - timedelta(days=(current.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    # Gregorian computus; NYSE Good Friday is two days before Easter Sunday.
    a, b, c = year % 19, year // 100, year % 100
    d, e, f = b // 4, b % 4, (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return date(year, month, (h + l - 7 * m + 114) % 31 + 1)


def us_market_holidays(year: int) -> set[date]:
    holidays = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),       # MLK Day
        _nth_weekday(year, 2, 0, 3),       # Presidents Day
        _easter(year) - timedelta(days=2), # Good Friday
        _last_weekday(year, 5, 0),         # Memorial Day
        _observed(date(year, 6, 19)),      # Juneteenth
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),       # Labor Day
        _nth_weekday(year, 11, 3, 4),      # Thanksgiving
        _observed(date(year, 12, 25)),
    }
    # New Year's Day can be observed on Dec 31 of the prior year.
    holidays.add(_observed(date(year + 1, 1, 1)))
    return {item for item in holidays if item.year == year}


def is_us_trading_day(value: date) -> bool:
    return value.weekday() < 5 and value not in us_market_holidays(value.year)


def previous_or_same_us_trading_day(value: date) -> date:
    candidate = value
    while not is_us_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def resolve_us_effective_trading_date(reference: datetime, window: str) -> date:
    if window not in {"us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"}:
        raise ValueError("unsupported_us_window")
    return previous_or_same_us_trading_day(reference.astimezone(NEW_YORK).date())


def us_session_availability(reference: datetime, window: str) -> dict[str, str | bool]:
    ny = reference.astimezone(NEW_YORK)
    wall_date = ny.date()
    if not is_us_trading_day(wall_date):
        return {"state": "OFF_SESSION_VERIFICATION", "available": False, "reason": "US_NON_TRADING_DAY"}
    minute = ny.hour * 60 + ny.minute
    if window == "us_pre_market_2000" and minute < 4 * 60:
        return {"state": "PREMARKET_SESSION_NOT_STARTED", "available": False, "reason": "PREMARKET_DATA_NOT_YET_AVAILABLE"}
    return {"state": "SESSION_DATA_EXPECTED", "available": True, "reason": "WITHIN_EXPECTED_WINDOW"}
