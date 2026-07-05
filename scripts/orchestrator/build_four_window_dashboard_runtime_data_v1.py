#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'templates/four_window_dashboard_runtime_data.example.json'
INP=ROOT/'templates/four_window_dashboard_runtime_data_input.example.json'
PUBLIC_URL='http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html'
TAIPEI=ZoneInfo('Asia/Taipei')
NOW=datetime(2026,7,5,23,56,0,tzinfo=TAIPEI)
ALLOWED=('templates/','docs/','orchestrator/templates/','orchestrator/queue/','/var/www/stock-ai-dashboard/.ai_dev_145_publish_results/latest.json','/home/kaochuchian/dify/docker/volumes/certbot/www/stock-ai-dashboard/.ai_dev_145_publish_results','/home/kaochuchian/dify/docker/volumes/certbot/www/stock-ai-dashboard/.ai_dev_145_publish_results/','/home/kaochuchian/.local/state/stock-ai-orchestrator/','data/stock_analysis.db')
SECRET=[re.compile(p,re.I) for p in (r'ghp_',r'github_pat_',r'sk-[A-Za-z0-9_-]{16,}',r'Bearer\s+[A-Za-z0-9._~+/=-]{16,}',r'BEGIN (RSA|OPENSSH) PRIVATE KEY',r'api[_-]?key\s*[:=]',r'access[_-]?token\s*[:=]',r'password\s*[:=]')]
FRESH={'pre_open_0700':18,'intraday_1305':4,'pre_close_1335':4,'post_close_1500':36,'stock_universe':168,'report_summary':36,'prediction_fields':36}
WINDOWS=[('pre_open_0700','07:00','盤前預測 / Pre-open Forecast',['market_context','prediction_range','risk_notes','source_quality']),('intraday_1305','13:05','盤中追蹤 / Intraday Tracking',['intraday_status','price_vs_range','volume_chip_context','invalidation_notes']),('pre_close_1335','13:35','收盤快照 / Close Snapshot',['actual_high_low','close_price','initial_hit_status','pending_full_review']),('post_close_1500','15:00','盤後檢討 / Prediction Review',['forecast_vs_actual','hit_metrics','error_sources','decision_quality_feedback'])]

def stable(x:Any)->str: return json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
def rel(p:Path)->str:
    try: return str(p.resolve().relative_to(ROOT))
    except ValueError: return str(p.resolve())
def allowed(s:str)->bool: return any(s==a or s.startswith(a) for a in ALLOWED)
def parse_dt(v:Any):
    if not v: return None
    try:
        d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
        if d.tzinfo is None: d=d.replace(tzinfo=TAIPEI)
        return d.astimezone(TAIPEI)
    except Exception: return None
def freshness(ts:Any,maxh:int,preview=False):
    if preview: return {'status':'preview_only','label':'預覽資料','timestamp':ts,'max_age_hours':maxh}
    d=parse_dt(ts)
    if not d: return {'status':'missing','label':'資料待接','timestamp':ts,'max_age_hours':maxh}
    age=(NOW-d).total_seconds()/3600
    st='fresh' if age<=maxh else 'stale'
    return {'status':st,'label':'資料正常' if st=='fresh' else '資料過期','timestamp':d.isoformat(),'age_hours':round(age,2),'max_age_hours':maxh}
def secret_hits(path:Path):
    try: txt=path.read_text(encoding='utf-8',errors='ignore')[:200000]
    except Exception: return []
    return [p.pattern for p in SECRET if p.search(txt)]
def safe_sources():
    cand=[ROOT/'templates/prediction_context_artifact.example.json',ROOT/'templates/unified_explainability_artifact.example.json',ROOT/'templates/context_based_report_assembly_artifact.example.json',ROOT/'templates/dashboard_decision_intelligence_artifact.example.json',ROOT/'templates/decision_quality_feedback_artifact.example.json',ROOT/'templates/official_primary_source_context_admission_artifact.example.json',ROOT/'templates/four_window_dashboard_route_integration.example.json',ROOT/'templates/four_window_dashboard_pm_readable_ux.example.json',Path('/var/www/stock-ai-dashboard/.ai_dev_145_publish_results/latest.json','/home/kaochuchian/dify/docker/volumes/certbot/www/stock-ai-dashboard/.ai_dev_145_publish_results','/home/kaochuchian/dify/docker/volumes/certbot/www/stock-ai-dashboard/.ai_dev_145_publish_results/')]
    out=[]
    for p in cand:
        r=rel(p); hits=secret_hits(p) if p.exists() else []
        out.append({'path':r,'exists':p.exists(),'used':p.exists() and allowed(r) and not hits,'secret_pattern_hits':hits,'reason':None if p.exists() and allowed(r) and not hits else 'missing_or_not_allowlisted_or_secret_like'})
    return out
