#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS
from app.us_stock.intraday_observed import DATA_STATES,ENTRY_STATES,SCHEMA_VERSION
from app.reports.canonical_outcomes import CANONICAL_OUTCOMES
from scripts.orchestrator.tw_four_window_validation_fixture import payloads
def validate():
 p=payloads();checks={"seven_routes":sum(len(v) for v in MARKET_WINDOWS.values())==7,"tw_four":set(p)==set(MARKET_WINDOWS["TW"]),"us_intraday_schema":SCHEMA_VERSION=="us_intraday_observed_market_v1","us_session_contract":"market_closed" in DATA_STATES and "triggered" in ENTRY_STATES,"us_outcome_exclusive":set(CANONICAL_OUTCOMES)=={"hit","fail","not_triggered","no_trade","pending"},"tw_counts":all(x["tracking_stock_count"]==len(x["cards"])==9 for x in p.values())}
 return {"ok":all(checks.values()),"checks":checks,"changed_contracts":["TW pre_open_0700","TW intraday_1305","TW pre_close_1335","TW post_close_1500"],"unchanged_contracts":["US 20:00","US 23:00","US 06:30"]}
def main():
 p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
