#!/usr/bin/env python3
"""Validate the AI-DEV-051 Dify review package runtime result package."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/ai_dev_051_dify_review_package_runtime_result.md'
TPL=ROOT/'templates/ai_dev_051_dify_review_package_runtime_result.example.json'
RELATED=[ROOT/'docs/ai_dev_one_shot_multi_agent_automation.md',ROOT/'docs/ai_task_queue_runbook.md']
PATTERNS={
 'github_pat':re.compile(r'github_pat_[A-Za-z0-9_]+'),
 'ghp':re.compile(r'ghp_[A-Za-z0-9_]+'),
 'sk':re.compile(r'sk-[A-Za-z0-9_-]{12,}'),
 'bearer_value':re.compile(r'Bearer\s+[A-Za-z0-9._~+/=-]{8,}',re.I),
 'api_key_assignment':re.compile(r'api[-_]?key["\'\s:=]+[A-Za-z0-9._~+/=-]{8,}',re.I),
 'token_assignment':re.compile(r'token["\'\s:=]+[A-Za-z0-9._~+/=-]{8,}',re.I),
 'private_key':re.compile(r'BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY')}
REQ=['task_id','dry_run','runtime_dry_run','dify_runtime_attempted','dify_runtime_called','fallback_used','n8n_started','n8n_stopped','chatgpt_openai_api_secret_read','notification_sent','production_db_modified','cron_or_timer_modified','main_py_executed','trading_executed','no_secret_values','local_only_outputs','secret_scan_summary','review_package','ai_dev_052_executed']
OUT=['dify_review_input','dify_runtime_result','chatgpt_ready_report','runtime_summary']
REV=['task_summary','implementation_summary','validation_summary','pr_gate_summary','safety_summary','blockers','next_action_recommendation']
def main():
 p=argparse.ArgumentParser(); p.add_argument('--pretty',action='store_true'); a=p.parse_args(); errors=[]; warnings=[]
 files={str(x.relative_to(ROOT)):x.exists() for x in [DOC,TPL,*RELATED]}
 for k,v in files.items():
  if not v: errors.append(f'missing required file: {k}')
 data={}
 if TPL.exists():
  try: data=json.loads(TPL.read_text())
  except Exception as e: errors.append(f'template JSON parse failed: {e}')
 for k in REQ:
  if k not in data: errors.append(f'missing required key: {k}')
 for k in ['dry_run','runtime_dry_run','dify_runtime_attempted','n8n_started','n8n_stopped','no_secret_values']:
  if data.get(k) is not True: errors.append(f'{k} must be true')
 for k in ['chatgpt_openai_api_secret_read','notification_sent','production_db_modified','trading_executed','ai_dev_052_executed']:
  if data.get(k) is not False: errors.append(f'{k} must be false')
 if data.get('dify_runtime_called') is True and data.get('safe_dify_review_mapping_found') is not True: errors.append('dify_runtime_called requires safe_dify_review_mapping_found')
 if data.get('dify_runtime_called') is False and data.get('fallback_used') is not True: errors.append('fallback_used must be true when Dify runtime was not called')
 lo=data.get('local_only_outputs',{})
 if not isinstance(lo,dict): errors.append('local_only_outputs must be object')
 else:
  for k in OUT:
   if k not in lo: errors.append(f'missing local_only_outputs.{k}')
 rp=data.get('review_package',{})
 if not isinstance(rp,dict): errors.append('review_package must be object')
 else:
  for k in REV:
   if k not in rp: errors.append(f'missing review_package.{k}')
 scan=data.get('secret_scan_summary',{})
 if not isinstance(scan,dict): errors.append('secret_scan_summary must be object')
 else:
  if scan.get('secret_values_printed') is not False: errors.append('secret values printed must be false')
  if scan.get('values_included') is not False: errors.append('secret values included must be false')
 text='\n'.join(x.read_text(errors='replace') for x in [DOC,TPL,*RELATED] if x.exists())
 hits={n:len(r.findall(text)) for n,r in PATTERNS.items()}
 for n,c in hits.items():
  if c: errors.append(f'forbidden secret-like value pattern found: {n} ({c})')
 doc=DOC.read_text(errors='replace') if DOC.exists() else ''
 for phrase in ['fallback/readiness','Dify runtime call was intentionally skipped','No credential or node parameter inspection','AI-DEV-052','local-only runtime artifacts']:
  if phrase not in doc: errors.append(f'document missing required phrase: {phrase}')
 result={'ok':not errors,'passed':not errors,'file_checks':files,'task_id':data.get('task_id'),'runtime_state':{'dify_runtime_attempted':data.get('dify_runtime_attempted'),'dify_runtime_called':data.get('dify_runtime_called'),'fallback_used':data.get('fallback_used'),'n8n_started':data.get('n8n_started'),'n8n_stopped':data.get('n8n_stopped'),'notification_sent':data.get('notification_sent'),'production_db_modified':data.get('production_db_modified'),'trading_executed':data.get('trading_executed'),'ai_dev_052_executed':data.get('ai_dev_052_executed')},'secret_scan_summary':data.get('secret_scan_summary'),'secret_value_pattern_hits':hits,'errors':errors,'warnings':warnings,'side_effects':{'files_modified':False,'n8n_started':False,'dify_called':False,'chatgpt_openai_api_called':False,'notification_sent':False,'runtime_queue_modified':False,'production_db_modified':False,'trading_execution_run':False}}
 print(json.dumps(result,indent=2 if a.pretty else None,ensure_ascii=False)); return 0 if result['ok'] else 1
if __name__=='__main__': raise SystemExit(main())
