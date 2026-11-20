"""Explicit supervised context for synthetic persistence fixtures only."""
from contextlib import contextmanager
from datetime import datetime
import json
import os
from unittest.mock import patch
from app.runtime.capture_context import make_context, CONTEXT_ENV, RUN_ENV


@contextmanager
def scheduled(market='US', window='us_pre_market_2000', day='2026-09-24'):
    at = datetime.fromisoformat(day + ('T07:00:00+08:00' if market=='TW' else 'T08:00:00-04:00'))
    if window == 'us_post_close_review_0630':
        at = datetime.fromisoformat(day+'T17:30:00-04:00')
    context = make_context(run_id='fixture-run', market=market, window=window, mode='scheduled', now=at)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return at if tz is None else at.astimezone(tz)
    with patch.dict(os.environ, {CONTEXT_ENV:json.dumps(context),RUN_ENV:'fixture-run'}), patch('app.runtime.capture_context.datetime', Clock):
        yield context
