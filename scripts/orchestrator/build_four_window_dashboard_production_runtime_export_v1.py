#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'templates/four_window_dashboard_production_runtime_export.example.json'
INP=ROOT/'templates/four_window_dashboard_production_runtime_export_input.example.json'
PUBLIC_URL='http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html'
TAIPEI=ZoneInfo('Asia/Taipei')
NOW=datetime(2026,7,6,0,22,0,tzinfo=TAIPEI)
SQLITE_URI='file:data/stock_analysis.db?mode=ro'
ALLOWED=('templates/','docs/','orchestrator/templates/','orchestrator/queue/','/var/www/stock-ai-dashboard/.ai_dev_145_publish_results/latest.json','/home/kaochuchian/dify/docker/volumes/certbot/www/stock-ai-dashboard/.ai_dev_145_publish_results','/home/kaochuchian/dify/docker/volumes/certbot/www/stock-ai-dashboard/.ai_dev_145_publish_results/','/home/kaochuchian/.local/state/stock-ai-orchestrator/','data/stock_analysis.db')
CANDIDATES=[ROOT/p for p in ['templates/daily_report_forecast_v1_result.example.json','templates/daily_report_renderer_result.example.json','templates/daily_report_intelligence_integration_result.example.json','templates/daily_report_dashboard_preview_feed_result.example.json','templates/prediction_quality_review_result.example.json','templates/daily_forecast_review_result.example.json','templates/decision_quality_feedback_artifact.example.json','templates/context_based_report_assembly_artifact.example.json','templates/dashboard_decision_intelligence_artifact.example.json','templates/official_primary_source_context_admission_artifact.example.json','templates/four_window_dashboard_runtime_data.example.json']]+[Path('/var/www/stock-ai-dashboard/.ai_dev_145_publish_results/latest.json')]
SECRET=[re.compile(p,re.I) for p in (r'ghp_',r'github_pat_',r'sk-[A-Za-z0-9_-]{16,}',r'Bearer\s+[A-Za-z0-9._~+/=-]{16,}',r'BEGIN (RSA|OPENSSH) PRIVATE KEY',r'api[_-]?key\s*[:=]',r'access[_-]?token\s*[:=]',r'password\s*[:=]')]
FRESH={'pre_open_0700':18,'intraday_1305':4,'pre_close_1335':4,'post_close_1500':36,'stock_universe':168,'latest_report':36,'per_stock_summary':36,'prediction_fields':36,'actual_outcome_fields':36,'prediction_review_fields':36}
WINDOWS=[('pre_open_0700','07:00','盤前預測 / Pre-open Forecast',['market_context','prediction_range','risk_notes','source_quality']),('intraday_1305','13:05','盤中追蹤 / Intraday Tracking',['intraday_status','price_vs_range','volume_chip_context','invalidation_notes']),('pre_close_1335','13:35','收盤快照 / Close Snapshot',['actual_high_low','close_price','initial_hit_status','pending_full_review']),('post_close_1500','15:00','盤後檢討 / Prediction Review',['forecast_vs_actual','hit_metrics','error_sources','decision_quality_feedback'])]
def stable(x:Any)->str: return json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
def rel(p:Path)->str:
    try: return str(p.resolve().relative_to(ROOT))
    except ValueError: return str(p.resolve())
def allowed(s:str)->bool: return any(s==a or s.startswith(a) for a in ALLOWED)
def hits_text(txt:str)->list[str]: return [p.pattern for p in SECRET if p.search(txt)]
def hits_path(p:Path)->list[str]:
    try: return hits_text(p.read_text(encoding='utf-8',errors='ignore')[:300000])
    except OSError: return []
def load_json(p:Path):
    try:
        txt=p.read_text(encoding='utf-8')
        return None if hits_text(txt[:300000]) else json.loads(txt)
    except Exception: return None
def parse_dt(v):
    if not v: return None
    try:
        d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
        if d.tzinfo is None: d=d.replace(tzinfo=TAIPEI)
        return d.astimezone(TAIPEI)
    except ValueError: return None
