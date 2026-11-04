"""Synthetic fault regressions; never represented as live source acceptance."""
from copy import deepcopy
from datetime import datetime
import unittest
from unittest.mock import patch, Mock

from app.prediction.technical_first import KEY, technical_base, news_adjustment, final_decision, status_text
from app.prediction.technical_first_adapters import us_base, apply_us
from app.research.article_evidence import assess
from app.evaluation.technical_ablation import evaluate, holdout

ASOF = '2026-11-02T20:00:00+08:00'
ENTRY = {'symbol': 'EXAM', 'name': 'Example Company', 'market': 'US'}


def inputs():
    quote = {'last_price':100, 'previous_close':99, 'market_data_as_of':'2026-10-30T16:00:00-04:00',
             'pre_market_price':100, 'pre_market_time':ASOF, 'market_data_source':'Synthetic OHLCV'}
    technical = {'ok':True, 'data_quality':{'history_days':60}, 'technical_score':70,
                 'trend_1m':'bullish', 'trend_3m':'bullish', 'volatility_state':'low',
                 'indicators':{'ma20':98, 'rsi14':55, 'macd_histogram':1, 'atr_like_range_pct':.02, 'latest_close':100}}
    return quote, technical


def base():
    q,t=inputs()
    return us_base(ENTRY,q,t,{},'us_pre_market_2000',ASOF)[0]


def article():
    text = ('Example Company reported revenue of 25 billion dollars in the third quarter of 2026. '
            'Example Company reported earnings of 2 billion dollars for the third quarter of 2026.')
    ev=assess(text,title='Example results',entry=ENTRY,source_url='https://finance.yahoo.com/news/example',
              published_at='2026-11-02T10:00:00Z', fetched_at='2026-11-02T11:00:00Z',as_of=ASOF)
    return {'article_evidence':ev,'company_identity':ENTRY,'candidate_id':'synthetic-example'}


