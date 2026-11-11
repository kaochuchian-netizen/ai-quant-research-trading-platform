"""US direct-source selection; mocked providers and body fetches only."""
import unittest
from unittest.mock import Mock, PropertyMock, patch
from yfinance.exceptions import YFDataException
from app.us_stock.live_data import YFinanceUSClient
from tests.article_content_fixture import with_article

ASOF = '2026-10-29T20:00:00+08:00'
def row(host):
    return {'title': 'Tesla battery production update', 'publisher': 'Finance',
            'pubDate': '2026-10-29T10:00:00Z', 'link': f'https://{host}/article/123', 'contentType': 'STORY'}

class DirectNewsTests(unittest.TestCase):
    def run_news(self, rows, usable=True, error=None):
        ticker = Mock()
        if error:
            type(ticker).news = PropertyMock(side_effect=error)
        else:
            ticker.news = rows
        client = YFinanceUSClient()
        with patch('app.research.article_evidence.enrich', side_effect=lambda rows, **kw: [with_article(r) for r in rows] if usable else rows) as enrich, patch('app.us_stock.news_rss_fallback.fetch_us_google_news_rss') as rss:
            result = client._fetch_news(ticker, 'TSLA', {'symbol': 'TSLA', 'name': 'Tesla'}, {'source_timestamp': ASOF})
        rss.assert_not_called()
        self.assertEqual(client.article_retriever.allowed_hosts, {'finance.yahoo.com', 'news.cnyes.com'})
        return result, enrich

    def test_yahoo_priority(self):
        (items, diagnostics), enrich = self.run_news([row('finance.yahoo.com'), row('news.cnyes.com')])
        self.assertTrue(items[0]['investment_usable'])
        self.assertEqual(enrich.call_count, 1)
        self.assertEqual(diagnostics['source_attempts']['CNYES']['status'], 'NOT_NEEDED')

    def test_direct_cnyes_only_fallback(self):
        (_, diagnostics), enrich = self.run_news([row('news.cnyes.com')])
        self.assertEqual(diagnostics['source_attempts']['CNYES']['status'], 'SUCCESS')
        self.assertTrue(diagnostics['retrieval']['fallback_used'])
        self.assertEqual(enrich.call_count, 1)

    def test_yahoo_exception_retained(self):
        (items, diagnostics), enrich = self.run_news([], error=YFDataException('synthetic'))
        self.assertEqual(items, [])
        self.assertEqual(diagnostics['news_status'], 'NEWS_UNAVAILABLE')
        self.assertEqual(diagnostics['source_attempts']['YAHOO_FINANCE']['status'], 'FAILED')
        self.assertEqual(diagnostics['source_attempts']['YAHOO_FINANCE']['error_type'], 'YFDataException')
        self.assertEqual(diagnostics['source_attempts']['CNYES']['status'], 'SOURCE_UNAVAILABLE')
        enrich.assert_not_called()

    def test_google_and_cnyes_search_excluded(self):
        google = row('news.google.com'); google['link'] = 'https://news.google.com/rss/articles/abc'
        (_, diagnostics), enrich = self.run_news([google, row('www.cnyes.com')])
        enrich.assert_not_called()
        self.assertEqual(diagnostics['news_status'], 'NEWS_UNAVAILABLE')
        self.assertEqual(diagnostics['source_attempts']['YAHOO_FINANCE']['excluded_source_count'], 2)

    def test_headlines_are_not_success(self):
        (_, diagnostics), _ = self.run_news([row('finance.yahoo.com')], usable=False)
        self.assertEqual(diagnostics['news_status'], 'NEWS_UNAVAILABLE')
        self.assertEqual(diagnostics['source_attempts']['YAHOO_FINANCE']['status'], 'NEWS_UNAVAILABLE')
