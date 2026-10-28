"""Offline, pinned-calendar US news window. No acquisition or credentials."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.evaluation.session_calendar import load_calendar, latest_completed_session


def aware_time(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('US_NEWS_TIMEZONE_REQUIRED')
    return parsed


def news_window(as_of):
    instant = aware_time(as_of).astimezone(ZoneInfo('America/New_York'))
    calendar = load_calendar('US')
    previous = latest_completed_session(calendar, 'US', instant.isoformat())
    close = aware_time(previous['close_at'])
    # Subtract elapsed UTC hours, not DST-sensitive wall-clock hours.
    start = min(instant.astimezone(timezone.utc) - timedelta(hours=72), close)
    return {'schema_version': 'us_news_window_v1', 'timezone': 'America/New_York',
            'as_of': instant.isoformat(), 'start': start.astimezone(ZoneInfo('America/New_York')).isoformat(),
            'previous_completed_session': previous['session_date'], 'previous_close': close.isoformat(),
            'calendar_hash': calendar['content_hash']}


def in_window(published, window):
    try:
        return aware_time(window['start']) <= aware_time(published) <= aware_time(window['as_of'])
    except (ValueError, TypeError, OverflowError):
        return False
