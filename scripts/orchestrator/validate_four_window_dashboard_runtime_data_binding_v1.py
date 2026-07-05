#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'templates/four_window_dashboard_runtime_data.example.json'; EXPORT=ROOT/'templates/four_window_dashboard_production_runtime_export.example.json'; HTML=ROOT/'templates/four_window_dashboard_route_preview.example.html'
DOCS=[ROOT/'docs/four_window_dashboard_runtime_data_binding_v1.md',ROOT/'docs/runbooks/four_window_dashboard_runtime_data_binding_runbook.md',ROOT/'docs/four_window_dashboard_production_runtime_export_v1.md',ROOT/'docs/runbooks/four_window_dashboard_production_runtime_export_runbook.md']
PUBLIC='http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html'
SECRET=[re.compile(p,re.I) for p in (r'ghp_',r'github_pat_',r'sk-[A-Za-z0-9_-]{16,}',r'Bearer\s+[A-Za-z0-9._~+/=-]{16,}',r'BEGIN (RSA|OPENSSH) PRIVATE KEY',r'api[_-]?key\s*[:=]',r'access[_-]?token\s*[:=]',r'password\s*[:=]')]
ALLOWED=('templates/','docs/','orchestrator/templates/','orchestrator/queue/','/var/www/stock-ai-dashboard/.ai_dev_145_publish_results/latest.json','/home/kaochuchian/dify/docker/volumes/certbot/www/stock-ai-dashboard/.ai_dev_145_publish_results','/home/kaochuchian/dify/docker/volumes/certbot/www/stock-ai-dashboard/.ai_dev_145_publish_results/','/home/kaochuchian/.local/state/stock-ai-orchestrator/','data/stock_analysis.db')
REQ_HTML=['四時段 AI 決策儀表板','今日決策摘要','四個時段怎麼看','目前追蹤標的','最新報告摘要','個股狀態摘要','預測資料狀態','實際結果 / 預測檢討狀態','資料新鮮度','資料來源可信度','技術檢查 / Debug','資料待接','資料過期']
def fetch(url):
    try:
        with urlopen(url,timeout=10) as r: return True,r.read().decode('utf-8',errors='replace'),None
    except (HTTPError,URLError,TimeoutError,OSError) as e: return False,'',str(e)
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def allowed_path(p): return any(str(p)==a or str(p).startswith(a) for a in ALLOWED)
def scan(paths):
    hits=[]
    for p in paths:
        if p.exists():
            txt=p.read_text(encoding='utf-8',errors='ignore')[:500000]
            hits += [f'{p.relative_to(ROOT)}:{pat.pattern}' for pat in SECRET if pat.search(txt)]
    return hits
def validate_html(txt,errors):
    for s in REQ_HTML:
        if s not in txt: errors.append(f'html missing section/text: {s}')
    if '<iframe' in txt.lower(): errors.append('html must not contain iframe')
    if '收盤前' in txt or 'Pre-close' in txt: errors.append('13:35 must not use pre-close semantic')
    if '收盤快照 / Close Snapshot' not in txt: errors.append('13:35 close snapshot missing')
    if '完整檢討待 15:00' not in txt: errors.append('13:35 must defer full review')
    if '盤後檢討 / Prediction Review' not in txt: errors.append('15:00 prediction review missing')
    if txt.find('技術檢查 / Debug') < txt.find('資料來源可信度'): errors.append('debug must remain after main content')
