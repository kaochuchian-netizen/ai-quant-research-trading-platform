#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[2]
EXPORT=ROOT/'templates/four_window_dashboard_production_runtime_export.example.json'; RUNTIME=ROOT/'templates/four_window_dashboard_runtime_data.example.json'; HTML=ROOT/'templates/four_window_dashboard_route_preview.example.html'
DOCS=[ROOT/'docs/four_window_dashboard_production_runtime_export_v1.md',ROOT/'docs/runbooks/four_window_dashboard_production_runtime_export_runbook.md']
PUBLIC='http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html'
ALLOWED=('templates/','docs/','orchestrator/templates/','orchestrator/queue/','/var/www/stock-ai-dashboard/.ai_dev_145_publish_results/latest.json','/home/kaochuchian/dify/docker/volumes/certbot/www/stock-ai-dashboard/.ai_dev_145_publish_results','/home/kaochuchian/dify/docker/volumes/certbot/www/stock-ai-dashboard/.ai_dev_145_publish_results/','/home/kaochuchian/.local/state/stock-ai-orchestrator/','data/stock_analysis.db')
SECRET=[re.compile(p,re.I) for p in (r'ghp_',r'github_pat_',r'sk-[A-Za-z0-9_-]{16,}',r'Bearer\s+[A-Za-z0-9._~+/=-]{16,}',r'BEGIN (RSA|OPENSSH) PRIVATE KEY',r'api[_-]?key\s*[:=]',r'access[_-]?token\s*[:=]',r'password\s*[:=]')]
REQ_HTML=['四時段 AI 決策儀表板','今日決策摘要','四個時段怎麼看','目前追蹤標的','最新報告摘要','個股狀態摘要','預測資料狀態','實際結果 / 預測檢討狀態','資料新鮮度','資料來源可信度','技術檢查 / Debug','資料待接','資料過期']
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def allowed(p): return any(p==a or str(p).startswith(a) for a in ALLOWED)
def scan(paths):
    hits=[]
    for p in paths:
        if p.exists():
            txt=p.read_text(encoding='utf-8',errors='ignore')[:500000]
            hits += [f'{p.relative_to(ROOT)}:{pat.pattern}' for pat in SECRET if pat.search(txt)]
    return hits
def fetch(url):
    try:
        with urlopen(url,timeout=10) as r: return True,r.read().decode('utf-8',errors='replace'),None
    except (HTTPError,URLError,TimeoutError,OSError) as e: return False,'',str(e)
def validate_export(d,errs):
    if d.get('schema_version')!='four_window_dashboard_production_runtime_export_v1': errs.append('schema mismatch')
    if d.get('task_id')!='AI-DEV-148': errs.append('task_id mismatch')
    for k in ['generated_at','export_mode','latest_runtime_window','latest_runtime_timestamp','global_freshness_status','stock_universe','latest_reports','per_stock_summaries','prediction_fields','actual_outcome_fields','prediction_review_fields','source_credibility','freshness_policy','freshness_checks','missing_data','stale_data','inspected_sources','safety','rollback']:
        if k not in d: errs.append(f'missing export field: {k}')
    if d.get('global_freshness_status') not in {'fresh','partial_data','stale','missing'}: errs.append('invalid freshness status')
    for k in ['stock_universe','latest_reports','per_stock_summaries','prediction_fields','actual_outcome_fields','prediction_review_fields','source_credibility','freshness_checks','missing_data','stale_data']:
        if not d.get(k): errs.append(f'{k} must exist or have explicit missing/stale state')
    statuses=[r.get('status') for r in d.get('freshness_checks',[]) if isinstance(r,dict)]
    if 'missing' not in statuses: errs.append('missing states must be explicit')
    if 'stale' not in statuses: errs.append('stale states must be explicit')
    for s in d.get('inspected_sources',[]):
        if isinstance(s,dict):
            p=str(s.get('path',''))
            if p and not allowed(p): errs.append(f'inspected source not allowlisted: {p}')
            if s.get('secret_pattern_hits') not in (0,[],None): errs.append(f'secret-like source hit: {p}')
    safety=d.get('safety',{}) if isinstance(d.get('safety'),dict) else {}
    for k in ['external_api_called','external_credentialed_api_called','secrets_read','db_write','scheduler_modified','external_notification_sent','production_pipeline_executed','python_main_executed','trading_or_order_executed','production_rating_action_confidence_weight_mutated','formal_delivery_behavior_changed','nginx_systemd_firewall_modified','fabricated_market_data']:
        if safety.get(k) is not False: errs.append(f'safety.{k} must be false')
    if safety.get('sqlite_opened_read_only') not in (True,False): errs.append('sqlite read-only flag missing')
    if not d.get('rollback',{}).get('static_preview_rollback_supported'): errs.append('rollback instructions missing')
def validate_html(html,errs):
    for x in REQ_HTML:
        if x not in html: errs.append(f'html missing required section/text: {x}')
    if '收盤快照 / Close Snapshot' not in html: errs.append('13:35 close snapshot missing')
    if '完整檢討待 15:00' not in html: errs.append('13:35 must defer full review')
    if '盤後檢討 / Prediction Review' not in html: errs.append('15:00 review missing')
    if '收盤前' in html or 'Pre-close' in html: errs.append('13:35 pre-close semantic forbidden')
    if '<iframe' in html.lower(): errs.append('iframe forbidden')
    if html.find('技術檢查 / Debug') < html.find('資料來源可信度'): errs.append('debug must remain after main content')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--published',action='store_true'); ap.add_argument('--pretty',action='store_true'); args=ap.parse_args(); errs=[]
    for p in [EXPORT,RUNTIME,HTML,*DOCS]:
        if not p.exists(): errs.append(f'missing file: {p.relative_to(ROOT)}')
    d=load(EXPORT) if EXPORT.exists() else {}; html=HTML.read_text(encoding='utf-8') if HTML.exists() else ''
    if d: validate_export(d,errs)
    if html: validate_html(html,errs)
    pub={'checked':False}
    if args.published:
        ok,txt,err=fetch(PUBLIC); pub={'checked':True,'reachable':ok,'error':err,'public_url':PUBLIC}
        if not ok: errs.append(f'public URL unreachable: {err}')
        else: validate_html(txt,errs)
    hits=scan([EXPORT,RUNTIME,HTML,*DOCS])
    if hits: errs += [f'secret pattern hit: {h}' for h in hits]
    res={'ok':not errs,'task_id':'AI-DEV-148','schema_version':'four_window_dashboard_production_runtime_export_validation_v1','published_mode':args.published,'errors':errs,'summary':{'stock_universe_count':len([r for r in d.get('stock_universe',[]) if isinstance(r,dict) and r.get('stock_id')]),'latest_report_count':len(d.get('latest_reports',[])) if isinstance(d.get('latest_reports'),list) else None,'per_stock_summary_count':len([r for r in d.get('per_stock_summaries',[]) if isinstance(r,dict) and r.get('stock_id')]),'missing_data_count':len(d.get('missing_data',[])) if isinstance(d.get('missing_data'),list) else None,'stale_data_count':len(d.get('stale_data',[])) if isinstance(d.get('stale_data'),list) else None,'global_freshness_status':d.get('global_freshness_status'),'sqlite_read_only':d.get('safety',{}).get('sqlite_opened_read_only') if isinstance(d.get('safety'),dict) else None,'secret_pattern_hits':len(hits),'published_summary':pub}}
    print(json.dumps(res,ensure_ascii=False,indent=2 if args.pretty else None,sort_keys=True)); return 0 if res['ok'] else 2
if __name__=='__main__': raise SystemExit(main())
