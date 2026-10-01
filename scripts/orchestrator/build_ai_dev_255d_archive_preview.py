#!/usr/bin/env python3
"""Synthetic-only actual archive/latest publisher preview; temporary roots only."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.dashboard import multi_market_dashboard as dashboard
from app.dashboard import public_latest_sync as sync
from app.dashboard.window_snapshot_archive import write_snapshot, resolve_snapshots
from app.reports.mobile_decision_presentation import digest, VERSION
from scripts.orchestrator.validate_cross_feature_regression_matrix_v1 import fixture_payload


def require_temporary(root):
    root = Path(root).resolve()
    if Path(tempfile.gettempdir()).resolve() not in root.parents or ROOT == root or ROOT in root.parents:
        raise ValueError("temporary non-production target required")
    return root


def seed_archive(root):
    root = require_temporary(root)
    fixtures = json.loads((ROOT / "tests/fixtures/ai_dev_255_mobile_decision_v1.json").read_text())["payloads"]
    for source in fixtures:
        market, window = source["market"], source["window"]
        for day in ("2026-09-23", "2026-09-24"):
            payload = fixture_payload(market, window, day, "synthetic-255d")
            # Reuse the existing production-shaped admission fixture unchanged.
            # No bypass of strict structured-card/source-hash admission.
            payload["input_kind"] = "SYNTHETIC"
            if window == "post_close_1500":
                for index, card in enumerate(payload["cards"]):
                    card.update(stock_name="合成測試公司 "+str(index+1),
                        direction_hit=index==0, prediction_range_result="hit" if index==0 else "miss",
                        actual_direction="bullish" if index==0 else "bearish",
                        actual_low=98+index, actual_high=103+index, actual_close=102+index,
                        mfe=4.2, mae=-1.1,
                        preserved_unknown={"lineage":"synthetic-origin","backtest":[1,2,3]})
            result = write_snapshot(root, market=market, window=window,
                effective_trading_date=day, generated_at=day+"T20:00:00+08:00",
                source_payload=payload, status="completed", run_kind="scheduled",
                run_id="synthetic-255d-"+window+"-"+day)
            if not result.get("written"):
                raise AssertionError(result)
    return [(p["market"],p["window"]) for p in fixtures]


def build_preview(root):
    root = require_temporary(root)
    archive, output, public = root/"archive", root/"build", root/"public"
    windows = seed_archive(archive)
    before = {str(p.relative_to(archive)):p.read_bytes() for p in archive.rglob("*.json")}
    rows = []
    with patch.object(dashboard, "WINDOW_SNAPSHOT_ARCHIVE", archive), patch.object(sync, "WINDOW_SNAPSHOT_ARCHIVE", archive):
        for market, window in windows:
            result = sync.synchronize_admitted_latest(market=market, window=window,
                static_root=public, output_dir=output/market/window)
            if result["status"] != "verified":
                raise AssertionError(result)
            path = public/f"dashboard/archive/{market.lower()}/{window}/latest/index.html"
            previous = dashboard.build_archive_route(output,market,window,"previous")
            payload = resolve_snapshots(archive,market,window).latest["payload"]
            rows.append({"market":market,"window":window,"html":str(path.relative_to(root)),
                         "previous_html":str(previous.relative_to(root)),"source_digest":digest(payload),
                         "status":result["status"],"input_kind":"SYNTHETIC"})
    after = {str(p.relative_to(archive)):p.read_bytes() for p in archive.rglob("*.json")}
    if before != after: raise AssertionError("archive source mutation")
    (root/"manifest.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n")
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True,type=Path)
    args=p.parse_args();rows=build_preview(args.output)
    print(json.dumps({"status":"PASS","windows":len(rows),"production_mutation":"NONE"}))


if __name__=="__main__": main()
