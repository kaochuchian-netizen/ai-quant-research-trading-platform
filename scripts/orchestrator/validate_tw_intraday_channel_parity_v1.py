#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from app.dashboard.multi_market_dashboard import render_tw_window_report
from app.dashboard.window_snapshot_archive import resolve_snapshots,write_snapshot
from app.reports.tw_four_window_decision import render_intraday_email,render_intraday_line
from app.runtime.operations_provenance import build_operations_provenance
from scripts.orchestrator.tw_four_window_validation_fixture import payloads
def validate():
 p=payloads()["intraday_1305"];u="/dashboard/archive/tw/intraday_1305/latest/index.html"
 with tempfile.TemporaryDirectory(prefix="ai186-parity-") as d:
  a=write_snapshot(Path(d),market="TW",window="intraday_1305",effective_trading_date=p["effective_trading_date"],generated_at=p["generated_at"],source_payload=p,status="completed",run_kind="scheduled")
  s=resolve_snapshots(Path(d),"TW","intraday_1305").latest or {};h=render_tw_window_report("intraday_1305",s.get("payload",{}));e=render_intraday_email(p,u);l=render_intraday_line(p,u)
  o=build_operations_provenance(market="TW",window="intraday_1305",runtime_status="completed",runtime_trading_date=p["effective_trading_date"],snapshot=s,public_sync={},email_result="dry_run_not_sent",line_result="dry_run_not_sent")
 q=p["tw_window_summary"]; checks={"admitted":a.get("written") is True,"dashboard_9":h.count('data-card-type="window-intraday"')==9,"same_counts":all(o.get(k)==q.get(k) for k in ("tracking_count","structured_card_count","triggered_count","invalidated_count","still_actionable_count","volume_confirmed_count")),"email_counts":str(q["still_actionable_count"]) in e,"line_counts":str(q["still_actionable_count"]) in l,"canonical_url":u in e and u in l}
 return {"ok":all(checks.values()),"checks":checks,"email_attempted":False,"line_attempted":False}
def main():
 x=argparse.ArgumentParser();x.add_argument("--pretty",action="store_true");a=x.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
