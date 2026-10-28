"""Bounded public RSS discovery. Google RSS has no guaranteed exhaustive cursor."""
import time
from datetime import timedelta
from urllib.parse import quote
import feedparser
import requests
from app.research.tw_news_window import build_news_window, published_time


class NewsCandidates(list):
    def __init__(self, items=(), *, coverage=None):
        super().__init__(items)
        self.coverage = coverage or {}


def fetch_stock_news(stock_id, stock_name, max_items=None, *, window=None, reference=None):
    # max_items retained for caller compatibility, never an early top-N filter.
    window = window or build_news_window(reference)
    start = published_time(window['start'])
    end = published_time(window['as_of'])
    items, seen, failures = [], set(), []
    requests_made = 0
    deadline = time.monotonic() + 24
    day = start.date()
    # Per-day extension avoids a single ranked feed hiding an entire long weekend.
    # Overlap dates because provider after/before boundary semantics are not trusted.
    while day <= end.date() and requests_made < 8 and len(items) < 400:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            failures.append('RSS_TIME_BUDGET'); break
        query = f'{stock_name} {stock_id} 股票 after:{day-timedelta(days=1)} before:{day+timedelta(days=1)}'
        url = f'https://news.google.com/rss/search?q={quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'
        requests_made += 1
        try:
            response = requests.get(url, timeout=min(8, remaining), headers={'User-Agent': 'stock-ai-news/1.0'})
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            if feed.get('bozo'):
                failures.append('RSS_PARSE_ERROR')
            for entry in feed.entries:
                item = {'title': entry.get('title', ''), 'link': entry.get('link', ''),
                        'published': entry.get('published', ''),
                        'source': (entry.get('source', {}).get('title', '') if isinstance(entry.get('source', {}), dict) else str(entry.get('source') or ''))}
                identity = (item['link'], item['title'], item['published'])
                if identity not in seen:
                    seen.add(identity); items.append(item)
                if len(items) >= 400:
                    failures.append('RSS_CANDIDATE_BUDGET'); break
        except requests.Timeout:
            failures.append('RSS_TIMEOUT')
        except requests.RequestException:
            failures.append('RSS_TRANSPORT_ERROR')
        day += timedelta(days=1)
    if day <= end.date():
        failures.append('RSS_QUERY_BUDGET_OR_TRUNCATION')
    return NewsCandidates(items, coverage={'status': 'PARTIAL' if items else 'UNKNOWN',
        'reason_codes': sorted(set(['RSS_NO_EXHAUSTIVE_PAGINATION_CONTRACT'] + failures)),
        'request_count': requests_made, 'candidate_count': len(items),
        'provider_pagination': 'UNSUPPORTED', 'extended_query': 'BOUNDED_DAILY_SLICES',
        'window': window})
