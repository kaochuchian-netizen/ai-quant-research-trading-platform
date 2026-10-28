"""One aware, calendar-bound news window; no live calendar or market access."""
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo('Asia/Taipei')


def published_time(value):
    try:
        text = str(value).strip()
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        try:
            parsed = parsedate_to_datetime(str(value))
        except (ValueError, TypeError, OverflowError):
            return None
    # Unknown publisher timezone must not be guessed.
    return parsed.astimezone(TAIPEI) if parsed.tzinfo else None


def build_news_window(reference, *, calendar=None):
    from app.evaluation.session_calendar import load_calendar, latest_completed_session
    as_of = published_time(reference)
    if as_of is None:
        raise ValueError('NEWS_AS_OF_TIMEZONE_REQUIRED')
    calendar = load_calendar('TW') if calendar is None else calendar
    previous = latest_completed_session(calendar, 'TW', as_of.isoformat())
    close = published_time(previous['close_at'])
    start = min(as_of - timedelta(hours=72), close)
    return {'schema_version': 'tw_news_window_v1', 'timezone': 'Asia/Taipei',
            'start': start.isoformat(), 'as_of': as_of.isoformat(),
            'previous_completed_session': previous['session_date'],
            'previous_close': close.isoformat(),
            'policy': '72h_or_previous_completed_close_whichever_earlier'}


def window_reason(value, window):
    published = published_time(value)
    if published is None:
        return 'NEWS_DATE_UNKNOWN'
    if published > published_time(window['as_of']):
        return 'NEWS_AFTER_AS_OF'
    if published < published_time(window['start']):
        return 'NEWS_OUTSIDE_WINDOW'
    return None
