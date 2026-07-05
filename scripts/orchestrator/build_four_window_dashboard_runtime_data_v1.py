#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,subprocess,sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'templates/four_window_dashboard_runtime_data.example.json'
INP=ROOT/'templates/four_window_dashboard_runtime_data_input.example.json'
EXPORT=ROOT/'templates/four_window_dashboard_production_runtime_export.example.json'
EXPORT_BUILDER=ROOT/'scripts/orchestrator/build_four_window_dashboard_production_runtime_export_v1.py'
PUBLIC_URL='http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html'
TAIPEI=ZoneInfo('Asia/Taipei'); NOW=datetime(2026,7,6,0,22,0,tzinfo=TAIPEI)
SECRET=[re.compile(p,re.I) for p in (r'ghp_',r'github_pat_',r'sk-[A-Za-z0-9_-]{16,}',r'Bearer\s+[A-Za-z0-9._~+/=-]{16,}',r'BEGIN (RSA|OPENSSH) PRIVATE KEY',r'api[_-]?key\s*[:=]',r'access[_-]?token\s*[:=]',r'password\s*[:=]')]
def stable(x:Any)->str: return json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
def ensure_export():
    subprocess.run([sys.executable,str(EXPORT_BUILDER),'--pretty','--write-input'],check=True,cwd=ROOT,stdout=subprocess.DEVNULL)
    txt=EXPORT.read_text(encoding='utf-8')
    for p in SECRET:
        if p.search(txt): raise SystemExit(f'secret-like pattern found in {EXPORT.relative_to(ROOT)}')
    return json.loads(txt)
def source_quality(export):
    return [{'source_family':r.get('source_family'),'label':r.get('label'),'quality':r.get('credibility'),'allowed_usage':r.get('allowed_usage'),'freshness_status':r.get('freshness_status')} for r in export.get('source_credibility',[]) if isinstance(r,dict)]
def build():
    e=ensure_export(); missing=list(e.get('missing_data',[])); stale=list(e.get('stale_data',[]))
    for cat,rows in [('prediction_fields',e.get('prediction_fields',[])),('actual_outcome_fields',e.get('actual_outcome_fields',[])),('prediction_review_fields',e.get('prediction_review_fields',[]))]:
        for r in rows:
            if isinstance(r,dict) and r.get('freshness_status')=='missing': missing.append({'category':cat,'id':r.get('field'),'message':r.get('message')})
    return {'schema_version':'four_window_dashboard_runtime_data_v1','task_id':'AI-DEV-148','generated_at':NOW.isoformat(),'data_binding_mode':'production_runtime_export_normalized_for_dashboard','production_runtime_export_ref':'templates/four_window_dashboard_production_runtime_export.example.json','global_freshness_status':e.get('global_freshness_status'),'latest_data_timestamp':e.get('latest_runtime_timestamp'),'latest_runtime_window':e.get('latest_runtime_window'),'dashboard_public_url':PUBLIC_URL,'stock_universe':e.get('stock_universe',[]),'latest_reports':e.get('latest_reports',[]),'per_stock_summaries':e.get('per_stock_summaries',[]),'four_windows':e.get('four_windows',[]),'prediction_fields':e.get('prediction_fields',[]),'actual_outcome_fields':e.get('actual_outcome_fields',[]),'prediction_review_fields':e.get('prediction_review_fields',[]),'source_quality':source_quality(e),'source_credibility':e.get('source_credibility',[]),'freshness_policy':e.get('freshness_policy',{}),'freshness_checks':e.get('freshness_checks',[]),'missing_data':missing,'stale_data':stale,'inspected_sources':e.get('inspected_sources',[]),'bound_categories':['production_runtime_export','stock_universe','latest_report_summary','per_stock_summary','prediction_fields_status','actual_outcome_fields_status','prediction_review_fields_status','source_credibility_policy','four_window_status'],'safety':e.get('safety',{})}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=OUT); ap.add_argument('--write-input',action='store_true'); ap.add_argument('--pretty',action='store_true'); args=ap.parse_args(); data=build(); args.output.write_text(stable(data),encoding='utf-8')
    if args.write_input: INP.write_text(stable({'schema_version':'four_window_dashboard_runtime_data_input_v1','task_id':'AI-DEV-148','production_runtime_export_ref':'templates/four_window_dashboard_production_runtime_export.example.json','dashboard_public_url':PUBLIC_URL}),encoding='utf-8')
    print(stable({'ok':True,'task_id':'AI-DEV-148','output':str(args.output),'global_freshness_status':data.get('global_freshness_status'),'stock_universe_count':len([r for r in data.get('stock_universe',[]) if r.get('stock_id')]),'latest_report_count':len(data.get('latest_reports',[])),'per_stock_summary_count':len([r for r in data.get('per_stock_summaries',[]) if r.get('stock_id')]),'missing_data_count':len(data.get('missing_data',[])),'stale_data_count':len(data.get('stale_data',[])),'sqlite_used_read_only':data.get('safety',{}).get('sqlite_opened_read_only')}),end='')
if __name__=='__main__': main()
