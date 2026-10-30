"""Dynamic universe/content gates; synthetic cases plus immutable historical facts."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from app.loaders.batch_universe import normalize_rows,freeze,validate,query,historical_universe,require_parity
from app.research.article_evidence import assess,ArticleRetriever,enrich
from app.research.news_evidence_funnel import normalize_yfinance_news
from app.us_stock.research_intelligence import USResearchIntelligenceBuilder
from app.us_stock.institutional_research import build_bundle
from app.us_stock.research_presentation import finalized_current_news_projection
from app.us_stock.premarket_decision import plan_gate_explanation,plan_reference_diagnostics
from tests.article_content_fixture import with_article

ASOF='2026-10-30T20:00:00+08:00'
def company(symbol='NEWC',name='New Company'):
 return {'symbol':symbol,'name':name,'market':'US','enabled':True,'aliases':[]}
def row(name='New Company',symbol='NEWC'):
 return {'title':name+' reports earnings for 2026','pubDate':'2026-10-30T10:00:00Z','publisher':'Synthetic Finance','link':'https://finance.yahoo.com/news/synthetic','relatedTickers':[symbol],'company_identity':company(symbol,name)}

class UniverseTests(unittest.TestCase):
 def test_dynamic_add_disable_remove_and_count(self):
  rows=[company(),company('NEXT','Next Company')]
  first=freeze(normalize_rows(rows,'US'),market='US',batch_as_of=ASOF,source={'kind':'sheet'})
  rows[0]['enabled']=False; rows.append(company('THIRD','Third Company'))
  second=freeze(normalize_rows(rows,'US'),market='US',batch_as_of=ASOF,source={'kind':'sheet'})
  self.assertEqual(first['symbols'],['NEWC','NEXT']); self.assertEqual(second['symbols'],['NEXT','THIRD'])
  removed=freeze(normalize_rows(rows[2:],'US'),market='US',batch_as_of=ASOF,source={'kind':'sheet'})
  self.assertEqual(len(removed['symbols']),1); self.assertEqual(first['symbols'],['NEWC','NEXT'])
 def test_invalid_market_enabled_symbol_and_conflicting_duplicate(self):
  for rows in [[{**company(),'market':'TW'}],[{**company(),'enabled':'perhaps'}],[{**company(),'symbol':'../bad'}],[company(),{**company(),'enabled':False}]]:
   with self.assertRaises(ValueError): normalize_rows(rows,'US')
 def test_tw_legacy_headers_and_disabled(self):
  from app.loaders.google_sheet_loader import _extract_tw_stock_ids,TWWatchlistSchemaError
  ids,_=_extract_tw_stock_ids([['stock_id','名稱','enabled','market'],['00878','ETF','1','TW'],['2330','公司','停用','TW']])
  self.assertEqual(ids,['00878']); self.assertEqual(ids.entries[0]['name'],'ETF')
  for value in ['unknown','2']:
   with self.assertRaises(TWWatchlistSchemaError): _extract_tw_stock_ids([['stock_id','enabled'],['2330',value]])
 def test_unavailable_sheet_never_uses_sample(self):
  from scripts.orchestrator.approved_us_stock_delivery import load_runtime_watchlist
  with patch('app.loaders.google_sheet_loader.load_us_stock_watchlist',side_effect=RuntimeError('source unavailable')):
   with self.assertRaises(RuntimeError): load_runtime_watchlist(False)
 def test_names_aliases_and_ambiguity(self):
  entries=normalize_rows([{**company(),'english_name':'New English','aliases':['New Alias'],'industry':'semiconductor'}],'US')
  q=query(entries[0]); self.assertIn('New Alias',q); self.assertIn('semiconductor',q)
  frozen=freeze([company('ONE','Same Company'),company('TWO','Same Company')],market='US',batch_as_of=ASOF,source={})
  with self.assertRaises(ValueError): query(frozen['entries'][0])
 def test_frozen_history_never_looks_up_current_sheet(self):
  snapshot={'snapshot_id':'immutable','market':'US','effective_trading_date':'2026-10-30','generated_at':ASOF,'payload':{'items':[{'symbol':'OLD'}]}}
  with patch('app.loaders.google_sheet_loader.load_us_stock_watchlist',side_effect=AssertionError('no live Sheet')):
   self.assertEqual(historical_universe(snapshot)['symbols'],['OLD'])
  frozen=historical_universe(snapshot); frozen['symbols']=['NEW']
  with self.assertRaises(ValueError): validate(frozen)
 def test_universe_parity_rejects_channel_subset(self):
  frozen=freeze([company(),company('NEXT','Next Company')],market='US',batch_as_of=ASOF,source={})
  require_parity(frozen,['NEWC','NEXT'])
  with self.assertRaises(ValueError): require_parity(frozen,['NEWC'])

class ContentTests(unittest.TestCase):
 def test_headline_only_discovered_not_investment_usable(self):
  raw=row(); a,d=normalize_yfinance_news([raw],symbol='NEWC',observed_at=ASOF)
  self.assertEqual(d['stages']['NEWS_ADMITTED'],1); self.assertEqual(d['stages']['INVESTMENT_USABLE'],0)
  material=USResearchIntelligenceBuilder.material_news(object.__new__(USResearchIntelligenceBuilder),'NEWC',a,d)
  self.assertEqual(material['items'],[])
  bundle=build_bundle('NEWC',{'material_news':material,'sec':{'ok':False}},{},ASOF)
  projection=finalized_current_news_projection(bundle)
  self.assertEqual(projection['selected_count'],0); self.assertEqual(projection['funnel']['stages']['RRE_USED'],0)
 def test_substantive_new_company_reaches_canonical_presentation(self):
  raw=with_article(row(),'New Company')
  a,d=normalize_yfinance_news([raw],symbol='NEWC',observed_at=ASOF)
  self.assertEqual(d['stages']['INVESTMENT_USABLE'],1)
  material=USResearchIntelligenceBuilder.material_news(object.__new__(USResearchIntelligenceBuilder),'NEWC',a,d)
  bundle=build_bundle('NEWC',{'material_news':material,'sec':{'ok':False}},{},ASOF)
  p=finalized_current_news_projection(bundle)
  self.assertEqual(p['selected_count'],1); self.assertEqual(p['primary_item']['direction_status'],'NOT_EVALUATED')
  self.assertTrue(p['primary_item']['chinese_summary']); self.assertTrue(p['primary_item']['article_evidence']['facts'])
 def test_content_fail_closed_matrix(self):
  for text,when in [('New Company earnings','2026-10-30T10:00:00Z'),('subscribe to continue reading','2026-10-30T10:00:00Z'),('Other Company revenue 20 billion. Other Company margin 12 percent.','2026-10-30T10:00:00Z'),('New Company may report revenue of 20 billion. New Company might report margin 20 percent.','2026-10-30T10:00:00Z'),('New Company revenue of 20 billion for the third quarter. New Company margin of 12 percent in the third quarter.','2026-10-30T13:00:00Z')]:
   evidence=assess(text,title='title',entry=company(),source_url='https://finance.yahoo.com/news/a',published_at=when,fetched_at=when,as_of=ASOF)
   self.assertFalse(evidence['investment_usable'])
 def test_historical_fetch_is_forbidden(self):
  retriever=Mock(); result=enrich([row()],entry=company(),as_of='2020-01-01T00:00:00Z',retriever=retriever)
  retriever.fetch.assert_not_called(); self.assertEqual(result[0]['article_evidence']['reason'],'HISTORICAL_CONTENT_REFETCH_FORBIDDEN')
 def test_ssrf_allowlist_redirect_and_robots(self):
  retriever=ArticleRetriever()
  for url in ['http://news.cnyes.com/news/1','https://127.0.0.1/x','https://finance.yahoo.com.evil.test/x','https://user:pass@news.cnyes.com/x']:
   with self.assertRaises(ValueError): retriever._get(url)
  with patch.object(retriever,'_get',return_value=(200,{},'User-agent: *\nDisallow: /')) as get:
   self.assertEqual(retriever.fetch('https://news.cnyes.com/news/id/1')['failure_reason'],'ROBOTS_DISALLOWED'); self.assertEqual(get.call_count,1)
 def test_provider_errors_and_redirect_private(self):
  for status in [403,429,500]:
   r=ArticleRetriever()
   with patch.object(r,'_get',side_effect=[(200,{},'User-agent: *\nAllow: /'),(status,{},'')]):
    self.assertEqual(r.fetch('https://news.cnyes.com/news/id/1')['failure_reason'],'HTTP_'+str(status))
  r=ArticleRetriever()
  with patch.object(r,'_get',side_effect=[(200,{},'User-agent: *\nAllow: /'),(302,{'location':'https://127.0.0.1/x'},'')]):
   self.assertTrue(r.fetch('https://news.cnyes.com/news/id/1')['failure_reason'])

class HistoricalPlanTests(unittest.TestCase):
 def test_all_original_gates_remain_and_no_fabricated_entry(self):
  path=Path(__file__).resolve().parents[1]/'docs/audits/ai-dev-292-historical-plan-evidence.json'
  history=json.loads(path.read_text())
  self.assertEqual(len(history['cards']),len(history['symbols']))
  for card in history['cards']:
   self.assertFalse(card['eligibility']['actionable']); self.assertIsNone(card['trade_plan']['entry'])
   self.assertIsNone(card['trade_plan']['stop']); self.assertIsNone(card['trade_plan']['target'])
   self.assertTrue(card['eligibility']['reason_codes']); self.assertIn('觀察區間不是正式進場',plan_gate_explanation(card))
 def test_price_basis_atr_gap_diagnostics_do_not_mutate(self):
  c={'eligibility':{'actionable':False,'reason_codes':['RR_BELOW_THRESHOLD']},'premarket':{'price':90,'previous_close':100,'gap_pct':-10}}
  before=copy.deepcopy(c); d=plan_reference_diagnostics(c,{'last_price':100,'last_price_source':'regular'}, {'indicators':{'atr_like_range_pct':0.03}},ASOF)
  self.assertEqual(d['atr_absolute_at_plan_basis'],3); self.assertEqual(c,before); self.assertFalse(d['risk_thresholds_changed'])


class IntegrationTests(unittest.TestCase):
 def test_false_bool_not_reenabled(self):
  from app.us_stock.watchlist import normalize_us_watchlist_rows
  self.assertFalse(normalize_us_watchlist_rows([dict(company(),enabled=False)])[0]['enabled'])
 def test_tw_ambiguous_company_never_calls_research(self):
  from analysis.news_analysis_engine import analyze_news
  with patch('analysis.news_analysis_engine.collect_tw_news') as collect, patch('analysis.news_analysis_engine.generate_analysis') as ai:
   result=analyze_news('2330','ambiguous',include_evidence=True,company={'symbol':'2330','name':'Same','ambiguous_aliases':['Same']})
  collect.assert_not_called();ai.assert_not_called();self.assertEqual(result['items'],[])
 def test_article_extraction_metadata_and_non_html(self):
  text='New Company reported revenue of 25 billion dollars in the third quarter. New Company reported margin of 12 percent in the third quarter.'
  html='<script type="application/ld+json">'+json.dumps({'@type':'NewsArticle','articleBody':text,'datePublished':'2026-10-30T10:00:00Z'})+'</script>'
  r=ArticleRetriever()
  with patch.object(r,'_get',side_effect=[(200,{},'User-agent: *\nAllow: /'),(200,{'Content-Type':'text/html'},html)]):
   result=r.fetch('https://news.cnyes.com/news/id/1')
  self.assertEqual(result['text'],text);self.assertEqual(result['published_at'],'2026-10-30T10:00:00Z')
  self.assertTrue(assess(text,title='earnings',entry=company(),source_url=result['source_url'],published_at=result['published_at'],fetched_at=result['fetched_at'],as_of=ASOF)['investment_usable'])
  r=ArticleRetriever()
  with patch.object(r,'_get',side_effect=[(200,{},'User-agent: *\nAllow: /'),(200,{'Content-Type':'image/png'},'x')]):
   self.assertEqual(r.fetch('https://news.cnyes.com/news/id/1')['failure_reason'],'NON_HTML_CONTENT')
 def test_unqualified_news_never_adjusts_prediction(self):
  from app.us_stock.live_pipeline import prediction_for_symbol
  quote={'last_price':100}; technical={'ok':True,'indicators':{'atr_like_range_pct':.02},'trend_1m':'neutral'}
  base=prediction_for_symbol(quote,technical,'us_pre_market_2000')
  for item in [{}, {'english_headline':'Huge earnings surprise'}, {'investment_usable':False}, {'investment_usable':True,'article_evidence':{'investment_usable':False}}]:
   self.assertEqual(base,prediction_for_symbol(quote,technical,'us_pre_market_2000',{'material_news':{'items':[item]}}))
  qualified={'investment_usable':True,'article_evidence':{'investment_usable':True}}
  self.assertTrue(prediction_for_symbol(quote,technical,'us_pre_market_2000',{'material_news':{'items':[qualified]}})['event_adjusted'])
 def test_snapshot_rejects_universe_drift_without_writes(self):
  from app.dashboard.window_snapshot_archive import write_snapshot
  u=freeze([company()],market='US',batch_as_of=ASOF,source={})
  with tempfile.TemporaryDirectory() as d:
   out=write_snapshot(Path(d),market='US',window='us_pre_market_2000',effective_trading_date='2026-10-30',generated_at=ASOF,source_payload={'batch_universe':u,'items':[{'symbol':'OTHER'}]},status='success')
   self.assertFalse(out['written']);self.assertEqual(list(Path(d).iterdir()),[])
 def test_historical_plan_reason_consistent_in_dashboard_email_line(self):
  from app.reports.mobile_decision_presentation import render_primary,render_line
  from scripts.orchestrator.approved_us_stock_delivery import _compact_us_email_block
  cards=json.loads((Path(__file__).resolve().parents[1]/'docs/audits/ai-dev-292-historical-plan-evidence.json').read_text())['cards']
  payload={'dashboard_ready_contract':{'cards':cards},'window':'us_pre_market_2000'}
  html=render_primary(payload,'US','us_pre_market_2000'); line=render_line(payload,'US','us_pre_market_2000','https://example.com')
  for card in cards:
   reason=plan_gate_explanation(card)
   self.assertIn(reason,html);self.assertIn(reason,line);self.assertIn(reason,_compact_us_email_block(card,'us_pre_market_2000'))
 def test_new_company_rss_and_cnyes_search_are_dynamic(self):
  from app.us_stock.news_rss_fallback import fetch_us_google_news_rss
  response=Mock(content=b'<rss><channel/></rss>')
  with patch('app.us_stock.news_rss_fallback.requests.get',return_value=response) as get:
   fetch_us_google_news_rss('NEWC',company(),source_domain='news.cnyes.com')
   search=get.call_args.kwargs['params']['q']
  self.assertIn('New Company',search);self.assertIn('NEWC',search);self.assertIn('site:news.cnyes.com',search)

if __name__=='__main__': unittest.main()
