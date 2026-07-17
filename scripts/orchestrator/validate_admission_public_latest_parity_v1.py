#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, tempfile, sys
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from app.dashboard import public_latest_sync as sync_module
from app.dashboard import multi_market_dashboard as dashboard_module
from app.dashboard.public_latest_sync import synchronize_admitted_latest, verify_identity
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, write_snapshot
from app.reports.delivery_provenance import build_delivery_provenance

def validate() -> dict:
    rows=[]
    with tempfile.TemporaryDirectory(prefix="ai183-public-") as tmp:
        root=Path(tmp)/"public"; build=Path(tmp)/"build"
        for market, windows in MARKET_WINDOWS.items():
            for window in windows:
                result=synchronize_admitted_latest(market=market, window=window, static_root=root, output_dir=build/market/window)
                rows.append({"market":market,"window":window,"status":result.get("status")})
        expected={"market":"TW","window":"intraday_1305","effective_trading_date":"2099-01-01","snapshot_id":"expected","revision":1,"payload_hash":"expected"}
        mismatch_path=root/"mismatch.html"; mismatch_path.write_text('<body data-market="TW"></body>',encoding="utf-8")
        mismatch=verify_identity(expected,mismatch_path)
        controlled_archive=Path(tmp)/"controlled-archive"
        original_sync_archive=sync_module.WINDOW_SNAPSHOT_ARCHIVE
        original_dashboard_archive=dashboard_module.WINDOW_SNAPSHOT_ARCHIVE
        try:
            sync_module.WINDOW_SNAPSHOT_ARCHIVE=controlled_archive
            dashboard_module.WINDOW_SNAPSHOT_ARCHIVE=controlled_archive
            admission=write_snapshot(
                controlled_archive, market="TW", window="intraday_1305",
                effective_trading_date="2026-07-17", generated_at="2026-07-17T13:09:00+08:00",
                source_payload={"market":"TW","window":"intraday_1305","runtime_provenance":"scheduled_production","fixture":False,"validator":False,"validation_only":False,"cards":[{"stock_id":"2330","action":"觀察"}]},
                status="completed", run_kind="scheduled", run_id="controlled-ai183", rebuild_routes=False,
                effective_batch_time="2026-07-17T13:05:00+08:00",
            )
            controlled_sync=synchronize_admitted_latest(market="TW",window="intraday_1305",static_root=Path(tmp)/"controlled-public",output_dir=Path(tmp)/"controlled-build")
            snapshot=sync_module.resolve_snapshots(controlled_archive,"TW","intraday_1305").latest or {}
            provenance=build_delivery_provenance(market="TW",window="intraday_1305",trading_date="2026-07-17",snapshot=snapshot,canonical_url="/dashboard/archive/tw/intraday_1305/latest/index.html",channel="email",content="controlled no-send",delivery_result="dry_run_not_sent",delivery_attempted=False)
        finally:
            sync_module.WINDOW_SNAPSHOT_ARCHIVE=original_sync_archive
            dashboard_module.WINDOW_SNAPSHOT_ARCHIVE=original_dashboard_archive
    failures=[row for row in rows if row["status"]!="verified"]
    controlled_ok=admission.get("written") is True and controlled_sync.get("status")=="verified" and provenance["delivery_result"]=="dry_run_not_sent"
    ok=not failures and mismatch["status"]=="failed_verification" and controlled_ok
    return {"ok":ok,"window_count":len(rows),"matrix":rows,"failed":failures,"copy_success_identity_mismatch":mismatch["status"],"controlled_scheduler_equivalent":{"runtime":"deterministic_production_shape","snapshot_admitted":admission.get("written"),"temporary_public_identity":controlled_sync.get("status"),"notification_provenance":provenance["delivery_result"],"email_attempted":False,"line_attempted":False,"trading":False},"production_publish":False,"archive_modified":False}
def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
