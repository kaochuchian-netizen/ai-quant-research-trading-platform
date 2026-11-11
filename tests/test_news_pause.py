"""Pause is tested without the opt-in used by historical acquisition fixtures."""
import os
import unittest
from unittest.mock import Mock, PropertyMock, patch
from contextlib import ExitStack

from app.research.news_policy import news_fetch_enabled, paused_diagnostics

class NewsPauseTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))
        self.network = self.stack.enter_context(patch('requests.sessions.Session.request', side_effect=AssertionError('external request')))
        self.dns = self.stack.enter_context(patch('socket.getaddrinfo', side_effect=AssertionError('DNS request')))

    def tearDown(self):
        self.network.assert_not_called()
        self.dns.assert_not_called()

    def test_flag_default_and_invalid_fail_closed(self):
        self.assertFalse(news_fetch_enabled())
        for value in ('0', '', 'true', 'yes', 'invalid'):
            with patch.dict(os.environ, {'STOCK_AI_NEWS_FETCH_ENABLED': value}):
                self.assertFalse(news_fetch_enabled())
        with patch.dict(os.environ, {'STOCK_AI_NEWS_FETCH_ENABLED': '1'}):
            self.assertTrue(news_fetch_enabled())

    def test_us_does_not_access_ticker_news_and_preserves_prices(self):
        import pandas as pd
        from app.us_stock.live_data import YFinanceUSClient
        ticker = Mock()
        prop = PropertyMock(side_effect=AssertionError('ticker.news called'))
        type(ticker).news = prop
        ticker.fast_info = {'last_price': 402., 'previous_close': 400.}
        ticker.get_info.return_value = {}
        ticker.history.return_value = pd.DataFrame({'Close': [399., 402.]})
        client = YFinanceUSClient(); client._ticker_cache['TSLA'] = ticker
        result = client.fetch_symbol('TSLA', company={'symbol': 'TSLA', 'name': 'Tesla'})
        self.assertTrue(result.ok)
        self.assertEqual(result.quote['last_price'], 402.)
        self.assertEqual(result.news, [])
        self.assertEqual(result.news_diagnostics['absence_state'], 'NEWS_PAUSED')
        ticker.history.assert_called_once()
        prop.assert_not_called()

    def test_tw_no_search_browser_retry_or_ai_and_neutral_score(self):
        from analysis.news_analysis_engine import analyze_news
        from analysis.news_scoring_engine import calculate_news_score
        from app.research.tw_news_aggregation import TwNewsAggregationSession, collect_tw_news
        factory = Mock(side_effect=AssertionError('browser created'))
        session = TwNewsAggregationSession(browser_factory=factory)
        google = Mock(side_effect=AssertionError('search called'))
        with patch('analysis.news_analysis_engine.generate_analysis', side_effect=AssertionError('news AI')) as ai:
            result = analyze_news('2330', '台積電', include_evidence=True, aggregation_session=session)
            direct = collect_tw_news('2330', '台積電', session=session, google_fetcher=google)
        self.assertEqual(result['analysis'], '新聞功能暫停')
        self.assertEqual(direct['retrieval']['sources_attempted'], [])
        self.assertEqual(calculate_news_score(result['analysis'])['score'], 50)
        with self.assertRaisesRegex(ValueError, 'NEWS_PAUSED'): session.get_browser()
        self.assertEqual(session.recovery_attempts, 0)
        factory.assert_not_called(); google.assert_not_called(); ai.assert_not_called()

    def test_direct_rss_entrypoints_no_requests(self):
        from analysis.news_fetcher import fetch_stock_news
        from app.us_stock.news_rss_fallback import fetch_us_google_news_rss
        rows = fetch_stock_news('2330', '台積電')
        self.assertEqual(rows.coverage['request_count'], 0)
        self.assertEqual(fetch_us_google_news_rss('NVDA'), ([], 'NEWS_PAUSED'))

    def test_article_entrypoints_before_dns_and_cached_content(self):
        from app.research.article_evidence import ArticleRetriever
        from app.research.tw_news_content_relevance import fetch_article_content
        r = ArticleRetriever(); r.cache['https://finance.yahoo.com/a'] = {'text': 'old body'}
        self.assertEqual(r.fetch('https://finance.yahoo.com/a')['failure_reason'], 'NEWS_PAUSED')
        with self.assertRaisesRegex(ValueError, 'NEWS_PAUSED'): r._get('https://finance.yahoo.com/a')
        self.assertEqual(fetch_article_content('https://news.cnyes.com/news/id/1', session=Mock()).failure_reason, 'NEWS_PAUSED')
        self.assertEqual(r.remaining, 12)

    def test_direct_browser_entrypoints_block_navigation(self):
        from app.research.cnyes_selenium_browser import CnyesSeleniumBrowser, create_cnyes_selenium_browser
        from app.research.tw_news_content_relevance import collect_cnyes_browser_news
        browser = object.__new__(CnyesSeleniumBrowser); browser.driver = Mock()
        for action in (lambda: browser.open_search('https://www.cnyes.com/search/news'),
                       lambda: browser.open_article('https://news.cnyes.com/news/id/1'),
                       create_cnyes_selenium_browser,
                       lambda: collect_cnyes_browser_news(browser, symbol='2330', stock_name='台積電', reference='2026-11-11')):
            with self.assertRaisesRegex(ValueError, 'NEWS_PAUSED'): action()
        browser.driver.get.assert_not_called()

    def test_us_research_presentation_pause_label(self):
        from app.us_stock.research_intelligence import USResearchIntelligenceBuilder
        from app.us_stock.institutional_research import build_bundle
        from app.us_stock.research_presentation import finalized_current_news_projection
        material = USResearchIntelligenceBuilder.material_news(object.__new__(USResearchIntelligenceBuilder), 'TSLA', [], paused_diagnostics('US', 'TSLA'))
        bundle = build_bundle('TSLA', {'sec': {'ok': False}, 'material_news': material}, {}, '2026-11-11T20:00:00+08:00')
        projection = finalized_current_news_projection(bundle)
        self.assertEqual(projection['state'], 'NEWS_PAUSED')
        self.assertIn('新聞功能暫停', projection['compact_summary'])

    def test_tw_research_presentation_pause_label(self):
        from analysis.news_analysis_engine import analyze_news
        from app.reports.tw_pre_open_quality import news_contract
        from app.reports.tw_prediction_explainability import finalized_tw_news_projection
        from app.reports.tw_preopen_product_intelligence import _news_message
        raw = analyze_news('2330', '台積電', include_evidence=True)
        contract = news_contract(raw, generated_at='2026-11-11T07:00:00+08:00', target_symbol='2330', target_name='台積電')
        self.assertEqual(contract['absence_state'], 'NEWS_PAUSED')
        projected = finalized_tw_news_projection({'symbol': '2330', 'news_evidence': contract})
        self.assertEqual(projected['state'], 'NEWS_PAUSED')
        self.assertEqual(_news_message(projected, [], {'retrieved_count': 0}), '新聞功能暫停')
