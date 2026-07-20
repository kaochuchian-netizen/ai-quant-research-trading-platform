#!/usr/bin/env python3
"""Admission safety matrix for observed US intraday cards."""
from __future__ import annotations
import argparse, copy, json, sys, tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app.dashboard.window_snapshot_archive import write_snapshot
from app.us_stock.intraday_observed import resolve_market_session, validate_intraday_payload
from scripts.orchestrator.validate_us_intraday_2300_observed_market_binding_v1 import fixture_card, fixture_payload

def admit(root: Path, payload: dict, date: str) -> dict:
    return write_snapshot(root,market="US",window="us_intraday_2300",effective_trading_date=date,generated_at=f"{date}T23:01:00+08:00",source_payload=payload,status="completed",run_kind="scheduled")

def validate() -> dict:
    good=fixture_card()
    unavailable=copy.deepcopy(good); unavailable.update({"symbol":"FAIL","current_price":None,"market_data_as_of":None,"entry_trigger_state":"unavailable","tactical_adjustment":"data_unavailable","data_status":"unavailable","missing_fields":["current_price","market_data_as_of"]})
    partial=fixture_payload([good,unavailable])
    all_bad=fixture_payload([unavailable])
    stale=copy.deepcopy(unavailable); stale.update({"symbol":"STALE","current_price":120.0,"market_data_as_of":"2026-07-17T09:30:00-04:00","data_status":"stale"})
    all_stale=fixture_payload([stale])
    closed=fixture_payload([copy.deepcopy(unavailable)])
    closed["session_context"]={**resolve_market_session(datetime(2026,7,18,23,0,tzinfo=ZoneInfo("Asia/Taipei"))),"reference_taipei":"2026-07-18T23:00:00+08:00"}
    closed["structured_intraday_cards"][0]["data_status"]="market_closed"
    closed["structured_intraday_cards"][0]["session_phase"]="market_closed"
    with tempfile.TemporaryDirectory(prefix="ai185-admission-") as tmp:
        root=Path(tmp)
        partial_result=admit(root,partial,"2026-07-17")
        all_bad_result=admit(root,all_bad,"2026-07-18")
        stale_result=admit(root,all_stale,"2026-07-19")
        closed_result=admit(root,closed,"2026-07-20")
    checks={
        "partial_retains_all_symbols":len(partial["structured_intraday_cards"])==2 and {c["symbol"] for c in partial["structured_intraday_cards"]}=={"AAPL","FAIL"},
        "partial_admitted":partial_result.get("written") is True,
        "all_unavailable_rejected":all_bad_result.get("written") is False and all_bad_result.get("reason")=="intraday_market_data_all_unavailable",
        "all_stale_rejected":stale_result.get("written") is False,
        "market_closed_not_complete":closed_result.get("written") is True and closed["structured_intraday_cards"][0]["data_status"]=="market_closed",
        "validation_reason_retained":"all_intraday_market_data_unavailable" in validate_intraday_payload(all_bad),
        "no_cross_symbol_fill":partial["structured_intraday_cards"][1]["current_price"] is None,
    }
    return {"ok":all(checks.values()),"checks":checks,"partial":partial_result,"all_unavailable":all_bad_result,"stale":stale_result,"market_closed":closed_result,"production_modified":False}

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
