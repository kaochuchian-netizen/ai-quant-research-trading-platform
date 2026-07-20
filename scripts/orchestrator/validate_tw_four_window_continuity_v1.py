#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.orchestrator.tw_four_window_validation_fixture import SYMBOLS,payloads
def validate():
 p=payloads(); maps={w:{(c.get("symbol") or c.get("stock_id")):c for c in x["cards"]} for w,x in p.items()};checks={}
 checks["symbol_sets"]=all(set(m)==set(SYMBOLS) for m in maps.values())
 checks["setup_identity"]=all(len({maps[w][s].get("setup_id") for w in maps})==1 for s in SYMBOLS)
 checks["parent_identity"]=all(maps[w][s].get("parent_setup_id")==maps["pre_open_0700"][s].get("setup_id") for w in ("intraday_1305","pre_close_1335","post_close_1500") for s in SYMBOLS)
 checks["levels_stable"]=all(len({(maps[w][s].get("entry_low"),maps[w][s].get("entry_high"),maps[w][s].get("stop_level"),maps[w][s].get("target_1")) for w in maps})==1 for s in SYMBOLS)
 return {"ok":all(checks.values()),"checks":checks,"symbols":SYMBOLS}
def main():
 p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