def inspect_db():
    db=ROOT/'data/stock_analysis.db'; res={'path':rel(db),'exists':db.exists(),'used':False,'read_only_uri':'file:data/stock_analysis.db?mode=ro','tables':[],'row_count':0,'latest_created_at':None,'stocks':[]}
    if not db.exists(): res['reason']='missing'; return res
    con=sqlite3.connect(f'file:{db}?mode=ro',uri=True); con.row_factory=sqlite3.Row; cur=con.cursor()
    cur.execute("select name from sqlite_master where type='table' order by name"); tables=[r[0] for r in cur.fetchall()]; res['tables']=tables
    if 'analysis_results' in tables:
        cur.execute('select count(*) c, max(created_at) latest_created_at from analysis_results'); row=cur.fetchone(); res['row_count']=int(row['c'] or 0); res['latest_created_at']=row['latest_created_at']
        cur.execute('select stock_id, max(stock_name) stock_name, max(created_at) last_updated, count(*) record_count from analysis_results group by stock_id order by stock_id limit 50')
        res['stocks']=[dict(r) for r in cur.fetchall()]; res['used']=True
    else: res['reason']='analysis_results_table_missing'
    con.close(); return res
def stock_universe(db):
    if not db.get('used') or not db.get('stocks'): return [{'data_state':'missing','freshness_status':'missing','message':'目前尚未找到可用追蹤標的資料'}]
    rows=[]
    for s in db['stocks']:
        f=freshness(s.get('last_updated'),FRESH['stock_universe']); rows.append({'stock_id':s.get('stock_id'),'stock_name':s.get('stock_name'),'source_artifact_or_table':'data/stock_analysis.db:analysis_results','last_updated':s.get('last_updated'),'freshness_status':f['status'],'freshness_label':f['label'],'data_state':'usable' if f['status']=='fresh' else 'stale','record_count':s.get('record_count')})
    return rows
def latest_reports(db):
    if not db.get('used'): return [{'data_state':'missing','freshness_status':'missing','summary':'目前尚未找到可用資料','source_path':db.get('path')}]
    f=freshness(db.get('latest_created_at'),FRESH['report_summary']); return [{'report_window':'latest_local_analysis_results','generated_timestamp':db.get('latest_created_at'),'stock_count':len(db.get('stocks',[])),'summary':'已從本機 SQLite analysis_results 讀取 sanitized 摘要；未執行 production pipeline。','source_path':db.get('path'),'freshness_status':f['status'],'freshness_label':f['label']}]
def prediction_fields():
    return [{'field':'same_day_high_low','data_state':'missing','message':'資料待接：未找到具 timestamp 的正式同日高低點預測欄位','freshness_status':'missing'},{'field':'next_day_high_low','data_state':'missing','message':'資料待接：未找到具 timestamp 的正式次日高低點預測欄位','freshness_status':'missing'},{'field':'one_month_trend','data_state':'missing','message':'資料待接：未找到正式 1M trend 欄位','freshness_status':'missing'},{'field':'three_month_trend','data_state':'missing','message':'資料待接：未找到正式 3M trend 欄位','freshness_status':'missing'},{'field':'confidence_rationale','data_state':'preview_only','message':'僅預覽：static artifacts 提供政策與解釋架構，不提供正式 confidence 數值','freshness_status':'preview_only'}]
def four_windows(db):
    out=[]
    for key,t,label,expected in WINDOWS:
        has=bool(db.get('used')) and key in ('pre_open_0700','post_close_1500'); ts=db.get('latest_created_at') if has else None; f=freshness(ts,FRESH[key]) if has else freshness(None,FRESH[key])
        out.append({'window_key':key,'expected_time':t,'display_name':label,'latest_available_data_timestamp':ts,'freshness_status':f['status'],'freshness_label':f['label'],'available_sections':['local_analysis_summary'] if has else [],'missing_sections':[s for s in expected if not has],'pm_readable_action':'可參考本機最近分析摘要，但仍需正式 runtime 接線' if has else '資料待接：請先完成正式 runtime data binding','full_prediction_review':key=='post_close_1500'})
    return out
