#!/usr/bin/env python3
"""Deterministic non-production validation for AI-DEV-179."""
from __future__ import annotations
import argparse, json, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from app.dashboard.multi_market_dashboard import render_snapshot_archive_page
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots, same_window_change, write_snapshot

def source(marker: str, **extra: object) -> dict[str, object]:
    value: dict[str, object] = {"schema_version": "deterministic_test_payload_v1", "marker": marker, "cards": [{"id": marker}]}
    value.update(extra); return value

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args=parser.parse_args()
    errors=[]; checks={}
    with tempfile.TemporaryDirectory(prefix="ai-dev-179-validator-") as raw:
        root=Path(raw)
        def put(market: str, window: str, day: str, marker: str, run_kind: str="scheduled", status: str="completed", **extra: object):
            return write_snapshot(root, market=market, window=window, effective_trading_date=day, generated_at=f"{day}T12:00:00+08:00", source_payload=source(marker, **extra), status=status, run_kind=run_kind, run_id=f"test-{marker}")
        put("TW","post_close_1500","2026-07-10","tw15-old")
        put("TW","post_close_1500","2026-07-13","tw15-first")
        put("TW","prediction_review_1500","2026-07-13","tw15-revision","manual_rerun")
        put("TW","pre_close_1335","2026-07-10","tw1335-old")
        put("TW","pre_close_1335","2026-07-13","tw1335-new")
        put("US","us_pre_market_2000","2026-07-10","us20-old")
        put("US","us_pre_market_2000","2026-07-13","us20-new")
        put("US","us_post_close_review_0630","2026-07-13","us0630-only")
        rejected = [
            put("TW","intraday_1305","2026-07-13","failed", status="failed"),
            put("TW","intraday_1305","2026-07-13","fixture", fixture=True),
            put("TW","intraday_1305","2026-07-13","validator", validation_only=True),
            put("TW","intraday_1305","2026-07-13","incomplete", incomplete=True),
        ]
        tw15=resolve_snapshots(root,"TW","post_close_1500")
        checks["tw15_latest_revision"] = bool(tw15.latest and tw15.latest["payload"]["marker"]=="tw15-revision" and tw15.latest["revision"]==1)
        checks["tw15_previous_distinct_date"] = bool(tw15.previous and tw15.previous["effective_trading_date"]=="2026-07-10")
        checks["tw15_not_1335"] = bool(tw15.latest and tw15.latest["payload"]["marker"]!="tw1335-new")
        tw1335=resolve_snapshots(root,"TW","pre_close_1335")
        checks["tw1335_pair"] = bool(tw1335.latest and tw1335.previous and tw1335.latest["effective_trading_date"]=="2026-07-13" and tw1335.previous["effective_trading_date"]=="2026-07-10")
        us20=resolve_snapshots(root,"US","us_pre_market_2000")
        checks["us20_pair"] = bool(us20.latest and us20.previous and us20.latest["payload"]["marker"]=="us20-new")
        checks["market_isolation"] = bool(tw15.latest and tw15.latest["market"]=="TW" and us20.latest and us20.latest["market"]=="US")
        us0630=resolve_snapshots(root,"US","us_post_close_review_0630")
        empty_change=same_window_change(us0630.latest,us0630.previous)
        checks["us0630_previous_empty"] = not empty_change["available"] and "previous snapshot" in empty_change["empty_state"]
        comparison=same_window_change(tw15.latest,tw15.previous)
        checks["comparison_baseline"] = comparison.get("previous_trading_date")=="2026-07-10" and comparison.get("current_trading_date")=="2026-07-13"
        rendered=render_snapshot_archive_page("TW","post_close_1500","latest",tw15.latest,comparison)
        checks["renderer_snapshot_payload_only"] = "tw15-revision" in rendered and "tw1335-new" not in rendered and "tw15-first" not in rendered
        checks["rejections"] = all(item.get("written") is False for item in rejected)
        checks["fixed_routes"] = sum(len(v) for v in MARKET_WINDOWS.values())*2==14
        checks["temporary_archive_isolated"] = str(root).startswith("/tmp/") and root != ROOT/"artifacts/archive/window_snapshots"
    checks["temporary_archive_removed"] = not Path(raw).exists()
    errors=[name for name,ok in checks.items() if not ok]
    payload={"schema_version":"ai_dev_179_validator_v2","task_id":"AI-DEV-179","ok":not errors,"errors":errors,"checks":checks,"fixed_route_count":14,"production_archive_used":False,"temporary_archive_removed":checks["temporary_archive_removed"],"safety":{"email_sent":False,"line_sent":False,"production_approved_delivery":False,"trading_executed":False,"scheduler_changed":False,"python3_main_executed":False}}
    print(json.dumps(payload,ensure_ascii=False,indent=2 if args.pretty else None,sort_keys=True)); return 0 if payload["ok"] else 1
if __name__=="__main__": raise SystemExit(main())
