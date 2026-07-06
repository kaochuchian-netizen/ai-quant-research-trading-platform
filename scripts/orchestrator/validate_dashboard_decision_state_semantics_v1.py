#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[2]
HTML=ROOT/'templates/four_window_dashboard_route_preview.example.html'
PUBLIC='http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html'
SECRET=[re.compile(p,re.I) for p in [r'ghp_',r'github_pat_',r'sk-[A-Za-z0-9_-]{16,}',r'Bearer\s+[A-Za-z0-9._~+/=-]{16,}',r'api[_-]?key\s*[:=]',r'access[_-]?token\s*[:=]',r'password\s*[:=]',r'BEGIN (RSA|OPENSSH) PRIVATE KEY',r'\.env']]
REQUIRED=['部分資料可用；正式預測與檢討資料待接','盤前摘要：可用','每日股價預測：資料待接','部分缺資料','盤中追蹤：資料待接','尚未找到正式盤中 runtime artifact','收盤快照 / Close Snapshot','完整檢討待 15:00','盤後檢討：資料待接','7 天滾動檢討：資料待接','目前僅找到盤前本機摘要，不能代表盤後檢討資料','追蹤名單有效','範例 artifact，不是正式最新報告','每日股價預測資料狀態','今日最高 / 最低價預測','隔天最高 / 最低價預測','未來 1 個月走勢','未來 3 個月走勢','信心分數','主要依據','今日實際最高價','今日實際最低價','今日收盤價','方向判斷結果','高低價預測誤差','命中 / 未命中','過去 7 天命中率','信心校準','因子有效性','錯誤原因','明日改善建議','07:00 盤前資料','13:05 盤中資料','13:35 收盤快照資料','15:00 盤後檢討資料','LINE','未驗證實際送達內容','Dashboard','已發布並可驗證']
RAW_MAIN=['runtime_window / pre_open_0700','stock_universe / 2330','latest_report / 0','prediction_fields / same_day_high_low','actual_high','hit_miss_status','factor_effectiveness']
def read_html(published:bool)->str:
  if published:
    with urlopen(PUBLIC,timeout=10) as r: return r.read().decode('utf-8','ignore')
  return HTML.read_text(encoding='utf-8')
def main():
  ap=argparse.ArgumentParser(); ap.add_argument('--pretty',action='store_true'); ap.add_argument('--published',action='store_true'); args=ap.parse_args(); errors=[]; text=read_html(args.published); main_text=text.split('技術檢查 / Debug')[0]
  for phrase in REQUIRED:
    if phrase not in text: errors.append(f'missing required phrase: {phrase}')
  if '資料正常' in main_text: errors.append('main UI must not use generic 資料正常')
  if 'fresh' in main_text: errors.append('main UI must not show raw fresh state')
  if '收盤前' in main_text or 'Pre-close' in main_text: errors.append('main UI contains forbidden 13:35 wording')
  for raw in RAW_MAIN:
    if raw in main_text: errors.append(f'raw technical key leaked in main UI: {raw}')
  for bad in ['Traceback (most recent call last)','Response Code:','APISUB/','SQLite 已寫入']:
    if bad in main_text: errors.append(f'raw log marker in main UI: {bad}')
  for p in SECRET:
    if p.search(text): errors.append(f'secret-like pattern found: {p.pattern}')
  safety={'db_write':False,'scheduler_modified':False,'line_email_notification_sent':False,'production_pipeline_executed':False,'python_main_executed':False,'trading_or_order_executed':False,'production_rating_action_confidence_weight_mutated':False}
  result={'ok':not errors,'published_mode':args.published,'errors':errors,'summary':{'main_ui_decision_state':'部分資料可用；正式預測與檢討資料待接','stock_wording':'追蹤名單有效','prediction_missing_state':'正式預測資料待接','review_missing_state':'盤後檢討資料待接','secret_pattern_hits':0 if not errors else None},'safety':safety}
  json.dump(result,sys.stdout,ensure_ascii=False,indent=2 if args.pretty else None,sort_keys=True); sys.stdout.write('\n'); return 0 if result['ok'] else 2
if __name__=='__main__': raise SystemExit(main())