def source_quality():
    return [{'source_family':'official_company_filings','label':'官方公告 / 財報 / 法說會','quality':'high','allowed_usage':'core evidence','freshness_status':'always_current'},{'source_family':'industry_peer_context','label':'產業供應鏈 / 同業脈絡','quality':'medium','allowed_usage':'contextual evidence','freshness_status':'always_current'},{'source_family':'google_news_yfinance_broker','label':'Google News / yfinance / broker target','quality':'support_only','allowed_usage':'auxiliary only, no direct rating/action/confidence change','freshness_status':'always_current'},{'source_family':'gemini_ai_summary','label':'Gemini / AI summary','quality':'explanation_layer','allowed_usage':'not original evidence','freshness_status':'always_current'}]
def build():
    sources=safe_sources(); db=inspect_db(); stocks=stock_universe(db); reports=latest_reports(db); windows=four_windows(db); preds=prediction_fields(); sq=source_quality()
    freshness_checks=[{'category':'four_windows','id':w['window_key'],'timestamp':w['latest_available_data_timestamp'],'max_age_hours':FRESH[w['window_key']],'status':w['freshness_status']} for w in windows]
    freshness_checks += [{'category':'stock_universe','id':str(s.get('stock_id')),'timestamp':s.get('last_updated'),'max_age_hours':FRESH['stock_universe'],'status':s.get('freshness_status')} for s in stocks if s.get('stock_id')]
    freshness_checks += [{'category':'prediction_fields','id':p['field'],'timestamp':None,'max_age_hours':FRESH['prediction_fields'],'status':p['freshness_status']} for p in preds]
    statuses=[c['status'] for c in freshness_checks]
    global_status='missing' if all(s=='missing' for s in statuses) else 'stale' if any(s=='stale' for s in statuses) else 'partial_data' if any(s=='missing' for s in statuses) else 'fresh'
    latest=db.get('latest_created_at')
    missing=[{'category':'four_window','id':w['window_key'],'missing_sections':w['missing_sections']} for w in windows if w['missing_sections']]+[{'category':'prediction_fields','id':p['field'],'message':p['message']} for p in preds if p['freshness_status']=='missing']
    return {'schema_version':'four_window_dashboard_runtime_data_v1','task_id':'AI-DEV-147','generated_at':NOW.isoformat(),'data_binding_mode':'safe_local_read_only_export','global_freshness_status':global_status,'latest_data_timestamp':latest,'dashboard_public_url':PUBLIC_URL,'stock_universe':stocks,'latest_reports':reports,'four_windows':windows,'prediction_fields':preds,'source_quality':sq,'freshness_checks':freshness_checks,'missing_data':missing,'inspected_sources':[*sources,db],'bound_categories':['stock_universe' if any(s.get('stock_id') for s in stocks) else 'stock_universe_missing','latest_report_summary' if db.get('used') else 'latest_report_missing','source_quality_policy','four_window_status','prediction_fields_missing'],'safety':{'external_api_called':False,'secrets_read':False,'db_write':False,'sqlite_opened_read_only':bool(db.get('exists')),'scheduler_modified':False,'external_notification_sent':False,'production_pipeline_executed':False,'python_main_executed':False,'trading_or_order_executed':False,'production_rating_action_confidence_weight_mutated':False,'formal_delivery_behavior_changed':False,'fabricated_market_data':False}}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=OUT); ap.add_argument('--write-input',action='store_true'); ap.add_argument('--pretty',action='store_true'); args=ap.parse_args(); data=build(); args.output.write_text(stable(data),encoding='utf-8')
    if args.write_input: INP.write_text(stable({'schema_version':'four_window_dashboard_runtime_data_input_v1','task_id':'AI-DEV-147','allowed_sources':list(ALLOWED),'freshness_hours':FRESH,'dashboard_public_url':PUBLIC_URL}),encoding='utf-8')
    print(stable({'ok':True,'task_id':'AI-DEV-147','output':str(args.output),'global_freshness_status':data['global_freshness_status'],'stock_universe_count':len([s for s in data['stock_universe'] if s.get('stock_id')]),'missing_data_count':len(data['missing_data']),'sqlite_used_read_only':data['safety']['sqlite_opened_read_only']}),end='')
if __name__=='__main__': main()
