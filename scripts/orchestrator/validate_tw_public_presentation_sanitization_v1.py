#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from app.dashboard.multi_market_dashboard import render_tw_window_report
from app.reports.tw_pre_open_structured import render_email,render_line
from scripts.orchestrator.tw_four_window_validation_fixture import payloads
def validate():
 p=payloads();url="/dashboard/archive/tw/pre_open_0700/latest/index.html";texts=[render_email(p["pre_open_0700"],url),render_line(p["pre_open_0700"],url)]+[render_tw_window_report(w,x) for w,x in p.items()]
 joined="\n".join(texts);forbidden=("Gemini Error","DEADLINE_EXCEEDED","datetime.date(","datetime.datetime(","[None, None]","資料待接","{'error':",'["2330", "2337"]')
 checks={"no_forbidden":not any(x in joined for x in forbidden),"sanitized_provider_failure":"新聞分析暫時無法取得" in joined,"internal_enum_localized":">sideways<" not in joined and ">wait<" not in joined and ">pending<" not in joined,"no_raw_none":">None<" not in joined}
 return {"ok":all(checks.values()),"checks":checks,"forbidden_hits":[x for x in forbidden if x in joined]}
def main():
 p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
