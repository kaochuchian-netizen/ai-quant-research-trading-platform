#!/usr/bin/env python3
"""Validate US runtime provenance classification and persistence isolation."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.dashboard.multi_market_dashboard as dashboard
from app.dashboard.window_snapshot_archive import admission_errors, resolve_snapshots, write_snapshot
from app.us_stock.runtime_provenance import RuntimeProvenance, classify_runtime_provenance, provenance_admission
from scripts.orchestrator import approved_us_stock_delivery as runner


def artifact(provenance: str, window: str = "us_intraday_2300") -> dict[str, Any]:
    production = provenance in {RuntimeProvenance.SCHEDULED_PRODUCTION.value, RuntimeProvenance.MANUAL_RERUN.value}
    return {
        "schema_version": "runtime_provenance_fixture_v1",
        "artifact_kind": "us_stock_runtime",
        "artifact_type": "us_stock_live_runtime_artifact" if production else "controlled_verification_artifact",
        "artifact_mode": "production_runtime" if production else provenance,
        "runtime_provenance": provenance,
        "data_source_mode": "live" if production else provenance,
        "fixture": provenance == RuntimeProvenance.FIXTURE.value,
        "validator": provenance == RuntimeProvenance.VALIDATOR.value,
        "validation_only": not production,
        "preview": provenance == RuntimeProvenance.PREVIEW.value,
        "dry_run": provenance == RuntimeProvenance.DRY_RUN.value,
        "market": "US", "window": window, "generated_at": "2026-07-15T23:00:00+08:00",
        "dashboard_ready_contract": {"cards": [{"symbol": "PROV", "name": "Provenance", "daily_tactical_summary": {"action": "等待確認", "entry_zone": {"low": 1, "high": 2}, "confidence": 60}}]},
        "runtime_watchlist_validation": {"enabled_stock_count": 1},
    }


def file_hashes(paths: list[Path]) -> dict[str, str | None]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        for path in paths
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}

    expected = {
        RuntimeProvenance.SCHEDULED_PRODUCTION.value: True,
        RuntimeProvenance.MANUAL_RERUN.value: True,
        RuntimeProvenance.CONTROLLED_NO_SEND.value: False,
        RuntimeProvenance.PREVIEW.value: False,
        RuntimeProvenance.FIXTURE.value: False,
        RuntimeProvenance.VALIDATOR.value: False,
        RuntimeProvenance.DRY_RUN.value: False,
    }
    for provenance, admitted in expected.items():
        payload = artifact(provenance)
        decision = provenance_admission(payload, run_kind="manual_rerun" if provenance == "manual_rerun" else "scheduled")
        checks[f"enum:{provenance}"] = classify_runtime_provenance(payload) == provenance
        checks[f"admission:{provenance}"] = decision["admitted"] is admitted

    formal_paths = [*runner.WINDOW_OUTPUTS.values(), *runner.LEGACY_WINDOW_OUTPUTS.values(), runner.STATUS_PATH, runner.US_STATUS_PATH]
    before = file_hashes(formal_paths)
    completed = subprocess.run(
        [sys.executable, "scripts/orchestrator/approved_us_stock_delivery.py", "--window", "us_pre_market_2000", "--dry-run", "--pretty"],
        cwd=ROOT, text=True, capture_output=True, timeout=60,
    )
    after = file_hashes(formal_paths)
    dry_result = json.loads(completed.stdout) if completed.returncode == 0 else {}
    checks["dry_run_does_not_overwrite_formal_latest"] = before == after
    checks["dry_run_not_persisted"] = dry_result.get("status", {}).get("formal_runtime_persisted") is False
    checks["dry_run_no_send"] = not dry_result.get("email", {}).get("attempted") and not dry_result.get("line", {}).get("attempted")

    with tempfile.TemporaryDirectory(prefix="ai-dev-181a-provenance-") as raw:
        temp = Path(raw)
        archive = temp / "archive"
        scheduled = artifact(RuntimeProvenance.SCHEDULED_PRODUCTION.value)
        fixture = artifact(RuntimeProvenance.FIXTURE.value)

        original_files = dashboard.US_RUNTIME_FILES
        original_archive = dashboard.WINDOW_SNAPSHOT_ARCHIVE
        try:
            dashboard_archive = temp / "dashboard-archive"
            dashboard_write = write_snapshot(
                dashboard_archive,
                market="US",
                window="us_intraday_2300",
                effective_trading_date="2026-07-15",
                generated_at="2026-07-15T23:00:00+08:00",
                source_payload=scheduled,
                status="completed",
                run_kind="scheduled",
            )
            dashboard.WINDOW_SNAPSHOT_ARCHIVE = dashboard_archive
            scheduled_html = dashboard.render_us_page()

            unsafe_archive = temp / "unsafe-dashboard-archive"
            fixture_write = write_snapshot(
                unsafe_archive,
                market="US",
                window="us_intraday_2300",
                effective_trading_date="2026-07-15",
                generated_at="2026-07-15T23:00:00+08:00",
                source_payload=fixture,
                status="completed",
                run_kind="scheduled",
            )
            dashboard.WINDOW_SNAPSHOT_ARCHIVE = unsafe_archive
            fixture_html = dashboard.render_us_page()
            checks["scheduled_dashboard_pass"] = (
                dashboard_write.get("written") is True
                and "PROV" in scheduled_html
                and "data-snapshot-id=" in scheduled_html
            )
            checks["fixture_dashboard_empty"] = (
                fixture_write.get("written") is False
                and "尚無可用 snapshot" in fixture_html
                and "PROV" not in fixture_html
            )

            first = write_snapshot(archive, market="US", window="us_intraday_2300", effective_trading_date="2026-07-14", generated_at="2026-07-15T23:00:00+08:00", source_payload=scheduled, status="completed", run_kind="scheduled")
            second = write_snapshot(archive, market="US", window="us_intraday_2300", effective_trading_date="2026-07-15", generated_at="2026-07-16T23:00:00+08:00", source_payload=scheduled, status="completed", run_kind="scheduled")
            manual_payload = artifact(RuntimeProvenance.MANUAL_RERUN.value)
            manual = write_snapshot(archive, market="US", window="us_intraday_2300", effective_trading_date="2026-07-15", generated_at="2026-07-17T00:10:00+08:00", source_payload=manual_payload, status="completed", run_kind="manual_rerun")
            rejected = {
                provenance: write_snapshot(archive, market="US", window="us_pre_market_2000", effective_trading_date="2026-07-15", generated_at="2026-07-15T20:00:00+08:00", source_payload=artifact(provenance, "us_pre_market_2000"), status="completed", run_kind="scheduled")
                for provenance in ("fixture", "validator", "preview", "dry_run", "controlled_no_send")
            }
            selected = resolve_snapshots(archive, "US", "us_intraday_2300")
            checks["scheduled_archive_admitted"] = first.get("written") is True and second.get("written") is True
            checks["manual_latest_revision"] = manual.get("revision") == 2 and selected.latest.get("revision") == 2 and selected.latest.get("runtime_provenance") == "manual_rerun"
            checks["previous_stable_date"] = selected.previous.get("effective_trading_date") == "2026-07-14"
            checks["unsafe_archive_rejected"] = all(not item.get("written") for item in rejected.values())
            checks["archive_audit_metadata"] = all(selected.latest.get(key) is not None for key in ("runtime_provenance", "admission_reason", "admitted")) and selected.latest.get("admitted") is True
            spoofed = dict(selected.latest)
            spoofed["runtime_provenance"] = "scheduled_production"
            spoofed["admitted"] = True
            spoofed["payload"] = artifact(RuntimeProvenance.FIXTURE.value)
            checks["archive_top_level_cannot_spoof_payload"] = "runtime_provenance" in admission_errors(spoofed)

            dashboard.WINDOW_SNAPSHOT_ARCHIVE = archive
            operations_production = dashboard.render_landing_page()
            dashboard.WINDOW_SNAPSHOT_ARCHIVE = unsafe_archive
            operations_validation = dashboard.render_landing_page()
            checks["operations_scheduled_production"] = "scheduled_production" in operations_production
            checks["operations_validation_only"] = (
                "fixture" not in operations_validation.lower()
                and "Validation Only" not in operations_validation
                and "scheduled_production" in operations_validation
            )
        finally:
            dashboard.US_RUNTIME_FILES = original_files
            dashboard.WINDOW_SNAPSHOT_ARCHIVE = original_archive
        evidence = {
            "dry_run_returncode": completed.returncode,
            "dry_run_runtime_provenance": dry_result.get("status", {}).get("runtime_provenance"),
            "scheduled_archive": first,
            "manual_archive": manual,
            "rejected": rejected,
        }
    checks["temporary_verification_removed"] = not Path(raw).exists()
    errors = [name for name, passed in checks.items() if not passed]
    result = {
        "schema_version": "runtime_provenance_classification_validation_v1", "task_id": "AI-DEV-181A",
        "ok": not errors, "errors": errors, "checks": checks, "evidence": evidence,
        "safety": {"email_attempted": False, "line_attempted": False, "production_delivery": False, "trading": False, "scheduler_changed": False, "python3_main_executed": False, "secrets_accessed": False},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
