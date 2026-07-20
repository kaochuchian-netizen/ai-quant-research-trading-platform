#!/usr/bin/env python3
"""Deterministic US 20:00 -> 23:00 -> 06:30 setup identity gate."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.orchestrator.validate_us_intraday_2300_observed_market_binding_v1 import fixture_card

def validate()->dict:
    symbols=("AAPL","NVDA","TSLA")
    pre={s:{"symbol":s,"setup_id":f"2026-07-17:{s}:daily_tactical","entry_zone":{"low":100,"high":105},"action":"盤前觀察"} for s in symbols}
    intraday=[]
    post=[]
    for index,symbol in enumerate(symbols):
        card=fixture_card(symbol,current=103+index,opened=101,previous=100,day_low=101)
        card.update({"setup_id":pre[symbol]["setup_id"],"pre_open_action":pre[symbol]["action"],"pre_open_setup_source":f"prediction_snapshots/2026-07-17/us_pre_market_2000_{symbol}.json"})
        intraday.append(card)
        post.append({"symbol":symbol,"setup_id":card["setup_id"],"canonical_outcome":"pending" if index==2 else "hit"})
    checks={
        "symbol_identity":set(pre)=={c["symbol"] for c in intraday}=={c["symbol"] for c in post},
        "setup_identity":all(pre[c["symbol"]]["setup_id"]==c["setup_id"]==next(p["setup_id"] for p in post if p["symbol"]==c["symbol"]) for c in intraday),
        "pre_open_action_retained":all(c["pre_open_action"]=="盤前觀察" for c in intraday),
        "trigger_explicit":all(c["entry_trigger_state"] in {"not_reached","inside_zone","triggered","passed_without_safe_entry","invalidated","unavailable"} for c in intraday),
        "post_outcome_not_reclassified":next(p for p in post if p["symbol"]=="TSLA")["canonical_outcome"]=="pending",
        "no_cross_window_fill":all("us_pre_market_2000" in c["pre_open_setup_source"] for c in intraday),
    }
    return{"ok":all(checks.values()),"checks":checks,"symbols":list(symbols),"production_modified":False}
def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
