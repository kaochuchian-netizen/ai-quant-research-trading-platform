"""Synthetic US fixtures only; no provider, credential, production or delivery."""
import unittest
from unittest.mock import patch
from app.research.news_evidence_funnel import normalize_yfinance_news, validate_funnel
from app.us_stock.news_window import news_window, in_window
from app.us_stock.research_intelligence import USResearchIntelligenceBuilder
from app.us_stock.research_intelligence_v2 import normalize_news
from app.us_stock.research_presentation import finalized_current_news_projection

from tests.article_content_fixture import with_article

ASOF='2026-10-28T20:00:00+08:00'
def raw(n=0,symbol='TSLA',name='Tesla',date='2026-10-28T10:00:00Z'):
    return with_article({'title':f'{name} {symbol} earnings outlook event {n}', 'publisher':'Synthetic Finance',
            'link':f'https://example.org/{symbol}/{n}', 'pubDate':date, 'relatedTickers':[symbol], 'contentType':'STORY'},name)
def pipeline(rows, symbol='TSLA', asof=ASOF):
    admitted, diag=normalize_yfinance_news(rows,symbol=symbol,observed_at=asof)
    material=USResearchIntelligenceBuilder.material_news(object.__new__(USResearchIntelligenceBuilder),symbol,admitted,diag)
    return admitted,diag,normalize_news(material['items'],asof,diag)

class WindowTests(unittest.TestCase):
    def test_weekend_holiday_and_dst(self):
        for instant,previous in [('2026-05-25T08:00:00-04:00','2026-05-22'),
                ('2026-03-08T08:00:00-04:00','2026-03-06'),('2026-11-01T08:00:00-05:00','2026-10-30'),
                ('2026-10-28T08:00:00-04:00','2026-10-27'),('2026-10-28T18:30:00-04:00','2026-10-28')]:
            with self.subTest(instant=instant):
                w=news_window(instant);self.assertEqual(w['previous_completed_session'],previous)
                self.assertTrue(in_window(w['previous_close'],w))
                self.assertFalse(in_window('2030-01-01T00:00:00Z',w))
    def test_long_weekend_prior_close_survives(self):
        asof='2026-12-28T08:00:00-05:00'
        w=news_window(asof)
        self.assertEqual(w['previous_completed_session'],'2026-12-24')
        rows=[raw(date='2026-12-24T19:00:00Z')]
        a,d,n=pipeline(rows,asof=asof)
        self.assertEqual(len(a),1);self.assertEqual(n['research_count'],1)
    def test_bad_time_fail_closed(self):
        for date in ('2026-10-28','2020-01-01T00:00:00Z','2026-10-29T00:00:00Z'):
            self.assertEqual(len(pipeline([raw(date=date)])[0]),0)
        self.assertEqual(len(pipeline([raw()],asof='2026-10-28')[0]),0)

