#!/usr/bin/env python3
"""Validate read-only Production Operations archive health presentation."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app.dashboard.multi_market_dashboard import WINDOW_SNAPSHOT_ARCHIVE, render_landing_page
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots
def main()->int:
 p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args(); html=render_landing_page(); checks={}
 checks["operations_center_present"]='id="production-operations-center"' in html
 checks["latest_revision_previous_columns"] = all(token in html for token in ("Latest","Revision","Previous"))
 checks["seven_window_rows"] = html.count('<tr data-market=')==7
 stable=True
 inventory=[]
 for market,windows in MARKET_WINDOWS.items():
  for window in windows:
   selected=resolve_snapshots(WINDOW_SNAPSHOT_ARCHIVE,market,window)
   if selected.latest and selected.previous:
    stable &= selected.latest["effective_trading_date"] != selected.previous["effective_trading_date"]
   inventory.append({"market":market,"window":window,"latest":selected.latest.get("effective_trading_date") if selected.latest else None,"revision":selected.latest.get("revision") if selected.latest else None,"previous":selected.previous.get("effective_trading_date") if selected.previous else None})
 checks["previous_distinct_trading_date"] = stable
 errors=[k for k,v in checks.items() if not v]; out={"schema_version":"production_batch_health_validation_v1","task_id":"AI-DEV-180","ok":not errors,"errors":errors,"checks":checks,"inventory":inventory,"read_only":True,"safety":{"notification_sent":False,"production_pipeline_executed":False,"scheduler_changed":False,"trading":False,"python3_main_executed":False,"secrets_accessed":False}}
 print(json.dumps(out,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True)); return 0 if out["ok"] else 1
if __name__=="__main__": raise SystemExit(main())
