#!/usr/bin/env python3
"""Read-only audit of existing JSON artifacts for safe window snapshot backfill."""
from __future__ import annotations
import argparse, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SKIP=(ROOT/"artifacts/archive/window_snapshots").resolve()
WINDOWS={"pre_open_0700":"TW","intraday_1305":"TW","pre_close_1335":"TW","post_close_1500":"TW","prediction_review_1500":"TW","us_pre_market_2000":"US","us_intraday_2300":"US","us_post_close_review_0630":"US","us_review_0630":"US"}
def main()->int:
 p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args(); admitted=[]; rejected=[]
 for path in sorted((ROOT/"artifacts").rglob("*.json")):
  if SKIP in path.resolve().parents: continue
  try: data=json.loads(path.read_text(encoding="utf-8"))
  except Exception: continue
  if not isinstance(data,dict): continue
  window=str(data.get("window") or data.get("scheduler_window") or data.get("window_context",{}).get("scheduler_window") or "")
  if window not in WINDOWS: continue
  market=str(data.get("market") or data.get("window_context",{}).get("market") or WINDOWS[window]).upper()
  trading_date=data.get("effective_trading_date") or data.get("trading_date")
  schema=data.get("schema_version")
  reasons=[]
  if not schema: reasons.append("schema_not_identifiable")
  if market not in {"TW","US"}: reasons.append("market_not_identifiable")
  if not trading_date: reasons.append("effective_trading_date_not_proven")
  mode=" ".join(str(data.get(k) or "") for k in ("artifact_type","artifact_mode","runtime_mode","data_source_mode","run_kind")).lower()
  if data.get("fixture") or data.get("validation_only") or "fixture" in mode or "validator" in mode: reasons.append("fixture_or_validation")
  item={"path":str(path.relative_to(ROOT)),"market":market,"window":window,"schema_version":schema,"effective_trading_date":trading_date}
  if reasons: item["reasons"]=sorted(set(reasons)); rejected.append(item)
  else: admitted.append(item)
 out={"schema_version":"window_snapshot_backfill_audit_v1","task_id":"AI-DEV-179","read_only":True,"backfill_performed":False,"admission_candidate_count":len(admitted),"rejected_count":len(rejected),"admission_candidates":admitted,"rejected":rejected,"policy":"No backfill unless market, canonical window, effective trading date, schema, completion, and non-fixture provenance are proven."}
 print(json.dumps(out,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