def validate_art(data,errors):
    if data.get('schema_version')!='four_window_dashboard_runtime_data_v1': errors.append('schema_version mismatch')
    if data.get('task_id')!='AI-DEV-148': errors.append('task_id mismatch')
    for key in ['data_binding_mode','production_runtime_export_ref','global_freshness_status','latest_data_timestamp','dashboard_public_url','stock_universe','latest_reports','per_stock_summaries','four_windows','prediction_fields','actual_outcome_fields','prediction_review_fields','source_quality','freshness_checks','missing_data','stale_data','inspected_sources','safety']:
        if key not in data: errors.append(f'missing artifact field: {key}')
    windows=data.get('four_windows',[])
    if not isinstance(windows,list) or len(windows)!=4: errors.append('four_windows must contain four windows')
    by={w.get('window_key'):w for w in windows if isinstance(w,dict)}
    if by.get('pre_close_1335',{}).get('display_name')!='收盤快照 / Close Snapshot': errors.append('13:35 must be close snapshot')
    if by.get('pre_close_1335',{}).get('full_prediction_review') is not False: errors.append('13:35 must not be full prediction review')
    if by.get('post_close_1500',{}).get('display_name')!='盤後檢討 / Prediction Review': errors.append('15:00 prediction review label mismatch')
    if by.get('post_close_1500',{}).get('full_prediction_review') is not True: errors.append('15:00 must be full prediction review')
    statuses=[c.get('status') for c in data.get('freshness_checks',[]) if isinstance(c,dict)]
    if 'stale' not in statuses: errors.append('stale data must be clearly labeled')
    if 'missing' not in statuses: errors.append('missing data must be clearly labeled')
    for key in ['latest_reports','per_stock_summaries','prediction_fields','actual_outcome_fields','prediction_review_fields','source_quality']:
        if not data.get(key): errors.append(f'{key} section or missing state required')
    for src in data.get('inspected_sources',[]):
        if isinstance(src,dict):
            p=src.get('path','')
            if p and not allowed_path(p): errors.append(f'inspected source not allowlisted: {p}')
            if src.get('secret_pattern_hits') not in (0,[],None): errors.append(f'secret-like hit in inspected source: {p}')
    safety=data.get('safety',{}) if isinstance(data.get('safety'),dict) else {}
    for k in ['external_api_called','secrets_read','db_write','scheduler_modified','external_notification_sent','production_pipeline_executed','python_main_executed','trading_or_order_executed','production_rating_action_confidence_weight_mutated','formal_delivery_behavior_changed','fabricated_market_data']:
        if safety.get(k) is not False: errors.append(f'safety.{k} must be false')
    if safety.get('sqlite_opened_read_only') not in (True,False): errors.append('sqlite_opened_read_only flag required')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--published',action='store_true'); ap.add_argument('--pretty',action='store_true'); args=ap.parse_args(); errors=[]
    for p in [ART,EXPORT,HTML,*DOCS]:
        if not p.exists(): errors.append(f'missing file: {p.relative_to(ROOT)}')
    data=load(ART) if ART.exists() else {}; html=HTML.read_text(encoding='utf-8') if HTML.exists() else ''
    if data: validate_art(data,errors)
    if html: validate_html(html,errors)
    pub={'checked':False}
    if args.published:
        ok,txt,err=fetch(PUBLIC); pub={'checked':True,'reachable':ok,'error':err,'public_url':PUBLIC}
        if not ok: errors.append(f'public URL unreachable: {err}')
        else: validate_html(txt,errors)
    hits=scan([ART,EXPORT,HTML,*DOCS])
    if hits: errors += [f'secret pattern hit: {h}' for h in hits]
    res={'ok':not errors,'task_id':'AI-DEV-148','schema_version':'four_window_dashboard_runtime_data_binding_validation_v1','published_mode':args.published,'errors':errors,'summary':{'global_freshness_status':data.get('global_freshness_status'),'stock_universe_count':len([s for s in data.get('stock_universe',[]) if isinstance(s,dict) and s.get('stock_id')]),'latest_report_count':len(data.get('latest_reports',[])) if isinstance(data.get('latest_reports'),list) else None,'per_stock_summary_count':len([s for s in data.get('per_stock_summaries',[]) if isinstance(s,dict) and s.get('stock_id')]),'missing_data_count':len(data.get('missing_data',[])) if isinstance(data.get('missing_data'),list) else None,'stale_data_count':len(data.get('stale_data',[])) if isinstance(data.get('stale_data'),list) else None,'secret_pattern_hits':len(hits),'published_summary':pub}}
    print(json.dumps(res,ensure_ascii=False,indent=2 if args.pretty else None,sort_keys=True)); return 0 if res['ok'] else 2
if __name__=='__main__': raise SystemExit(main())
