#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys
from datetime import datetime
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'templates/four_batch_delivery_content_audit.example.json'
PUBLIC_URL='http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html'
WINDOWS=['pre_open_0700','intraday_1305','pre_close_1335','post_close_1500']
CHANNELS=['line','email','dashboard']
SECRET=[re.compile(p,re.I) for p in [r'ghp_',r'github_pat_',r'sk-[A-Za-z0-9_-]{16,}',r'Bearer\s+[A-Za-z0-9._~+/=-]{16,}',r'api[_-]?key\s*[:=]',r'access[_-]?token\s*[:=]',r'password\s*[:=]',r'BEGIN (RSA|OPENSSH) PRIVATE KEY',r'\.env']]
REQUIRED={
  'pre_open_0700':['台股盤前預測','今日最高價預測','今日最低價預測','隔天最高價預測','隔天最低價預測','未來 1 個月走勢','未來 3 個月走勢','信心分數','主要依據','風險提醒','台指期夜盤觀察','美股盤後摘要狀態','Dashboard URL'],
  'intraday_1305':['盤中分析','目前價格狀態','是否接近今日預測高低區間','成交量','盤前假設是否仍有效','風險提醒','Dashboard URL'],
  'pre_close_1335':['收盤快照','今日高 / 低 / 收盤狀態','與 07:00 預測區間的初步比對','完整檢討待 15:00','Dashboard URL'],
  'post_close_1500':['盤後檢討','過去 7 天預測命中率','今日 forecast vs actual','高低價預測誤差','方向判斷命中','confidence calibration','factor effectiveness','Dashboard URL'],
}
def stable(x:Any)->str: return json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
def read(path:Path)->str:
  try: return path.read_text(encoding='utf-8',errors='ignore')
  except OSError: return ''
def sha(text:str)->str|None: return hashlib.sha256(text.encode('utf-8')).hexdigest() if text else None
def secret_hits(text:str)->list[str]: return [p.pattern for p in SECRET if p.search(text)]
def detect(text:str, window:str)->tuple[list[str],list[str]]:
  found=[]
  for sec in REQUIRED[window]:
    if sec in text or sec.replace(' / ','/') in text: found.append(sec)
  missing=[s for s in REQUIRED[window] if s not in found]
  return found, missing
def dashboard_text()->tuple[str,str|None,str|None]:
  path=ROOT/'templates/four_window_dashboard_route_preview.example.html'
  text=read(path)
  manifest=Path('/var/www/stock-ai-dashboard/.ai_dev_145_publish_results/latest.json')
  ts=None
  if manifest.exists():
    try: ts=json.loads(read(manifest)).get('published_at')
    except Exception: ts=None
  return text, str(path.relative_to(ROOT)), ts
def channel_source(channel:str, window:str)->tuple[str,str|None,str|None,str]:
  if channel=='dashboard':
    text,path,ts=dashboard_text(); return text,path,ts,'published' if text else 'missing_delivery_artifact'
  # LINE/Email are external delivery channels. Do not infer actual sent content
  # from generic templates or logs; report unknown explicitly when no safe
  # delivery result artifact exists.
  if channel in {'line','email'}:
    return '', None, None, 'unknown_delivery_state'
  return '', None, None, 'missing_delivery_artifact'
def build()->dict[str,Any]:
  records=[]
  for w in WINDOWS:
    for ch in CHANNELS:
      text,path,ts,state=channel_source(ch,w)
      found,missing=detect(text,w) if text else ([], REQUIRED[w])
      records.append({'window':w,'channel':ch,'sent_or_published':state=='published','delivery_state':state,'timestamp':ts,'source_artifact':path,'content_hash':sha(text),'detected_sections':found,'missing_sections':missing,'contains_prediction_fields':all(s in text for s in ['今日最高價預測','今日最低價預測','隔天最高價預測','隔天最低價預測','未來 1 個月走勢','未來 3 個月走勢']) if text else False,'contains_same_day_high_low':all(s in text for s in ['今日最高價預測','今日最低價預測']) if text else False,'contains_next_day_high_low':all(s in text for s in ['隔天最高價預測','隔天最低價預測']) if text else False,'contains_1m_trend':'未來 1 個月走勢' in text if text else False,'contains_3m_trend':'未來 3 個月走勢' in text if text else False,'contains_dashboard_url':PUBLIC_URL in text if text else False,'contains_raw_logs':any(b in (text.split('技術檢查 / Debug')[0] if ch=='dashboard' else text) for b in ['Traceback (most recent call last)','Response Code:','APISUB/','SQLite 已寫入']) if text else False,'contains_secret_like_text':bool(secret_hits(text)) if text else False,'notes':['channel could not be verified; explicit missing/unknown state retained'] if state!='published' else []})
  return {'schema_version':'four_batch_delivery_content_audit_v1','task_id':'AI-DEV-149','generated_at':datetime.now().replace(microsecond=0).isoformat(),'audit_scope':'read-only local artifacts; no LINE/Email resend; no DB write','public_dashboard_url':PUBLIC_URL,'records':records,'summary':{'record_count':len(records),'dashboard_published_records':len([r for r in records if r['channel']=='dashboard' and r['sent_or_published']]),'missing_delivery_artifact_count':len([r for r in records if r['delivery_state']=='missing_delivery_artifact']),'unknown_delivery_state_count':len([r for r in records if r['delivery_state']=='unknown_delivery_state']),'secret_like_record_count':len([r for r in records if r['contains_secret_like_text']]),'raw_log_record_count':len([r for r in records if r['contains_raw_logs']])},'safety':{'db_write':False,'scheduler_modified':False,'line_email_notification_sent':False,'production_pipeline_executed':False,'python_main_executed':False,'trading_or_order_executed':False,'secrets_read':False}}
def main():
  ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=OUT); ap.add_argument('--pretty',action='store_true'); args=ap.parse_args(); data=build(); args.output.write_text(stable(data),encoding='utf-8'); print(stable({'ok':True,'output':str(args.output),'records':len(data['records']),'summary':data['summary']}),end='')
if __name__=='__main__': main()