def fresh(ts,maxh,always=False):
    if always: return {'status':'always_current','label':'政策資料','timestamp':ts,'max_age_hours':maxh}
    d=parse_dt(ts)
    if not d: return {'status':'missing','label':'資料待接','timestamp':ts,'max_age_hours':maxh}
    age=(NOW-d).total_seconds()/3600; st='fresh' if age<=maxh else 'stale'
    return {'status':st,'label':'資料正常' if st=='fresh' else '資料過期','timestamp':d.isoformat(),'age_hours':round(age,2),'max_age_hours':maxh}
def find_ts(x):
    if isinstance(x,dict):
        for k in ('generated_at','generated_timestamp','report_date','review_date','created_at','updated_at','published_at'):
            if x.get(k): return str(x[k])
        for v in x.values():
            r=find_ts(v)
            if r: return r
    if isinstance(x,list):
        for v in x[:20]:
            r=find_ts(v)
            if r: return r
    return None
def sections(x):
    if not isinstance(x,dict): return []
    out=[]
    for k in ('report_sections','dashboard_ready_blocks','email_ready_blocks','line_summary_blocks','recommendation_blocks','warning_blocks','source_credibility_section','formal_report_integration_section'):
        v=x.get(k)
        if isinstance(v,dict): out+=list(v.keys())
        elif isinstance(v,list): out.append(k)
        elif v is not None: out.append(k)
    return sorted(set(map(str,out)))
def inspect_sources():
    rows=[]
    for p in CANDIDATES:
        r=rel(p); exists=p.exists(); hs=hits_path(p) if exists else []; payload=load_json(p) if exists and not hs else None; ts=find_ts(payload) if payload is not None else None
        rows.append({'path':r,'type':'json','allowlist_category':next((a for a in ALLOWED if r==a or r.startswith(a)),None),'exists':exists,'used':exists and allowed(r) and not hs and payload is not None,'reason':'used' if exists and allowed(r) and not hs and payload is not None else 'missing_or_not_allowlisted_or_secret_like_or_unparseable','timestamp':ts,'freshness_status':fresh(ts,FRESH['latest_report'])['status'] if ts else 'missing','secret_pattern_hits':len(hs),'sections':sections(payload)})
    return rows
def inspect_db():
    db=ROOT/'data/stock_analysis.db'; res={'path':rel(db),'exists':db.exists(),'used':False,'read_only_uri':SQLITE_URI,'sqlite_opened_read_only':False,'tables':[],'row_count':0,'latest_created_at':None,'stocks':[],'latest_rows':[]}
    if not db.exists(): res['reason']='missing'; return res
    con=sqlite3.connect(f'file:{db}?mode=ro',uri=True); con.row_factory=sqlite3.Row; cur=con.cursor(); res['sqlite_opened_read_only']=True
    cur.execute("select name from sqlite_master where type='table' order by name"); res['tables']=[r[0] for r in cur.fetchall()]
    if 'analysis_results' in res['tables']:
        cur.execute('select count(*) c, max(created_at) latest_created_at from analysis_results'); row=cur.fetchone(); res['row_count']=int(row['c'] or 0); res['latest_created_at']=row['latest_created_at']
        cur.execute('select stock_id, max(stock_name) stock_name, max(created_at) last_updated, count(*) record_count from analysis_results group by stock_id order by stock_id limit 100'); res['stocks']=[dict(r) for r in cur.fetchall()]
        cur.execute('pragma table_info(analysis_results)'); cols=[r['name'] for r in cur.fetchall()]
        wanted=['stock_id','stock_name','created_at','total_score','rating','action','technical_summary','chip_summary','news_summary','adr_summary','risk_summary']
        select_cols=[c for c in wanted if c in cols]
        cur.execute('select '+', '.join(select_cols)+' from analysis_results where created_at in (select max(created_at) from analysis_results) order by stock_id limit 100')
        latest=[]
        for row in cur.fetchall():
            d=dict(row)
            for c in wanted:
                d.setdefault(c,None)
            latest.append(d)
        res['latest_rows']=latest
        res['used']=True
    else: res['reason']='analysis_results_table_missing'
    con.close(); return res
