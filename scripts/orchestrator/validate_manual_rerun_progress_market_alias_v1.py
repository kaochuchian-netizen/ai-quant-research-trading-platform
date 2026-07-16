#!/usr/bin/env python3
"""Validate manual progress persistence and active market Dashboard snapshot parity."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.dashboard.multi_market_dashboard as dashboard
from app.dashboard.market_dashboard_alias import resolve_active_snapshot, snapshot_parity_contract
from app.dashboard.window_snapshot_archive import write_snapshot
from scripts.orchestrator.manual_rerun_runtime_bridge import lifecycle_status, persist_status, status_payload


def payload(market: str, window: str, marker: str) -> dict[str, Any]:
    tactical = {"action": "observe", "entry_zone": {"low": 10, "high": 11}, "confidence": 61}
    card = {"stock_id": marker, "stock_name": marker, "strategies": {"daily_tactical": tactical}}
    data: dict[str, Any] = {
        "schema_version": "manual_alias_fixture_v1", "market": market, "window": window,
        "runtime_provenance": "scheduled_production", "artifact_mode": "production_runtime",
        "fixture": False, "validation_only": False, "marker": marker,
        "notification_sent": False, "production_pipeline_executed": False,
    }
    if market == "TW":
        data["cards"] = [card]
    else:
        data["dashboard_ready_contract"] = {"cards": [{"symbol": marker, "name": marker, "daily_tactical_summary": tactical}]}
        data["runtime_watchlist_validation"] = {"enabled_stock_count": 1}
    return data


def put(archive: Path, market: str, window: str, day: str, marker: str, run_kind: str = "scheduled") -> dict[str, Any]:
    return write_snapshot(
        archive, market=market, window=window, effective_trading_date=day,
        generated_at=f"{day}T12:{'30' if run_kind == 'manual_rerun' else '00'}:00+08:00",
        source_payload=payload(market, window, marker), status="completed", run_kind=run_kind,
        run_id=f"controlled-{market}-{window}-{marker}", rebuild_routes=False,
    )


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def route_hashes(public: Path) -> dict[str, str | None]:
    return {
        path.relative_to(public).as_posix(): digest(path)
        for path in sorted((public / "dashboard/archive").rglob("index.html"))
    }


def attrs(text: str) -> dict[str, str]:
    keys = ("window", "snapshot-id", "effective-trading-date", "revision", "payload-hash")
    return {key: (re.search(fr'data-{key}="([^"]+)"', text) or [None, ""])[1] for key in keys}


def section_hash(text: str) -> str:
    match = re.search(r'<section class="section immutable-snapshot-payload".*?</section>', text, re.S)
    return hashlib.sha256((match.group(0) if match else "").encode()).hexdigest()


def parity(output: Path, market: str, main_name: str) -> bool:
    main = (output / main_name).read_text(encoding="utf-8")
    identity = attrs(main)
    archive = (output / f"dashboard/archive/{market.lower()}/{identity['window']}/latest/index.html").read_text(encoding="utf-8")
    return identity == attrs(archive) and section_hash(main) == section_hash(archive)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix="ai-dev-181e-") as raw:
        temp = Path(raw)
        archive, output, public, status_dir = temp / "archive", temp / "output", temp / "public", temp / "status"
        old_archive = dashboard.WINDOW_SNAPSHOT_ARCHIVE
        dashboard.WINDOW_SNAPSHOT_ARCHIVE = archive
        try:
            put(archive, "TW", "pre_open_0700", "2026-07-16", "tw07-r1")
            put(archive, "US", "us_pre_market_2000", "2026-07-15", "us20-r1")
            put(archive, "US", "us_intraday_2300", "2026-07-15", "us23-r1")
            dashboard.publish_pages(static_root=public, source_dir=output)
            checks["tw_initial_active_0700"] = resolve_active_snapshot(archive, "TW")["window"] == "pre_open_0700"
            checks["us_initial_active_2300"] = resolve_active_snapshot(archive, "US")["window"] == "us_intraday_2300"
            checks["tw_snapshot_parity"] = parity(output, "TW", "tw_index.html")
            checks["us_snapshot_parity"] = parity(output, "US", "us_index.html")

            before_routes = route_hashes(public)
            before_market = digest(public / "dashboard/tw/index.html")
            put(archive, "TW", "pre_open_0700", "2026-07-16", "tw07-r2", "manual_rerun")
            active_result = dashboard.publish_manual_rerun_update("TW", "pre_open_0700", static_root=public, output_dir=temp / "active-rerun")
            after_routes = route_hashes(public)
            changed = sorted(key for key in before_routes if before_routes[key] != after_routes[key])
            checks["active_latest_changed"] = changed == ["dashboard/archive/tw/pre_open_0700/latest/index.html"]
            checks["active_market_synced"] = active_result["market_dashboard_updated"] is True and before_market != digest(public / "dashboard/tw/index.html")
            checks["active_previous_unchanged"] = before_routes["dashboard/archive/tw/pre_open_0700/previous/index.html"] == after_routes["dashboard/archive/tw/pre_open_0700/previous/index.html"]
            checks["active_other_thirteen_unchanged"] = all(before_routes[key] == after_routes[key] for key in before_routes if key != "dashboard/archive/tw/pre_open_0700/latest/index.html")

            put(archive, "TW", "post_close_1500", "2026-07-16", "tw15-r1")
            dashboard.publish_pages(static_root=public, source_dir=output)
            checks["tw_active_advances_to_1500"] = resolve_active_snapshot(archive, "TW")["window"] == "post_close_1500"
            before_routes = route_hashes(public)
            before_market = digest(public / "dashboard/tw/index.html")
            put(archive, "TW", "pre_open_0700", "2026-07-16", "tw07-r3", "manual_rerun")
            nonactive_result = dashboard.publish_manual_rerun_update("TW", "pre_open_0700", static_root=public, output_dir=temp / "nonactive-rerun")
            after_routes = route_hashes(public)
            changed = sorted(key for key in before_routes if before_routes[key] != after_routes[key])
            checks["nonactive_latest_changed"] = changed == ["dashboard/archive/tw/pre_open_0700/latest/index.html"]
            checks["nonactive_market_stable"] = nonactive_result["market_dashboard_updated"] is False and before_market == digest(public / "dashboard/tw/index.html")
            checks["nonactive_previous_unchanged"] = before_routes["dashboard/archive/tw/pre_open_0700/previous/index.html"] == after_routes["dashboard/archive/tw/pre_open_0700/previous/index.html"]
            checks["nonactive_other_thirteen_unchanged"] = all(before_routes[key] == after_routes[key] for key in before_routes if key != "dashboard/archive/tw/pre_open_0700/latest/index.html")

            failed_before = {**route_hashes(public), "market": digest(public / "dashboard/tw/index.html")}
            failed = lifecycle_status({"job_id": "failed-job", "market": "TW", "window": "pre_open_0700"}, "failed", error_stage="建立 Runtime", error_summary="controlled failure", latest_route_updated=False, market_dashboard_updated=False)
            failed_after = {**route_hashes(public), "market": digest(public / "dashboard/tw/index.html")}
            checks["failed_terminal"] = failed["status"] == "failed" and failed["latest_route_updated"] is False
            checks["failed_updates_nothing"] = failed_before == failed_after

            state: dict[str, Any] = {"job_id": "progress-job", "task_id": "progress-job", "market": "TW", "window": "pre_open_0700", "submitted_at": "2026-07-16T08:00:00+08:00"}
            for lifecycle_state in ("submitted", "queued", "running", "publishing"):
                state = lifecycle_status(state, lifecycle_state)
                persist_status(state, status_dir)
            state = lifecycle_status(state, "completed", finished_at="2026-07-16T08:02:15+08:00", duration_seconds=135, effective_trading_date="2026-07-16", revision=2, latest_route_updated=True, market_dashboard_updated=True, previous_route_updated=False, other_windows_updated=False, latest_url="/latest", market_dashboard_url="/market")
            persist_status(state, status_dir)
            recovered = status_payload("progress-job", status_dir)
            checks["lifecycle_complete"] = recovered.get("lifecycle") == ["submitted", "queued", "running", "publishing", "completed"]
            checks["completion_contract"] = all(recovered.get(key) is not None for key in ("revision", "finished_at", "duration_seconds", "latest_url")) and recovered.get("previous_route_updated") is False and recovered.get("line_attempted") is False and recovered.get("email_attempted") is False
            checks["refresh_restart_recovery"] = recovered.get("job_id") == "progress-job" and status_payload(None, status_dir).get("status") == "completed"
            rejected = lifecycle_status({"market": "TW", "window": "pre_open_0700"}, "rejected", error_summary="invalid pin")
            checks["rejected_terminal"] = rejected["status"] == "rejected" and rejected["latest_route_updated"] is False
            landing = dashboard.render_landing_page()
            checks["engineering_matrix_hidden"] = "Controlled no-send verification matrix" not in landing
            checks["landing_manual_status_ui"] = all(marker in landing for marker in ("manual-status-state", "localStorage", "manual-status-latest-link", "manual-status-market-link"))
            checks["fourteen_routes"] = len(route_hashes(public)) == 14
            checks["seven_manual_buttons"] = landing.count('class="manual-batch-button" data-market=') == 7
            checks["operations_seven_rows"] = landing.count('<tr data-market=') == 7
            evidence = {
                "tw_active": snapshot_parity_contract(resolve_active_snapshot(archive, "TW")),
                "us_active": snapshot_parity_contract(resolve_active_snapshot(archive, "US")),
                "active_rerun": active_result,
                "nonactive_rerun": nonactive_result,
                "completion": recovered,
            }
        finally:
            dashboard.WINDOW_SNAPSHOT_ARCHIVE = old_archive
    checks["temporary_fixtures_removed"] = not Path(raw).exists()
    errors = [name for name, passed in checks.items() if not passed]
    result = {
        "schema_version": "manual_rerun_progress_market_alias_validation_v1", "task_id": "AI-DEV-181E",
        "ok": not errors, "errors": errors, "checks": checks, "evidence": evidence,
        "safety": {"email_attempted": False, "line_attempted": False, "production_delivery": False, "trading": False, "scheduler_changed": False, "python3_main_executed": False, "secrets_accessed": False},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
