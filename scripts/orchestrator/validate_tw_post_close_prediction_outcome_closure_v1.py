#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.orchestrator.tw_four_window_validation_fixture import payloads
def validate():
 p=payloads()["post_close_1500"];c=p["structured_review_cards"];q=p["tw_window_summary"];oc=q["outcome_counts"]
 checks={"prediction_traceable":all(x.get("prediction_source_window")=="pre_open_0700" and x.get("prediction_snapshot_id") for x in c),"actual_ohlc":sum(x.get("actual_status")=="complete" for x in c)==8,"canonical_outcomes":sum(oc.values())==9 and set(oc)=={"hit","fail","not_triggered","no_trade","pending"},"mfe_mae":all("mfe_pct" in x and "mae_pct" in x for x in c),"review_semantics":q["completed_review_count"]+q["pending_review_count"]==q["review_universe_count"]==9,"not_all_pending":oc["pending"]<9,"no_none_range":all(x.get("review_snapshot",{}).get("actual_range")!={"low":None,"high":None} for x in c if x.get("actual_status")=="complete")}
 return {"ok":all(checks.values()),"checks":checks,"outcomes":oc}
def main():
 p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