def stock_universe(db):
    if not db.get('used'): return [{'data_state':'missing','freshness_status':'missing','message':'目前尚未找到可用追蹤標的資料'}]
    out=[]
    for s in db.get('stocks',[]):
        f=fresh(s.get('last_updated'),FRESH['stock_universe']); out.append({'stock_id':s.get('stock_id'),'stock_name':s.get('stock_name'),'latest_report_timestamp':s.get('last_updated'),'source':'data/stock_analysis.db:analysis_results','record_count':s.get('record_count'),'freshness_status':f['status'],'freshness_label':f['label'],'data_state':'usable' if f['status']=='fresh' else 'stale'})
    return out
def latest_reports(db,sources):
    out=[]
    if db.get('used'):
        f=fresh(db.get('latest_created_at'),FRESH['latest_report']); out.append({'report_window':'latest_local_analysis_results','generated_timestamp':db.get('latest_created_at'),'stock_count':len(db.get('stocks',[])),'report_sections_available':['stock_universe','per_stock_summary','rating_action_if_existing','technical_summary','chip_summary','news_summary','adr_summary','risk_summary'],'missing_sections':['formal_prediction_fields','actual_outcome_review_fields'],'freshness_status':f['status'],'freshness_label':f['label'],'source':db.get('path'),'summary':'Read existing local analysis_results in read-only mode; no production report was generated.'})
    for s in sources:
        if s.get('used') and s.get('sections'):
            f=fresh(s.get('timestamp'),FRESH['latest_report']) if s.get('timestamp') else {'status':'preview_only','label':'靜態範例'}
            out.append({'report_window':Path(str(s.get('path'))).stem,'generated_timestamp':s.get('timestamp'),'stock_count':None,'report_sections_available':s.get('sections',[]),'missing_sections':[],'freshness_status':f.get('status'),'freshness_label':f.get('label'),'source':s.get('path'),'summary':'Existing sanitized structured artifact discovered for dashboard context.'})
    return out[:12] or [{'data_state':'missing','freshness_status':'missing','summary':'No structured report artifact found.'}]
def per_stock(db):
    out=[]
    for r in db.get('latest_rows',[]):
        f=fresh(r.get('created_at'),FRESH['per_stock_summary']); out.append({'stock_id':r.get('stock_id'),'stock_name':r.get('stock_name'),'window':'latest_local_analysis_results','generated_at':r.get('created_at'),'latest_close':None,'total_score':r.get('total_score'),'rating':r.get('rating'),'action':r.get('action'),'technical_summary':r.get('technical_summary'),'chip_summary':r.get('chip_summary'),'news_summary':r.get('news_summary'),'adr_summary':r.get('adr_summary'),'risk_summary':r.get('risk_summary'),'data_state':'existing_runtime_record' if f['status']=='fresh' else 'stale_existing_runtime_record','freshness_status':f['status'],'freshness_label':f['label'],'source':'data/stock_analysis.db:analysis_results'})
    return out or [{'data_state':'missing','freshness_status':'missing','message':'No safe per-stock summaries found.'}]
def missing_prediction_fields():
    return [{'field':k,'label':label,'data_state':'missing','message':f'資料待接：未找到具 timestamp 的正式 {label} 欄位','source_timestamp':None,'freshness_status':'missing'} for k,label in [('same_day_high_low','same-day high/low forecast'),('next_day_high_low','next-day high/low forecast'),('one_month_trend','1M trend'),('three_month_trend','3M trend'),('confidence','confidence'),('rationale','rationale')]]