class TechnicalFirstTests(unittest.TestCase):
    def test_four_scenarios_preserve_base_and_confidence(self):
        b=base(); before=deepcopy(b)
        cases=[([],{'status':'SUCCESS'},'TECHNICAL_ONLY','NO_RELEVANT_NEWS'),
               ([],{'status':'FAILED'},'TECHNICAL_ONLY','UNAVAILABLE'),
               ([article()],{'status':'SUCCESS'},'TECHNICAL_PLUS_NEWS','AVAILABLE')]
        for news, diag, mode, status in cases:
            d=final_decision(b,news_adjustment(entry=ENTRY,as_of=ASOF,items=news,retrieval=diag))
            self.assertEqual(d['final_decision']['mode'],mode)
            self.assertEqual(d['final_decision']['news_status'],status)
            self.assertEqual(d['final_decision']['prediction'],b['prediction'])
            self.assertEqual(d['final_decision']['confidence'],b['confidence'])
            self.assertEqual(d['technical_base'],before)
            self.assertTrue(d['final_decision']['technical_research_usable'])
        q,t=inputs(); t['ok']=False; t['data_quality']['history_days']=0
        blocked=us_base(ENTRY,q,t,{},'us_pre_market_2000',ASOF)[0]
        d=final_decision(blocked,news_adjustment(entry=ENTRY,as_of=ASOF,items=[article()]))
        self.assertEqual(d['final_decision']['mode'],'DATA_BLOCKED')
        self.assertIsNone(d['final_decision']['trade_plan']['entry'])
        self.assertFalse(d['final_decision']['combined_research_usable'])

    def test_no_news_is_not_low_risk_or_reduced_confidence(self):
        d=final_decision(base(),news_adjustment(entry=ENTRY,as_of=ASOF,items=[]))
        self.assertEqual(d['final_decision']['event_risk'],'UNKNOWN')
        self.assertEqual(d['final_decision']['confidence'],d['technical_base']['confidence'])
        self.assertFalse(d['final_decision']['news_evidence_usable'])

    def test_valid_event_can_veto_never_create_or_increase(self):
        a=article();a['event_risk']='high';b=base()
        d=final_decision(b,news_adjustment(entry=ENTRY,as_of=ASOF,items=[a]))
        self.assertFalse(d['final_decision']['eligibility']['actionable'])
        self.assertIn('EVENT_RISK_HIGH',d['final_decision']['eligibility']['reason_codes'])
        self.assertEqual(b,d['technical_base'])
        self.assertEqual(d['final_decision']['confidence'],b['confidence'])

    def test_headline_wrong_company_stale_future_rejected(self):
        for kind in ('headline','company','old','future','modified','facts'):
            a=article()
            if kind=='headline': a['article_evidence']['article_content_status']='HEADLINE_ONLY'
            if kind=='company': a['company_identity']={'symbol':'OTHER'}
            if kind=='old': a['article_evidence']['published_at']='2026-10-01T00:00:00Z'
            if kind=='future': a['article_evidence']['published_at']='2026-11-03T00:00:00Z'
            if kind=='modified': a['article_evidence']['modified_at']='2026-11-03T00:00:00Z'
            if kind=='facts': a['article_evidence']['facts']=[{'text':'Other Company revenue 25 billion.'}]*2
            d=final_decision(base(),news_adjustment(entry=ENTRY,as_of=ASOF,items=[a],retrieval={'status':'SUCCESS'}))
            self.assertEqual(d['final_decision']['mode'],'TECHNICAL_ONLY',kind)
            self.assertTrue(d['news_adjustment']['rejected'])

    def test_stale_nan_future_or_unknown_price_time_blocks(self):
        for timestamp in ('2026-10-01T00:00:00Z', '2026-11-03T00:00:00Z',None):
            q,t=inputs();q['market_data_as_of']=timestamp
            b=us_base(ENTRY,q,t,{},'us_pre_market_2000',ASOF)[0]
            self.assertEqual(b['status'],'DATA_BLOCKED')
            self.assertIsNone(b['trade_plan']['entry'])
        b=base(); b['confidence']=99
        with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):
            final_decision(b,news_adjustment(entry=ENTRY,as_of=ASOF,items=[]))

    def test_news_exception_does_not_erase_prices(self):
        import pandas as pd
        from app.us_stock.live_data import YFinanceUSClient
        client=YFinanceUSClient(); ticker=Mock()
        ticker.fast_info={'last_price':100};ticker.get_info.return_value={}
        ticker.history.return_value=pd.DataFrame({'Close':[100]})
        with patch.object(client,'_ticker',return_value=ticker), patch.object(client,'_fetch_news',side_effect=RuntimeError('synthetic')):
            result=client.fetch_symbol('EXAM',company=ENTRY)
        self.assertTrue(result.ok);self.assertEqual(result.quote['last_price'],100)
        self.assertEqual(result.news,[]);self.assertTrue(result.news_diagnostics['price_data_preserved'])

    def test_native_us_runtime_survives_optional_research_failure(self):
        import pandas as pd
        from app.us_stock.live_data import FetchResult
        from app.us_stock.live_pipeline import build_live_runtime_artifact
        q,t=inputs()
        with patch('app.us_stock.live_pipeline.YFinanceUSClient') as client, patch('app.us_stock.live_pipeline.analyze_history',return_value=t), patch('app.us_stock.live_pipeline.USResearchIntelligenceBuilder') as research:
            client.return_value.fetch_context.return_value={}
            client.return_value.fetch_symbol.return_value=FetchResult('EXAM',True,q,pd.DataFrame({'Close':[100]}),[],{'retrieval':{'status':'FAILED'}},None)
            research.return_value.build_for_symbol.side_effect=RuntimeError('synthetic research failure')
            p=build_live_runtime_artifact('us_pre_market_2000',[ENTRY],production_runtime=False,write_snapshots=False,reference=datetime.fromisoformat(ASOF))
        d=p['items'][0][KEY]
        self.assertEqual(d['final_decision']['mode'],'TECHNICAL_ONLY')
        self.assertEqual(d,p['dashboard_ready_contract']['cards'][0][KEY])

    def test_preview_three_channels_share_status(self):
        from app.reports.mobile_decision_presentation import render_primary, render_line
        from scripts.orchestrator.approved_us_stock_delivery import build_email_body
        d=final_decision(base(),news_adjustment(entry=ENTRY,as_of=ASOF,items=[],retrieval={'status':'FAILED'}))
        card=apply_us({'symbol':'EXAM','name':'Example Company'},d)
        p={'market':'US','window':'us_pre_market_2000','effective_trading_date':'2026-11-02','dashboard_ready_contract':{'cards':[card]}}
        status=status_text(card)
        for text in (render_primary(p,'US','us_pre_market_2000'),render_line(p,'US','us_pre_market_2000','https://example.test'),build_email_body(p,'us_pre_market_2000')):
            self.assertIn(status,text)
        from app.reports.mobile_decision_presentation import _post_close_compact_line
        self.assertIn(status,_post_close_compact_line(card,'TW','post_close_1500'))

    def test_native_pipeline_four_scenarios_no_send(self):
        import pandas as pd
        from app.us_stock.live_data import FetchResult
        from app.us_stock.live_pipeline import build_live_runtime_artifact
        from app.reports.mobile_decision_presentation import render_primary, render_line
        from scripts.orchestrator.approved_us_stock_delivery import build_email_body
        a=article();a.update(title='Example Company quarterly results',source_url='https://finance.yahoo.com/news/example',published_at='2026-11-02T10:00:00Z')
        for kind,news,diagnostics,mode in (
            ('valid_news',[a],{'status':'SUCCESS'},'TECHNICAL_PLUS_NEWS'),
            ('no_news',[],{'status':'SUCCESS'},'TECHNICAL_ONLY'),
            ('news_failure',[],{'status':'FAILED'},'TECHNICAL_ONLY'),
            ('price_failure',[],{'status':'SUCCESS'},'DATA_BLOCKED')):
            with self.subTest(kind=kind):
                q,t=inputs()
                if kind=='price_failure': q['market_data_as_of']='2026-10-01T00:00:00Z'
                with patch('app.us_stock.live_pipeline.YFinanceUSClient') as client, patch('app.us_stock.live_pipeline.analyze_history',return_value=t), patch('app.us_stock.live_pipeline.USResearchIntelligenceBuilder') as research, patch('app.us_stock.live_pipeline.write_json') as writer:
                    client.return_value.fetch_context.return_value={}
                    client.return_value.fetch_symbol.return_value=FetchResult('EXAM',True,q,pd.DataFrame({'Close':[100]}),news,diagnostics,None)
                    research.return_value.build_for_symbol.return_value={}
                    p=build_live_runtime_artifact('us_pre_market_2000',[ENTRY],production_runtime=False,write_snapshots=False,reference=datetime.fromisoformat(ASOF))
                    writer.assert_not_called()
                card=p['dashboard_ready_contract']['cards'][0]
                self.assertEqual(card[KEY]['final_decision']['mode'],mode)
                for text in (render_primary(p,'US','us_pre_market_2000'),render_line(p,'US','us_pre_market_2000','https://preview.invalid'),build_email_body(p,'us_pre_market_2000')):
                    self.assertIn(status_text(card),text)

    def test_ablation_never_backfills_or_uses_early_outcome(self):
        self.assertEqual(evaluate(None,{})['reason'],'NO_FROZEN_TECHNICAL_NEWS_SPLIT')
        d=final_decision(base(),news_adjustment(entry=ENTRY,as_of=ASOF,items=[]))
        out={'market':'US','symbol':'EXAM','session_date':'2026-11-02','high':102,'low':99,'close':101,'complete':True,'source_ref':'synthetic',
             'session_open':'2026-11-02T14:30:00Z','session_close':'2026-11-02T21:00:00Z','observed_at':'2026-11-02T21:01:00Z'}
        row=evaluate(d,out);self.assertEqual(row['status'],'EVALUATED');self.assertEqual(row['news_adjustment_gain'],0)
        self.assertIsNone(row['technical_performance']['direction_correct'])
        wrong=deepcopy(out);wrong['session_date']='2026-11-03'
        self.assertEqual(evaluate(d,wrong)['status'],'UNKNOWN')
        out['observed_at']=ASOF;self.assertEqual(evaluate(d,out)['status'],'UNKNOWN')
        self.assertEqual(holdout([(d,out)],'2026-11-03T00:00:00Z')['paired_samples'],0)

    def test_ablation_requires_intact_admitted_origin(self):
        import tempfile, json
        from pathlib import Path
        from app.loaders.batch_universe import digest
        from app.evaluation.technical_ablation import immutable_us_decision
        d=final_decision(base(),news_adjustment(entry=ENTRY,as_of=ASOF,items=[]))
        wrapper={'market':'us','window':'us_pre_market_2000','effective_trading_date':'2026-11-02',
                 'admitted':True,'payload':{'dashboard_ready_contract':{'cards':[{'symbol':'EXAM',KEY:d}]}}}
        wrapper['snapshot_id']=digest(wrapper)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'revision-0001.json';path.write_text(json.dumps(wrapper))
            source={'source_path':str(path),'source_snapshot_id':wrapper['snapshot_id'],
                    'source_effective_date':'2026-11-02','symbol':'EXAM'}
            self.assertEqual(immutable_us_decision(source,tmp),d)
            wrapper['admitted']=False;path.write_text(json.dumps(wrapper))
            self.assertIsNone(immutable_us_decision(source,tmp))
            self.assertIsNone(immutable_us_decision(source,Path(tmp)/'other'))

    def test_later_observation_does_not_replace_origin_plan(self):
        from app.prediction.technical_first_adapters import observe_us
        d=final_decision(base(),news_adjustment(entry=ENTRY,as_of=ASOF,items=[]))
        plan={'status':'active','entry':{'low':99,'high':100},'stop':98,'target':104}
        card={'trade_plan':deepcopy(plan),'eligibility':{'actionable':True}}
        with patch('app.evaluation.technical_ablation.immutable_us_decision',return_value=d):
            observe_us(card,d,{},'.')
        self.assertEqual(card['trade_plan'],plan)
        self.assertTrue(card['eligibility']['actionable'])
        self.assertEqual(card[KEY],d)

    def test_market_confidence_and_learning_split(self):
        from app.reports.tw_pre_open_structured import _market_bias, _coverage
        from app.evaluation.daily_learning import derive
        d=final_decision(base(),news_adjustment(entry=ENTRY,as_of=ASOF,items=[]))
        card={KEY:d,'news_status':'unavailable'}
        score=_market_bias(_coverage([card]),[card])['market_confidence']['score']
        card.update(news_status='available',news_direction='bullish',news_summary='qualifying event')
        self.assertEqual(score,_market_bias(_coverage([card]),[card])['market_confidence']['score'])
        row={'status':'EVALUATED','news_adjustment_gain':0}
        learning=derive('2026-11-03',{'US':{'review_evidence':[{'cards':[{'review':{'technical_news_ablation_v1':row}}]}]}})
        self.assertEqual(learning['markets']['US']['technical_news_ablation_v1']['paired_samples'],1)
        self.assertEqual(learning['markets']['TW']['technical_news_ablation_v1']['status'],'UNKNOWN')

    def test_candidate_stage_evidence_survives_metadata_rejection(self):
        from app.research.news_evidence_funnel import normalize_yfinance_news
        ev={'investment_usable':False,'article_content_status':'FAILED','reason':'ROBOTS_DISALLOWED'}
        _,f=normalize_yfinance_news([{'title':'Other Company revenue','pubDate':ASOF,'link':'https://example.test/a','article_evidence':ev}],symbol='EXAM',observed_at=ASOF)
        self.assertEqual(f['candidate_records'][0]['article_evidence'],ev)

    def test_tw_native_card_and_stale_price_gate(self):
        import pandas as pd
        from app.strategy.tw_daily_tactical import technical_factors, build_tactical
        from app.reports.tw_pre_open_structured import build_card
        rows=[{'date':str(d.date()),'open':100+i/10,'close':100+i/10,'high':102+i/10,'low':98+i/10,'volume':1000+i}
              for i,d in enumerate(pd.bdate_range(end='2026-10-30',periods=65))]
        factors=technical_factors(rows)
        tactical=build_tactical({'symbol':'9101','name':'Example Company'},factors,{})
        tactical['generated_at']=ASOF
        cards=[]
        for news in ({'items':[],'retrieval':{'status':'SUCCESS'}},{'items':[],'retrieval':{'status':'FAILED','failure_reason':'TIMEOUT'}}):
            card=build_card(symbol='9101',name='Example Company',trading_date='2026-11-02',
                            indicator={'close':106,'date':'2026-10-30'},tactical=tactical,news=news,generated_at=ASOF)
            self.assertEqual(card[KEY]['final_decision']['mode'],'TECHNICAL_ONLY')
            cards.append(card)
        self.assertEqual(cards[0][KEY]['technical_base'],cards[1][KEY]['technical_base'])
        tactical['technical_factors']['history_end']='2026-10-01'
        card=build_card(symbol='9101',name='Example Company',trading_date='2026-11-02',indicator={'close':106,'date':'2026-10-01'},tactical=tactical,generated_at=ASOF)
        self.assertEqual(card[KEY]['final_decision']['mode'],'DATA_BLOCKED')
        self.assertFalse(card['actionable']);self.assertIsNone(card['entry_zone'])

    def test_body_budget_not_spent_on_metadata_rejections(self):
        from app.research.article_evidence import enrich_us_candidates
        retriever=Mock()
        rows=enrich_us_candidates([{'title':'Unrelated weather','pubDate':ASOF,'link':'https://finance.yahoo.com/news/weather'}],entry=ENTRY,as_of=ASOF,retriever=retriever)
        retriever.fetch.assert_not_called()
        self.assertEqual(rows[0]['article_stages']['fetch']['status'],'NOT_ATTEMPTED')

    def test_coverage_scope_exception_rejects_any_risk_change(self):
        from pathlib import Path
        from scripts.orchestrator.validate_ai_dev_226_tw_four_window_summary_regression_ledger_v1 import technical_coverage_only
        head=(Path(__file__).resolve().parents[1]/'app/strategy/tw_daily_tactical.py').read_text()
        base=head.replace('    technical_coverage = {k: v for k, v in coverage.items() if k != "event_news"}\n','').replace('technical_coverage.values()','coverage.values()')
        self.assertTrue(technical_coverage_only(base,head))
        self.assertFalse(technical_coverage_only(base,head.replace('partial <= 2','partial <= 99')))
        self.assertFalse(technical_coverage_only(base,head.replace('days >= 20','days >= 1')))

    def test_new_status_mobile_viewport(self):
        from playwright.sync_api import sync_playwright
        from app.reports.mobile_decision_presentation import render_primary
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':393,'height':852})
                page.route('**/*',lambda route:route.abort())
                for kind in ('no_news','valid_news','price_failure'):
                    q,t=inputs()
                    if kind=='price_failure': q['market_data_as_of']='2026-10-01T00:00:00Z'
                    b=us_base(ENTRY,q,t,{},'us_pre_market_2000',ASOF)[0]
                    d=final_decision(b,news_adjustment(entry=ENTRY,as_of=ASOF,items=[article()] if kind=='valid_news' else [],retrieval={'status':'SUCCESS'}))
                    card=apply_us({'symbol':'EXAM','name':'Example Company'},d)
                    payload={'dashboard_ready_contract':{'cards':[card]}}
                    page.set_content(render_primary(payload,'US','us_pre_market_2000'))
                    self.assertIn(status_text(card),page.locator('body').inner_text())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),393)
                    self.assertEqual(page.locator('dt',has_text='技術與新聞').count(),1)
            finally:
                browser.close()

if __name__=='__main__': unittest.main()
