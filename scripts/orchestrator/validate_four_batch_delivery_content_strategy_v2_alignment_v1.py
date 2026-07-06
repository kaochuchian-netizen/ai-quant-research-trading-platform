#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,subprocess,sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'templates/four_batch_delivery_content_audit.example.json'
CONTRACT=ROOT/'templates/four_batch_delivery_content_contract.example.json'
DASH=ROOT/'templates/four_window_dashboard_route_preview.example.html'
SECRET=[re.compile(p,re.I) for p in [r'ghp_',r'github_pat_',r'sk-[A-Za-z0-9_-]{16,}',r'Bearer\s+[A-Za-z0-9._~+/=-]{16,}',r'api[_-]?key\s*[:=]',r'access[_-]?token\s*[:=]',r'password\s*[:=]',r'BEGIN (RSA|OPENSSH) PRIVATE KEY',r'\.env']]
WINDOWS=['pre_open_0700','intraday_1305','pre_close_1335','post_close_1500']; CHANNELS=['line','email','dashboard']
REQUIRED_0700=['今日最高價預測','今日最低價預測','隔天最高價預測','隔天最低價預測','未來 1 個月走勢','未來 3 個月走勢','信心分數','主要依據']
def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def run(cmd:list[str])->dict[str,Any]:
  proc=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
  try: data=json.loads(proc.stdout)
  except Exception: data={'ok':False,'raw':proc.stdout,'stderr':proc.stderr}
  data['_returncode']=proc.returncode; return data
def main()->int:
  ap=argparse.ArgumentParser(); ap.add_argument('--pretty',action='store_true'); args=ap.parse_args(); reasons=[]
  if not AUDIT.exists():
    run([sys.executable,'scripts/orchestrator/audit_today_four_batch_delivery_content_v1.py','--pretty'])
  for p in [AUDIT,CONTRACT,DASH,ROOT/'docs/four_batch_delivery_content_strategy_v2_alignment_v1.md',ROOT/'docs/runbooks/four_batch_delivery_content_strategy_v2_alignment_runbook.md']:
    if not p.exists(): reasons.append(f'missing required file: {p.relative_to(ROOT)}')
  audit=load(AUDIT) if AUDIT.exists() else {}; contract=load(CONTRACT) if CONTRACT.exists() else {}; html=DASH.read_text(encoding='utf-8') if DASH.exists() else ''
  recs=audit.get('records',[]); rows=contract.get('windows',[])
  for w in WINDOWS:
    for c in CHANNELS:
      if not any(r.get('window')==w and r.get('channel')==c for r in recs): reasons.append(f'audit missing {w}/{c}')
      if not any(r.get('window')==w and r.get('channel')==c for r in rows): reasons.append(f'contract missing {w}/{c}')
  if not any(r.get('delivery_state') in {'missing_delivery_artifact','unknown_delivery_state'} for r in recs): reasons.append('audit must explicitly support missing/unknown delivery states')
  pre=[r for r in rows if r.get('window')=='pre_open_0700']
  pre_text=json.dumps(pre,ensure_ascii=False)
  for f in REQUIRED_0700:
    if f not in pre_text: reasons.append(f'07:00 contract missing prediction field {f}')
  if '盤中分析' not in json.dumps([r for r in rows if r.get('window')=='intraday_1305'],ensure_ascii=False): reasons.append('13:05 contract missing intraday analysis')
  close_text=json.dumps([r for r in rows if r.get('window')=='pre_close_1335'],ensure_ascii=False)
  if '收盤快照 / Close Snapshot' not in close_text: reasons.append('13:35 contract missing Close Snapshot label')
  if '完整檢討待 15:00' not in close_text: reasons.append('13:35 contract must defer full review to 15:00')
  if '收盤前' in close_text or 'Pre-close' in close_text: reasons.append('13:35 primary contract contains forbidden pre-close wording')
  if '過去 7 天預測命中率' not in json.dumps([r for r in rows if r.get('window')=='post_close_1500'],ensure_ascii=False): reasons.append('15:00 contract missing 7-day rolling review')
  for c,phrase in [('line','短摘要'),('email','完整報告'),('dashboard','完整資料狀態')]:
    if phrase not in json.dumps(contract.get('channel_policies',{}).get(c,{}),ensure_ascii=False): reasons.append(f'{c} channel policy not differentiated')
  for phrase in ['資料待接','不產生假預測']:
    if phrase not in json.dumps(contract,ensure_ascii=False)+html: reasons.append(f'missing fallback phrase: {phrase}')
  for phrase in ['LINE / Email / Dashboard delivery audit summary','今日最高價預測','今日最低價預測','隔天最高價預測','隔天最低價預測','未來 1 個月走勢','未來 3 個月走勢','收盤快照','完整檢討待 15:00']:
    if phrase not in html: reasons.append(f'dashboard html missing {phrase}')
  main_html=html.split('技術檢查 / Debug')[0]
  if 'Pre-close' in main_html or '收盤前' in main_html: reasons.append('primary dashboard html contains forbidden 13:35 wording')
  for bad in ['Traceback (most recent call last)','Response Code:','APISUB/']:
    if bad in main_html: reasons.append(f'user-facing dashboard contains raw log marker {bad}')
  all_text=json.dumps(contract,ensure_ascii=False)+json.dumps(audit,ensure_ascii=False)+html
  for p in SECRET:
    if p.search(all_text): reasons.append(f'secret-like pattern found: {p.pattern}')
  safety=contract.get('safety_policy',{})
  for k in ['db_write','scheduler_modified','line_email_notification_sent','production_pipeline_executed','python_main_executed','trading_or_order_executed','production_rating_action_confidence_weight_mutated','fabricated_forecast_values']:
    if safety.get(k) is not False: reasons.append(f'safety {k} must be false')
  result={'ok':True,'passed':not reasons,'audit_records':len(recs),'contract_rows':len(rows),'reasons':reasons,'checks':{'four_windows':WINDOWS,'channels':CHANNELS,'line_email_dashboard_differentiated':True,'missing_prediction_fallback':'資料待接','no_fabricated_forecast_values':True},'side_effects':{'db_write':False,'scheduler_modified':False,'line_email_notification_sent':False,'production_pipeline_executed':False,'python_main_executed':False,'trading_or_order_executed':False}}
  json.dump(result,sys.stdout,ensure_ascii=False,indent=2 if args.pretty else None,sort_keys=True); sys.stdout.write('\n'); return 0 if result['passed'] else 2
if __name__=='__main__': raise SystemExit(main())
