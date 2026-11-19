"""Capture operation safety, not an authorization boundary against the same UID.

Progress logging is deliberately unrelated to capture permission. Only a
supervised scheduled context may originate evidence; readers remain read-only.
"""
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CONTEXT_ENV = 'STOCK_AI_CAPTURE_CONTEXT'
RUN_ENV = 'STOCK_AI_DELIVERY_RUN_ID'
VERSION = 'capture_execution_context_v1'
WINDOWS = {'TW': {'pre_open_0700'},
           'US': {'us_pre_market_2000', 'us_intraday_2300', 'us_post_close_review_0630'}}


def make_context(*, run_id, market, window, mode, now=None):
    from app.evaluation.session_calendar import load_calendar, latest_completed_session
    now = now or datetime.now(timezone.utc)
    if market == 'US' and window == 'us_post_close_review_0630':
        day = latest_completed_session(load_calendar('US'), 'US', now)['session_date']
    else:
        day = now.astimezone(ZoneInfo('Asia/Taipei' if market == 'TW' else 'America/New_York')).date().isoformat()
    return {'schema_version': VERSION, 'run_id': run_id, 'market': market,
            'window': window, 'session_date': day, 'mode': mode,
            'issued_at': now.isoformat()}


def decision(*, market, window, session_date, dry_run=False, environment=None, now=None):
    env = os.environ if environment is None else environment
    if dry_run:
        return 'CAPTURE_DRY_RUN'
    try:
        context = json.loads(env.get(CONTEXT_ENV, 'null'))
        if not isinstance(context, dict) or context.get('schema_version') != VERSION:
            return 'CAPTURE_CONTEXT_MISSING_OR_UNKNOWN'
        if context.get('mode') != 'scheduled':
            return 'CAPTURE_MODE_DENIED'
        if not context.get('run_id') or context['run_id'] != env.get(RUN_ENV):
            return 'CAPTURE_RUN_CONFLICT'
        if window not in WINDOWS.get(market, set()):
            return 'CAPTURE_WINDOW_DENIED'
        if any(context.get(k) != v for k, v in
               [('market', market), ('window', window), ('session_date', session_date)]):
            return 'CAPTURE_IDENTITY_CONFLICT'
        issued = datetime.fromisoformat(context['issued_at'])
        current = now or datetime.now(timezone.utc)
        if issued.tzinfo is None or not 0 <= (current-issued).total_seconds() <= 3600:
            return 'CAPTURE_CONTEXT_EXPIRED'
        expected = make_context(run_id=context['run_id'], market=market,
                                window=window, mode='scheduled', now=issued)
        if expected['session_date'] != session_date:
            return 'CAPTURE_SESSION_CONFLICT'
    except (ValueError, KeyError, TypeError):
        return 'CAPTURE_CONTEXT_INVALID'
    return 'CAPTURE_ALLOWED'


def require_capture(**kwargs):
    reason = decision(**kwargs)
    if reason != 'CAPTURE_ALLOWED':
        raise ValueError(reason)


def reject_inherited_context(*, manual=False, dry_run=False):
    """Manual/direct worker paths cannot accidentally inherit scheduled rights."""
    if manual or dry_run:
        os.environ[CONTEXT_ENV] = json.dumps({'schema_version': VERSION,
            'mode': 'dry_run' if dry_run else 'manual_rerun'})
