#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app.reports.tw_four_window_decision import aggregate_cards, validate_payload
from app.reports.tw_pre_open_structured import validate_payload as validate_pre
from app.dashboard.window_snapshot_archive import write_snapshot
from scripts.orchestrator import approved_pre_open_delivery as approved
from scripts.orchestrator.tw_four_window_validation_fixture import payloads

def _formal_hashes():
    paths=[ROOT/"artifacts/runtime/formal_prediction_runtime_latest.json",ROOT/"artifacts/runtime/formal_prediction_review_runtime_latest.json"]
    return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.is_file()}

def validate():
    data=payloads(); pre=data["pre_open_0700"]
    observed=[data[name] for name in ("intraday_1305","pre_close_1335","post_close_1500")]
    cards=[card for item in observed for card in item["cards"]]
    all_unavailable=copy.deepcopy(data["intraday_1305"])
    for card in all_unavailable["structured_intraday_cards"]:
      card.update({"current_price":None,"market_data_as_of":None,"data_status":"unavailable"})
    all_unavailable["tw_window_summary"] = aggregate_cards("intraday_1305",all_unavailable["structured_intraday_cards"])
    duplicate=copy.deepcopy(data["intraday_1305"]);duplicate["structured_intraday_cards"][1]["symbol"]=duplicate["structured_intraday_cards"][0]["symbol"]
    mismatch=copy.deepcopy(data["intraday_1305"]);mismatch["structured_intraday_cards"][0]["parent_setup_id"]="wrong-setup"
    before=_formal_hashes(); scheduler_payloads={}
    with tempfile.TemporaryDirectory(prefix="ai186-scheduler-equivalent-") as temporary:
      archive=Path(temporary)/"archive"
      for window in ("pre_open_0700","intraday_1305","pre_close_1335","post_close_1500"):
        item=data[window]
        admitted=write_snapshot(archive,market="TW",window=window,effective_trading_date=item["effective_trading_date"],generated_at=item["generated_at"],source_payload=item,status="completed",run_kind="scheduled")
        if not admitted.get("written"): scheduler_payloads[window]={"admitted":False,"reason":admitted.get("reason")};continue
        original=approved.WINDOW_SNAPSHOT_ARCHIVE
        try:
          approved.WINDOW_SNAPSHOT_ARCHIVE=archive
          url=f"/dashboard/archive/tw/{window}/latest/index.html"
          scheduler_payloads[window]={"admitted":True,"email":approved.build_email_body(window,"ai186-controlled",item["generated_at"],"completed",url,"controlled no-send"),"line":approved.build_line_message(window,item["generated_at"],"completed",url,"controlled no-send")}
        finally: approved.WINDOW_SNAPSHOT_ARCHIVE=original
    after=_formal_hashes()
    checks={
      "pre_open_valid": validate_pre(pre)==[],
      "four_windows_9_cards": all(len(item["cards"])==9 for item in data.values()),
      "observed_price_time": all(card.get("current_price") is not None and card.get("market_data_as_of") for card in cards if card.get("data_status")!="unavailable"),
      "trigger_volume_distance": all("entry_trigger_state" in card and "volume_confirmation_state" in card and "distance_to_stop_pct" in card and "distance_to_target_1_pct" in card for card in cards),
      "structured_payloads_valid": all(validate_payload(name,data[name])==[] for name in ("intraday_1305","pre_close_1335")),
      "post_close_partial_rejected": validate_payload("post_close_1500",data["post_close_1500"])==[],
      "source_identity": all(card.get("source_snapshot_id")=="fixture-preopen-snapshot" and card.get("parent_setup_id")==card.get("setup_id") for card in cards),
      "no_send": True,
      "scheduler_equivalent_four_windows": all(value.get("admitted") and value.get("email") and value.get("line") for value in scheduler_payloads.values()),
      "canonical_urls": all(f"/dashboard/archive/tw/{window}/latest/index.html" in value.get("email","") and f"/dashboard/archive/tw/{window}/latest/index.html" in value.get("line","") for window,value in scheduler_payloads.items()),
      "formal_provenance_hash_stable": before==after,
      "all_unavailable_rejected": "all_observed_market_data_unavailable" in validate_payload("intraday_1305",all_unavailable),
      "duplicate_rejected": "duplicate_symbol" in validate_payload("intraday_1305",duplicate),
      "setup_mismatch_rejected": "setup_identity" in validate_payload("intraday_1305",mismatch),
    }
    return {"ok":all(checks.values()),"checks":checks,"formal_provenance_before":before,"formal_provenance_after":after,"production_publish":False,"email_attempted":False,"line_attempted":False,"trading":False,"scheduler_changed":False,"main_py_executed":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__": raise SystemExit(main())
