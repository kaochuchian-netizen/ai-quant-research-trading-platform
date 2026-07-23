#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.orchestrator.tw_four_window_validation_fixture import payloads
def validate():
 p=payloads()["pre_close_1335"];c=p["structured_pre_close_cards"];q=p["tw_window_summary"]
 checks={"market_time":all(x.get("market_data_as_of") for x in c),"proximity_deterministic":all(isinstance(x.get("near_stop"),bool) and isinstance(x.get("near_target"),bool) for x in c),"same_setup":all(x.get("setup_id")==x.get("parent_setup_id") and x.get("source_snapshot_id") for x in c),"priority_subset":0<len(q["priority_symbols"])<len(c),"priority_groups":all(k in q["priority_groups"] for k in ("hold","hold_with_protection","watch","reduce","exit","no_trade")),"partition_complete":sum(q["overnight_action_counts"].values())==len(c)}
 return {"ok":all(checks.values()),"checks":checks}
def main():
 p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
