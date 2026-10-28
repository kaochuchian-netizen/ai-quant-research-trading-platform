"""Synthetic-only window/acquisition/admission/AI regressions. No live provider."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.research.tw_news_window import build_news_window, window_reason
from app.research.tw_news_aggregation import collect_tw_news, TwNewsAggregationSession, select_prompt_news_items
from app.research.tw_news_content_relevance import ArticleContent, collect_cnyes_time_window_results
from app.reports.tw_pre_open_quality import news_contract
from analysis.news_fetcher import fetch_stock_news
from analysis.news_analysis_engine import analyze_news
from analysis.gemini_client import GeminiClient

AS_OF = '2026-10-28T07:00:00+08:00'
BODY = '台積電 2330 公布營收成長，訂單擴產與財報展望。' * 12


def item(n=0, date='2026-10-27T15:00:00+08:00', symbol='2330', name='台積電'):
    return {'title': f'{name} {symbol} 營收訂單第{n}筆', 'link': f'https://news.cnyes.com/news/id/{9000000+n}',
            'published': date, 'source': '鉅亨網', 'content': BODY.replace('台積電',name).replace('2330',symbol), 'fetch_status': 'success'}


def aggregate(rows, symbol='2330', name='台積電', reference=AS_OF):
    return collect_tw_news(symbol,name,reference=reference,
        session=TwNewsAggregationSession(enable_cnyes=False),google_fetcher=lambda *_:rows)


class WindowTests(unittest.TestCase):
    def test_normal_weekend_long_holiday_and_year_boundary(self):
        for reference, previous in [('2026-10-28T07:00:00+08:00','2026-10-27'),
                ('2026-10-12T07:00:00+08:00','2026-10-08'),
                ('2026-10-11T07:00:00+08:00','2026-10-08')]:
            with self.subTest(reference=reference):
                w=build_news_window(reference)
                self.assertEqual(w['previous_completed_session'],previous)
                self.assertLessEqual(w['start'],w['previous_close'])
                self.assertEqual(window_reason(w['previous_close'],w),None)
    def test_year_boundary_requires_calendar_evidence(self):
        # Pinned calendar starts Jan 1; missing prior session must not be invented.
        with self.assertRaisesRegex(ValueError, 'NO_COMPLETED_SESSION'):
            build_news_window('2026-01-02T07:00:00+08:00')

    def test_aware_and_as_of_boundaries(self):
        w=build_news_window(AS_OF)
        self.assertEqual(window_reason('2026-10-28T00:00:01Z',w),'NEWS_AFTER_AS_OF')
        self.assertEqual(window_reason('2026-10-01T00:00:00Z',w),'NEWS_OUTSIDE_WINDOW')
        self.assertEqual(window_reason('2026-10-27',w),'NEWS_DATE_UNKNOWN')
        with self.assertRaises(ValueError):build_news_window('2026-10-28')
    def test_cnyes_weekend_in_unified_window(self):
        w=build_news_window('2026-10-12T07:00:00+08:00')
        rows=[{'title':'台積電營收', 'url':'https://news.cnyes.com/news/id/123',
               'published_at':'2026-10-10T12:00:00+08:00','content_status':'TITLE_ONLY'}]
        result=collect_cnyes_time_window_results([rows],symbol='2330',stock_name='台積電',reference=w['as_of'],news_window=w)
        self.assertEqual(result['within_window_results'],1)


class RssTests(unittest.TestCase):
    def test_rfc2822_local_normalization_preserves_original(self):
        raw='Tue, 27 Oct 2026 07:00:00 GMT'
        result=aggregate([item(date=raw)])
        self.assertEqual(result['items'][0]['published_at'],'2026-10-27T15:00:00+08:00')
        self.assertEqual(result['items'][0]['original_published_at'],raw)
        self.assertEqual(result['funnel']['admitted'],1)

    def test_all_candidates_not_first_five_and_disordered_dates(self):
        rows=[item(n) for n in range(12)]+[item(20,'2020-01-01T00:00:00+08:00')]
        feed=SimpleNamespace(entries=list(reversed(rows)))
        feed.get=lambda *_:False
        with patch('analysis.news_fetcher.requests.get',return_value=SimpleNamespace(content=b'x',raise_for_status=lambda:None)) as get, patch('analysis.news_fetcher.feedparser.parse',return_value=feed):
            found=fetch_stock_news('2330','台積電',window=build_news_window(AS_OF))
        self.assertEqual(len(found),13)
        self.assertIn('after%3A',get.call_args.args[0]);self.assertIn('before%3A',get.call_args.args[0])
        self.assertLessEqual(get.call_count,8)
        with patch('app.research.tw_news_content_relevance.fetch_article_content', return_value=ArticleContent('success',BODY)):
            result=aggregate(found)
        self.assertEqual(result['funnel']['in_window'],12)
        self.assertEqual(result['funnel']['admitted'],12)
        self.assertEqual(found.coverage['status'],'PARTIAL')
    def test_rss_provider_truncation_never_complete(self):
        rows=[item(n) for n in range(450)]
        feed=SimpleNamespace(entries=rows,get=lambda *_:False)
        with patch('analysis.news_fetcher.requests.get',return_value=SimpleNamespace(content=b'x',raise_for_status=lambda:None)),patch('analysis.news_fetcher.feedparser.parse',return_value=feed):
            result=fetch_stock_news('2330','台積電',window=build_news_window(AS_OF))
        self.assertEqual(len(result),400)
        self.assertIn('RSS_CANDIDATE_BUDGET',result.coverage['reason_codes'])
        self.assertEqual(result.coverage['status'],'PARTIAL')
    def test_transport_failure_explicit(self):
        import requests
        with patch('analysis.news_fetcher.requests.get',side_effect=requests.Timeout()):
            result=fetch_stock_news('2330','台積電',window=build_news_window(AS_OF))
        self.assertEqual(result.coverage['status'],'UNKNOWN')
        self.assertIn('RSS_TIMEOUT',result.coverage['reason_codes'])


class EvidenceTests(unittest.TestCase):
    def test_stage_counts_and_duplicates(self):
        rows=[item(n) for n in range(8)]+[item(0),item(20,'2020-01-01T00:00:00+08:00')]
        result=aggregate(rows);f=result['funnel']
        self.assertEqual(f,{'fetched':10,'in_window':9,'outside_window':1,'deduped':8,'duplicates':1,'relevant':8,'admitted':8,'analyzed':0})
        self.assertEqual(len(select_prompt_news_items(result['items'])),6)
    def test_no_evidence_does_not_call_ai(self):
        result=aggregate([item(0,'2020-01-01T00:00:00+08:00')])
        with patch('analysis.news_analysis_engine.collect_tw_news',return_value=result),patch('analysis.news_analysis_engine.generate_analysis') as ai:
            value=analyze_news('2330','台積電',include_evidence=True)
        ai.assert_not_called();self.assertEqual(value['ai_analysis']['reason_code'],'NO_ADMITTED_EVIDENCE')
    def test_2337_rejected_evidence_cannot_produce_summary(self):
        row=item(symbol='2337',name='旺宏');row.pop('content');row['fetch_status']='title_only'
        with patch('app.research.tw_news_content_relevance.fetch_article_content',return_value=ArticleContent('failed','',failure_reason='HTTP_403')):
            result=aggregate([row],symbol='2337',name='旺宏')
        with patch('analysis.news_analysis_engine.collect_tw_news',return_value=result),patch('analysis.news_analysis_engine.generate_analysis') as ai:
            value=analyze_news('2337','旺宏',include_evidence=True)
        ai.assert_not_called();self.assertEqual(value['funnel']['admitted'],0)
        formal=news_contract(value,generated_at=AS_OF,target_symbol='2337',target_name='旺宏')
        self.assertEqual(formal['evidence_funnel']['rejection_reasons'],{'ARTICLE_CONTENT_UNAVAILABLE':1})
        self.assertEqual(formal['evidence_funnel']['candidate_records'][0]['content_failure_reason'],'HTTP_403')
    def test_6873_five_synthetic_candidates_retained_not_fabricated(self):
        rows=[item(n, '2026-10-27T12:00:00+08:00' if n==0 else '2026-10-01T12:00:00+08:00','6873','泓德能源') for n in range(5)]
        result=aggregate(rows,'6873','泓德能源')
        self.assertEqual(len(result['items']),5);self.assertEqual(result['funnel']['admitted'],1)
        self.assertEqual(result['funnel']['outside_window'],4)
    def test_etf_specific_rejection(self):
        result=aggregate([item(symbol='00878',name='國泰永續高股息')],'00878','國泰永續高股息')
        self.assertEqual(result['funnel']['admitted'],0)
        self.assertEqual(result['items'][0]['relevance_materiality_evaluation']['rejection_reason'],'ETF_COMPANY_NEWS_NOT_APPLICABLE')
    def test_ai_budget_retains_unanalyzed(self):
        result=aggregate([item(n) for n in range(9)])
        with patch('analysis.news_analysis_engine.collect_tw_news',return_value=result),patch('analysis.news_analysis_engine.generate_analysis',return_value={'status':'SUCCESS','text':'已依新聞證據分析。'}) as ai:
            value=analyze_news('2330','台積電',include_evidence=True)
        self.assertEqual(value['funnel']['admitted'],9)
        self.assertEqual(value['funnel']['analyzed'],6)
        self.assertEqual(sum(i['analysis_status']=='ANALYSIS_BUDGET' for i in value['items']),3)
        self.assertTrue(ai.call_args.kwargs['structured'])
    def test_cross_day_window_rejected(self):
        with self.assertRaisesRegex(ValueError,'NEWS_WINDOW_BATCH_DATE_MISMATCH'):
            news_contract({'items':[item()], 'news_window':build_news_window(AS_OF)},
                          target_symbol='2330',generated_at='2026-10-29T07:00:00+08:00')

    def test_invalid_window_not_trusted(self):
        w=build_news_window(AS_OF);w['start']='2000-01-01T00:00:00+08:00'
        with self.assertRaisesRegex(ValueError,'NEWS_WINDOW_IDENTITY_MISMATCH'):
            news_contract({'items':[item()], 'news_window':w},target_symbol='2330',generated_at=AS_OF)


class AiTests(unittest.TestCase):
    def test_error_classes_no_provider_text_leak(self):
        for error, expected in [(TimeoutError('private deadline'),'TIMEOUT'),(RuntimeError('429 private'),'QUOTA'),
                                 (ConnectionError('private'),'TRANSPORT_ERROR'),(ValueError('private'),'PARSE_ERROR')]:
            client=object.__new__(GeminiClient);client.model_name='test';client.client=Mock()
            client.client.models.generate_content.side_effect=error
            result=client.generate('synthetic',structured=True)
            self.assertEqual(result['status'],expected);self.assertNotIn('private',json.dumps(result))
    def test_empty_response(self):
        client=object.__new__(GeminiClient);client.model_name='test';client.client=Mock()
        client.client.models.generate_content.return_value.text=None
        self.assertEqual(client.generate('test',structured=True)['status'],'PARSE_ERROR')


class RecoveryTests(unittest.TestCase):
    def test_browser_replacement_bounded(self):
        first=SimpleNamespace(fallback_reason='BROWSER_STAGE_TIMEOUT',close=Mock())
        replacement=SimpleNamespace(fallback_reason=None,close=Mock())
        session=TwNewsAggregationSession(browser=first,browser_factory=Mock(return_value=replacement))
        self.assertIs(session.get_browser(),replacement);first.close.assert_called_once()
        replacement.fallback_reason='BROWSER_STAGE_TIMEOUT'
        with self.assertRaises(Exception):session.get_browser()
        self.assertEqual(session.browser_factory.call_count,1)
    def test_content_budget_no_disappearing_candidates(self):
        from app.research.tw_news_content_relevance import enrich_news_items
        rows=[{**item(n),'content':'','fetch_status':'title_only'} for n in range(3)]
        with patch('app.research.tw_news_content_relevance.fetch_article_content',return_value=ArticleContent('success',BODY)) as fetch:
            result,_=enrich_news_items(rows,stock_id='2330',stock_name='台積電',max_fetches=1)
        self.assertEqual(len(result),3);self.assertEqual(fetch.call_count,1)
        self.assertEqual(result[1]['article_fetch']['failure_reason'],'CONTENT_BUDGET_EXHAUSTED')


class PresentationTests(unittest.TestCase):
    def test_safe_summary_and_collapsed_diagnostics(self):
        from app.reports.tw_pre_open_structured import build_card
        from app.reports.presentation_normalization import concise_news_summary
        from app.dashboard.multi_market_dashboard import _tw_pre_open_structured_card
        result=aggregate([item()])
        with patch('analysis.news_analysis_engine.collect_tw_news',return_value=result),patch('analysis.news_analysis_engine.generate_analysis',return_value={'status':'TIMEOUT','text':'','reason_code':'AI_TIMEOUT'}):
            bundle=analyze_news('2330','台積電',include_evidence=True)
        card=build_card(symbol='2330',name='台積電',trading_date='2026-10-28',news=bundle,generated_at=AS_OF)
        self.assertNotIn('analysis：',card['news_summary'])
        summary=concise_news_summary(card)
        self.assertIn('逾時',summary['reason']);self.assertNotIn('GOOGLE_NEWS_RSS',summary['reason'])
        html=_tw_pre_open_structured_card(card)
        self.assertIn('data-section="news-diagnostics"',html)
        self.assertNotIn('<details open',html)
        self.assertNotIn('analysis：',html)
        from app.reports.mobile_decision_presentation import project_card
        mobile=project_card(card,'TW','pre_open_0700')
        self.assertIn('逾時',str(mobile))
        self.assertNotIn('來源詳見研究證據',str(mobile))

    def test_ai_invalid_result_fail_closed(self):
        for malformed in ('unstructured', {}, {'status':'UNKNOWN'}, {'status':'SUCCESS','text':123}):
            with self.subTest(malformed=malformed), patch('analysis.news_analysis_engine.collect_tw_news',return_value=aggregate([item()])),patch('analysis.news_analysis_engine.generate_analysis',return_value=malformed):
                result=analyze_news('2330','台積電',include_evidence=True)
            self.assertEqual(result['ai_analysis']['status'],'PARSE_ERROR')
            self.assertEqual(result['funnel']['analyzed'],0)

    def test_open_article_timeout_fallback_retains_candidates(self):
        from scripts.orchestrator.validate_ai_dev_248_tw_news_aggregation_cnyes_delivery_integration_v1 import _Browser
        row={'title':'台積電 2330 營收成長','published_at':'2026-10-27T15:00:00+08:00',
             'url':'https://news.cnyes.com/news/id/9999999','content_status':'TITLE_ONLY'}
        browser=_Browser([[row]])
        def fail(_):
            browser.fallback_reason='BROWSER_STAGE_TIMEOUT'
            raise TimeoutError('synthetic')
        browser.open_article=fail
        with patch('app.research.tw_news_content_relevance.fetch_article_content',return_value=ArticleContent('success',BODY)) as fallback:
            result=collect_tw_news('2330','台積電',reference=AS_OF,session=TwNewsAggregationSession(browser_factory=lambda:browser),google_fetcher=lambda *_:[])
        self.assertEqual(result['source_health']['CNYES']['status'],'degraded')
        self.assertEqual(result['funnel']['admitted'],1)
        fallback.assert_called_once()
        self.assertEqual(result['retrieval']['coverage'],'PARTIAL')


if __name__ == '__main__':unittest.main()
