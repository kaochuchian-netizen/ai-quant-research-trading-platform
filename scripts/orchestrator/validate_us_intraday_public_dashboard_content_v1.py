#!/usr/bin/env python3
"""US intraday public-content contract; public fetch is explicit/read-only."""
from __future__ import annotations
import argparse,json,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from app.dashboard.multi_market_dashboard import render_us_window_report
from scripts.orchestrator.validate_us_intraday_2300_observed_market_binding_v1 import fixture_payload

URL="http://35.201.242.167/stock-ai-dashboard/dashboard/archive/us/us_intraday_2300/latest/index.html"
FORBIDDEN=("待盤中量價確認","等待盤中確認","待開盤")

def inspect(html:str)->dict:
    return{
        "observed_price": "Current price" in html and "334.20" in html,
        "market_time": "行情時間" in html,
        "gap": "Gap 回補" in html,
        "volume": "Volume ratio" in html,
        "trigger": "Trigger status" in html,
        "distances": "距停損" in html and "距目標" in html,
        "adjustment": "Tactical adjustment" in html and "調整原因" in html,
        "no_generic_placeholder":not any(x in html for x in FORBIDDEN),
    }

def validate(require_public:bool=False)->dict:
    local_html=render_us_window_report("us_intraday_2300",[fixture_payload()])
    checks={f"deterministic_{k}":v for k,v in inspect(local_html).items()}
    public={"required":require_public,"observed":False,"http_status":None,"checks":{}}
    if require_public:
        try:
            with urllib.request.urlopen(URL,timeout=15) as response:
                body=response.read().decode("utf-8","replace");public.update({"observed":True,"http_status":response.status,"checks":inspect(body)})
            checks["public_http_200"]=public["http_status"]==200
            checks["public_contract"]=all(public["checks"].values())
        except Exception as exc:
            public["error"]=f"{type(exc).__name__}: {str(exc)[:160]}";checks["public_http_200"]=False;checks["public_contract"]=False
    return{"ok":all(checks.values()),"checks":checks,"public":public,"url":URL,"production_modified":False}
def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");p.add_argument("--require-public",action="store_true");a=p.parse_args();r=validate(a.require_public);print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