def missing_actual_fields(): return [{'field':f,'data_state':'missing','message':'資料待接：未找到安全 actual outcome / review 欄位','freshness_status':'missing'} for f in ['actual_high','actual_low','actual_close','direction_result','high_low_forecast_error','hit_miss_status','review_timestamp']]
def missing_review_fields(): return [{'field':f,'data_state':'missing','message':'資料待接：未找到正式 prediction review runtime 欄位','freshness_status':'missing'} for f in ['review_window','review_timestamp','seven_day_hit_rate','confidence_calibration','factor_effectiveness','error_reasons','recommendation_for_improvement']]
def source_credibility():
    return [{'source_family':'official_company_financial_ir','label':'官方公告 / 財報 / 法說會','credibility':'core_evidence','allowed_usage':'core forecast evidence when present','freshness_status':'always_current'},{'source_family':'twse_chip_market','label':'TWSE / 籌碼 / 市場官方資料','credibility':'structured_evidence','allowed_usage':'official market/chip evidence','freshness_status':'always_current'},{'source_family':'industry_peer_context','label':'產業 / 同業脈絡','credibility':'contextual_evidence','allowed_usage':'contextual evidence','freshness_status':'always_current'},{'source_family':'google_news_rss','label':'Google News / yfinance / broker target','credibility':'auxiliary_context','allowed_usage':'event/sentiment support only','freshness_status':'always_current'},{'source_family':'yfinance_yahoo','label':'yfinance / Yahoo','credibility':'external_market_proxy','allowed_usage':'external market proxy, not official evidence','freshness_status':'always_current'},{'source_family':'broker_target_analyst_rating','label':'券商目標價 / 分析師評等','credibility':'metadata_noise','allowed_usage':'metadata only; no direct rating/action/confidence impact','freshness_status':'always_current'},{'source_family':'gemini_ai_summary','label':'Gemini / AI summary','credibility':'explanation_layer','allowed_usage':'not original evidence','freshness_status':'always_current'}]
def four_windows(ts):
    out=[]
    for key,t,label,expected in WINDOWS:
        has=key in {'pre_open_0700','post_close_1500'} and bool(ts); f=fresh(ts if has else None,FRESH[key])
        out.append({'window_key':key,'expected_time':t,'display_name':label,'latest_available_data_timestamp':ts if has else None,'freshness_status':f['status'],'freshness_label':f['label'],'available_sections':['latest_local_analysis_summary'] if has else [],'missing_sections':[] if has else expected,'pm_readable_action':'可參考既有本機分析摘要；仍需正式 runtime data 接線' if has else '資料待接：請先完成正式 runtime data binding','full_prediction_review':key=='post_close_1500'})
    return out
