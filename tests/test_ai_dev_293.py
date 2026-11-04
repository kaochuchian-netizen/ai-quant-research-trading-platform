import unittest
from unittest.mock import patch
from app.loaders.batch_universe import normalize_rows, freeze, historical_universe, digest, complete_tw_identities
from app.evaluation.platform_quality import check_snapshot

class QualityRegression(unittest.TestCase):
    def test_sheet_aliases_disabled_and_provenance(self):
        from app.loaders.google_sheet_loader import _extract_tw_stock_ids
        symbols, _ = _extract_tw_stock_ids([['股票代號','stock_name','enabled'],['009816','基金甲','yes'],['2330','公司乙','no']])
        self.assertEqual(symbols,['009816'])
        self.assertEqual(symbols.entries[0]['name'],'基金甲')
        self.assertEqual(symbols.source_evidence['disabled_symbols'],['2330'])
        self.assertTrue(symbols.source_evidence['raw_rows_sha256'])
    def test_authoritative_identity_only_and_frozen_history(self):
        u=freeze(normalize_rows([{'symbol':'2330'}],'TW'),market='TW',batch_as_of='2026-11-02T07:00:00+08:00',source={})
        ignored=complete_tw_identities(u,lambda s:{'symbol':s,'name':'猜測名稱','source':'local_stock_name_map'})
        self.assertEqual(ignored['entries'][0]['name'],'')
        fixed=complete_tw_identities(u,lambda s:{'symbol':s,'name':'公司甲','source':'shioaji_contracts'})
        self.assertTrue(fixed['entries'][0]['identity_provenance'])
        snap={'market':'TW','effective_trading_date':'2026-11-02','payload':{'stock_universe_evidence':{'batch_universe':u},'structured_pre_open_cards':[{'stock_id':'2330','stock_name':'禁止回填'}]}}
        snap['snapshot_id']=digest(snap)
        self.assertEqual(historical_universe(snap)['entries'][0]['name'],'')
        self.assertEqual(check_snapshot(snap)['symbols'][0]['status'],'FAIL')
    def test_identity_failure_does_not_claim_network_attempt(self):
        from analysis.news_analysis_engine import analyze_news
        from app.reports.tw_prediction_explainability import finalized_tw_news_projection
        with patch('analysis.news_analysis_engine.collect_tw_news') as fetch:
            result=analyze_news('2330','display',include_evidence=True,company={'symbol':'2330'})
        fetch.assert_not_called()
        self.assertEqual(result['retrieval']['sources_attempted'],[])
        self.assertEqual(result['retrieval']['failure_reason'],'COMPANY_IDENTITY_UNRESOLVED_OR_AMBIGUOUS')
        self.assertEqual(finalized_tw_news_projection({'news_evidence':result})['state'],'RETRIEVAL_FAILED')
    def test_metadata_is_not_article(self):
        from app.research.tw_news_content_relevance import extract_article_text
        self.assertEqual(extract_article_text('<meta name="description" content="公司營收成長百分之百">'),'')
    def test_event_multiplier_applied_once(self):
        from app.us_stock.live_pipeline import prediction_for_symbol
        q={'last_price':100}; t={'ok':True,'indicators':{'atr_like_range_pct':.02},'trend_1m':'neutral'}
        r=prediction_for_symbol(q,t,'us_pre_market_2000',{'earnings':{'event_risk_level':'high'}})
        self.assertEqual(r['predicted_next_session_high'],102.78)
    def test_snapshot_tamper_fails_and_sent_is_not_receipt(self):
        snap={'snapshot_id':'tampered'}
        self.assertEqual(check_snapshot(snap)['status'],'FAIL')
    def test_old_and_future_article_rejected(self):
        from app.research.article_evidence import assess
        for date in ('2026-10-01T00:00:00Z','2026-11-03T00:00:00Z'):
            e=assess('Company revenue 100 million. Company earnings 20 million.',title='title',entry={'symbol':'NEW','name':'Company'},source_url='https://news.cnyes.com/news/id/1',published_at=date,fetched_at='2026-11-02T00:00:00Z',as_of='2026-11-02T00:00:00Z')
            self.assertFalse(e['investment_usable'])
    def test_explicit_article_rejection_survives_formal_contract(self):
        from app.reports.tw_pre_open_quality import news_contract
        item={'title':'台積電營收','source':'Reuters','published_at':'2026-11-02T06:00:00+08:00','source_url':'https://example.com/article','article_evidence':{'investment_usable':False,'reason':'HEADLINE_ONLY'}}
        result=news_contract({'items':[item]},generated_at='2026-11-02T07:00:00+08:00',target_symbol='2330',target_name='台積電')
        self.assertEqual(result['evidence'],[])
        self.assertEqual(result['evidence_funnel']['rejection_reasons']['HEADLINE_ONLY'],1)
    def test_browser_policy_denial_prevents_navigation(self):
        from app.research.cnyes_selenium_browser import CnyesSeleniumBrowser
        from unittest.mock import Mock
        driver=Mock()
        browser=CnyesSeleniumBrowser(driver,robots_guard=Mock(side_effect=ValueError('ROBOTS_DISALLOWED')))
        with self.assertRaises(ValueError): browser.open_article('https://news.cnyes.com/news/id/1')
        driver.get.assert_not_called()
    def test_tw_retains_masked_transport_receipt(self):
        import tempfile,json
        from pathlib import Path
        from app.reports.tw_pre_open_delivery_contract import _channel_delivery
        from tests.test_ai_dev_283 import inputs
        snapshot,_=inputs()
        evidence={'transport_result':'transport_accepted','recipients':[{'recipient_mask':'sha256:abc','status':'accepted'}]}
        with tempfile.TemporaryDirectory() as d:
            _channel_delivery('email',lambda s:{'send_attempted':True,'send_status':'sent','receipt':evidence},snapshot,Path(d))
            retained=json.loads(next(Path(d).glob('*.json')).read_text())
            self.assertEqual(retained['transport_receipt'],evidence)