class EvidenceTests(unittest.TestCase):
    def test_seventh_important_and_all_metadata_retained(self):
        a,d=normalize_yfinance_news([raw(i) for i in range(8)],symbol='TSLA',observed_at=ASOF)
        for x in a:x['materiality']='low'
        a[6]['materiality']='critical'
        m=USResearchIntelligenceBuilder.material_news(object.__new__(USResearchIntelligenceBuilder),'TSLA',a,d)
        n=normalize_news(m['items'],ASOF,d)
        self.assertEqual(len(m['items']),8);self.assertEqual(n['selected_items'][0]['candidate_id'],a[6]['candidate_id'])
        self.assertEqual(n['research_count'],8);self.assertEqual(n['selected_count'],2)
        self.assertTrue(all(x['selected_for_rre'] for x in n['items']))
        self.assertEqual(n['evidence_funnel']['stages']['RRE_USED'],8)
        self.assertEqual(n['evidence_funnel']['stages']['RENDERED'],2)
        self.assertEqual(validate_funnel(n['evidence_funnel']),[])
    def test_research_consumer_keeps_nonpresented_events(self):
        from app.us_stock.institutional_research import build_bundle
        a,d=normalize_yfinance_news([raw(i) for i in range(8)],symbol='TSLA',observed_at=ASOF)
        b=object.__new__(USResearchIntelligenceBuilder)
        m=b.material_news('TSLA',a,d)
        bundle=build_bundle('TSLA',{'sec':{'ok':False},'official_sources':{},'fundamentals':{},'earnings':{},'material_news':m},{},ASOF)
        self.assertEqual(len([x for x in bundle['evidence'] if x.get('provider_tier')=='C']),8)
        self.assertEqual(bundle['news_intelligence_v2']['selected_count'],2)
        self.assertEqual(bundle['news_intelligence_v2']['research_count'],8)
        self.assertEqual(bundle['research_intelligence_v2']['evidence_ownership']['directionless_news_contribution'],{'bullish':0,'bearish':0})

    def test_duplicate_other_symbol_and_counts(self):
        a,d,n=pipeline([raw(),raw(),raw(3,symbol='GOOGL',name='Alphabet')])
        self.assertEqual(len(a),1);self.assertEqual(d['stages']['RETRIEVED'],3)
        self.assertEqual(sum(x['admission_status']=='ADMITTED' for x in d['candidate_records']),1)
        self.assertEqual(n['research_count'],1)
    def test_symbols_and_no_direction_invention(self):
        for sym,name in [('TSLA','Tesla'),('GOOGL','Alphabet'),('SPCX','SpaceX')]:
            a,d,n=pipeline([raw(symbol=sym,name=name)],symbol=sym)
            self.assertEqual(len(a),1)
            self.assertEqual(n['directional_contribution'],{'bullish':0,'bearish':0})
            self.assertEqual(n['selected_items'][0]['direction'],'unavailable')
    def test_partial_unknown_failure_and_truncation(self):
        for rows,error,coverage in [([raw()],None,'PARTIAL'),([],None,'UNKNOWN'),([], 'TimeoutError','UNKNOWN')]:
            a,d=normalize_yfinance_news(rows,symbol='TSLA',observed_at=ASOF,retrieval_error=error)
            self.assertEqual(d['coverage']['status'],coverage)
            self.assertNotEqual(d['coverage']['status'],'COMPLETE')
            self.assertIn('COMPANY_IR_NOT_FETCHED',d['coverage']['source_gaps'])
        a,d,n=pipeline([raw(i) for i in range(80)])
        self.assertEqual(len(d['candidate_records']),80);self.assertFalse(d['candidate_retention']['truncated'])
        self.assertEqual(n['research_count'],80);self.assertEqual(n['selected_count'],2)
    def test_ir_registry_is_not_fetch(self):
        b=object.__new__(USResearchIntelligenceBuilder)
        for symbol in ('TSLA','SPCX','GOOGL'):
            r=b.official_sources(symbol,{})
            self.assertEqual(r['retrieval_status'],'NOT_FETCHED');self.assertEqual(r['coverage'],'UNKNOWN')
    def test_identity_and_window_mismatch(self):
        a,d,n=pipeline([raw()]);d['candidate_records'][0]['admission_status']='REJECTED'
        self.assertEqual(normalize_news(a,ASOF,d)['research_count'],0)
        d['window']['start']='2020-01-01T00:00:00Z'
        self.assertEqual(normalize_news(a,ASOF,d)['research_count'],0)
    def test_line_size_independent_of_metadata_count(self):
        from app.us_stock.institutional_research import build_bundle
        from scripts.orchestrator.approved_us_stock_delivery import line_text
        outputs=[]
        for count in (8,80):
            a,d=normalize_yfinance_news([raw(i) for i in range(count)],symbol='TSLA',observed_at=ASOF)
            m=USResearchIntelligenceBuilder.material_news(object.__new__(USResearchIntelligenceBuilder),'TSLA',a,d)
            b=build_bundle('TSLA',{'sec':{'ok':False},'material_news':m},{},ASOF)
            card={'symbol':'TSLA','institutional_research':b}
            outputs.append(line_text({'dashboard_ready_contract':{'cards':[card]}},'us_pre_market_2000'))
        self.assertLess(abs(len(outputs[1])-len(outputs[0])),100)
        self.assertIn('TSLA',outputs[0])

    def test_display_is_bounded_and_coverage_visible(self):
        a,d,n=pipeline([raw(i) for i in range(8)])
        p=finalized_current_news_projection({'news_intelligence_v2':n})
        self.assertEqual(p['selected_count'],2);self.assertEqual(p['coverage_status'],'PARTIAL')
        self.assertNotIn('NOT_EVALUATED',p['compact_summary'])
        self.assertNotIn('tier_3',p['compact_summary'])

if __name__=='__main__':unittest.main()