def build():
    sources=inspect_sources(); db=inspect_db(); stocks=stock_universe(db); reports=latest_reports(db,sources); ps=per_stock(db); preds=missing_prediction_fields(); actuals=missing_actual_fields(); reviews=missing_review_fields(); cred=source_credibility(); ts=db.get('latest_created_at'); windows=four_windows(ts)
    checks=[{'category':'runtime_window','id':w['window_key'],'timestamp':w['latest_available_data_timestamp'],'max_age_hours':FRESH[w['window_key']],'status':w['freshness_status']} for w in windows]
    checks += [{'category':'stock_universe','id':str(s.get('stock_id')),'timestamp':s.get('latest_report_timestamp'),'max_age_hours':FRESH['stock_universe'],'status':s.get('freshness_status')} for s in stocks if s.get('stock_id')]
    checks += [{'category':'latest_report','id':str(i),'timestamp':r.get('generated_timestamp'),'max_age_hours':FRESH['latest_report'],'status':r.get('freshness_status')} for i,r in enumerate(reports)]
    checks += [{'category':'prediction_fields','id':r['field'],'timestamp':r.get('source_timestamp'),'max_age_hours':FRESH['prediction_fields'],'status':r.get('freshness_status')} for r in preds]
    checks += [{'category':'actual_outcome_fields','id':r['field'],'timestamp':None,'max_age_hours':FRESH['actual_outcome_fields'],'status':r.get('freshness_status')} for r in actuals]
    checks += [{'category':'prediction_review_fields','id':r['field'],'timestamp':None,'max_age_hours':FRESH['prediction_review_fields'],'status':r.get('freshness_status')} for r in reviews]
    statuses=[c.get('status') for c in checks]; global_st='missing' if all(s=='missing' for s in statuses) else 'stale' if 'stale' in statuses else 'partial_data' if 'missing' in statuses else 'fresh'
    missing=[{'category':c.get('category'),'id':c.get('id'),'message':'source timestamp or field unavailable'} for c in checks if c.get('status')=='missing']; stale=[{'category':c.get('category'),'id':c.get('id'),'timestamp':c.get('timestamp'),'max_age_hours':c.get('max_age_hours')} for c in checks if c.get('status')=='stale']
    inspected=[*sources,{'path':db['path'],'type':'sqlite','allowlist_category':'data/stock_analysis.db','exists':db['exists'],'used':db['used'],'timestamp':db.get('latest_created_at'),'freshness_status':fresh(db.get('latest_created_at'),FRESH['latest_report'])['status'] if db.get('latest_created_at') else 'missing','secret_pattern_hits':0,'sqlite_opened_read_only':db.get('sqlite_opened_read_only'),'reason':'used_read_only' if db.get('used') else db.get('reason','missing')}]
    return {'schema_version':'four_window_dashboard_production_runtime_export_v1','task_id':'AI-DEV-148','generated_at':NOW.isoformat(),'export_mode':'safe_local_read_only_existing_runtime_artifacts','latest_runtime_window':'latest_local_analysis_results' if db.get('used') else 'missing','latest_runtime_timestamp':ts,'global_freshness_status':global_st,'stock_universe':stocks,'latest_reports':reports,'per_stock_summaries':ps,'prediction_fields':preds,'actual_outcome_fields':actuals,'prediction_review_fields':reviews,'source_credibility':cred,'four_windows':windows,'freshness_policy':FRESH,'freshness_checks':checks,'missing_data':missing,'stale_data':stale,'inspected_sources':inspected,'rollback':{'static_preview_rollback_supported':True,'latest_known_publish_manifest':'/var/www/stock-ai-dashboard/.ai_dev_145_publish_results/latest.json'},'safety':{'external_api_called':False,'external_credentialed_api_called':False,'secrets_read':False,'db_write':False,'sqlite_opened_read_only':bool(db.get('sqlite_opened_read_only')),'scheduler_modified':False,'external_notification_sent':False,'production_pipeline_executed':False,'python_main_executed':False,'trading_or_order_executed':False,'production_rating_action_confidence_weight_mutated':False,'formal_delivery_behavior_changed':False,'nginx_systemd_firewall_modified':False,'fabricated_market_data':False}}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=OUT); ap.add_argument('--write-input',action='store_true'); ap.add_argument('--pretty',action='store_true'); args=ap.parse_args(); data=build(); args.output.write_text(stable(data),encoding='utf-8')
    if args.write_input: INP.write_text(stable({'schema_version':'four_window_dashboard_production_runtime_export_input_v1','task_id':'AI-DEV-148','allowed_sources':list(ALLOWED),'source_candidates':[rel(p) for p in CANDIDATES],'sqlite_uri':SQLITE_URI,'freshness_hours':FRESH,'dashboard_public_url':PUBLIC_URL}),encoding='utf-8')
    print(stable({'ok':True,'task_id':'AI-DEV-148','output':str(args.output),'global_freshness_status':data['global_freshness_status'],'stock_universe_count':len([r for r in data['stock_universe'] if r.get('stock_id')]),'latest_report_count':len(data['latest_reports']),'per_stock_summary_count':len([r for r in data['per_stock_summaries'] if r.get('stock_id')]),'missing_data_count':len(data['missing_data']),'stale_data_count':len(data['stale_data']),'sqlite_used_read_only':data['safety']['sqlite_opened_read_only']}),end='')
if __name__=='__main__': main()
