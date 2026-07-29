#!/usr/bin/env python3
"""Deterministic validation for AI-DEV-196 recovery and prevention."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime.window_batch_health import TAIPEI, WINDOW_SPECS, assess_window
from app.loaders.google_sheet_loader import load_stock_ids_with_provenance
from scripts.orchestrator.approved_pre_open_delivery import build_pipeline_failure_result, window_config


def check(condition: bool, message: str, checks: list[dict[str, object]]) -> None:
    checks.append({"name": message, "ok": bool(condition)})
    if not condition:
        raise AssertionError(message)


def blank() -> dict[str, object]:
    return {}


def healthy_inputs(effective_date: str) -> dict[str, dict[str, object]]:
    identity = {"snapshot_id": "snap-1", "revision": 1, "source_payload_hash": "hash-1"}
    return {
        "progress": {"started_at": f"{effective_date}T07:00:01+08:00", "status": "completed"},
        "runtime": {"effective_trading_date": effective_date, "structured_pre_open_cards": [{"symbol": "2330"}]},
        "snapshot": {**identity, "effective_trading_date": effective_date, "admitted": True},
        "public_sync": {**identity, "status": "verified"},
        "email": identity,
        "line": identity,
        "operations": identity,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    checks: list[dict[str, object]] = []

    calls = {"primary": 0}

    def primary(**_: object) -> list[str]:
        calls["primary"] += 1
        return ["2330", "2337"]

    symbols, evidence = load_stock_ids_with_provenance(primary_loader=primary)
    check(symbols == ["2330", "2337"] and calls["primary"] == 1, "primary universe is loaded exactly once", checks)
    check(evidence["fallback_used"] is False, "primary success does not report fallback", checks)

    def unavailable(**_: object) -> list[str]:
        raise RuntimeError("provider unavailable")

    symbols, evidence = load_stock_ids_with_provenance(
        primary_loader=unavailable,
        fallback_loader=lambda: {
            "stock_ids": ["2330", "2337"],
            "snapshot_id": "tw-0700-1",
            "effective_trading_date": "2026-07-28",
            "revision": 2,
            "source_payload_hash": "hash-0700",
        },
    )
    check(symbols == ["2330", "2337"] and evidence["fallback_used"] is True, "bounded admitted snapshot fallback succeeds", checks)
    check(evidence["source_snapshot_id"] == "tw-0700-1", "fallback preserves source identity", checks)
    check(evidence["source_revision"] == 2 and evidence["source_payload_hash"] == "hash-0700", "fallback preserves revision and payload hash", checks)
    check(evidence["failure_category"] == "RuntimeError", "fallback diagnostics are sanitized", checks)
    try:
        load_stock_ids_with_provenance(primary_loader=unavailable, fallback_loader=lambda: {"stock_ids": []})
    except RuntimeError as exc:
        check("unavailable from primary and admitted fallback" in str(exc), "empty fallback fails closed", checks)
    else:
        raise AssertionError("empty fallback must fail")

    failure = build_pipeline_failure_result(
        SimpleNamespace(window="pre_open_0700"),
        window_config("pre_open_0700"),
        generated_at="2026-07-29T07:00:02+08:00",
        run_id="incident",
        returncode=1,
        progress={"status": "failed"},
        pipeline_diagnostics={"exception_type": "APIError"},
    )
    check(not failure["ok"] and failure["stage_results"]["pipeline"] == "FAIL", "failed child produces explicit incident artifact", checks)
    check(not any(failure[key] for key in ("delivery_attempted", "dashboard_publish_attempted", "email_attempted", "line_attempted")), "failed child attempts no publish or delivery", checks)
    check(failure["archive_write"]["written"] is False and failure["stage_results"]["operations"] == "NOT_BUILT", "failed child cannot reach archive or Operations", checks)

    spec = WINDOW_SPECS[0]
    base = dict(
        spec=spec,
        expected_trading_date="2026-07-29",
        progress=blank(), runtime=blank(), snapshot=blank(), public_sync=blank(),
        email=blank(), line=blank(), operations=blank(),
    )
    check(assess_window(now=datetime(2026, 7, 29, 7, 3, tzinfo=TAIPEI), **base)["status"] == "running", "missing batch before 07:05 remains running", checks)
    check(assess_window(now=datetime(2026, 7, 29, 7, 6, tzinfo=TAIPEI), **base)["status"] == "warning", "missing batch after 07:05 raises warning", checks)
    check(assess_window(now=datetime(2026, 7, 29, 7, 11, tzinfo=TAIPEI), **base)["status"] == "missing_batch", "missing batch after hard deadline fails", checks)
    failed_base = {**base, "progress": {"started_at": "2026-07-29T07:00:02+08:00", "status": "failed"}}
    check(assess_window(now=datetime(2026, 7, 29, 7, 3, tzinfo=TAIPEI), **failed_base)["status"] == "failed", "explicit pipeline failure fails immediately", checks)
    healthy = healthy_inputs("2026-07-29")
    check(assess_window(now=datetime(2026, 7, 29, 7, 11, tzinfo=TAIPEI), spec=spec, expected_trading_date="2026-07-29", **healthy)["status"] == "healthy", "complete admitted and published batch is healthy", checks)
    stale = healthy_inputs("2026-07-28")
    check(assess_window(now=datetime(2026, 7, 29, 7, 11, tzinfo=TAIPEI), spec=spec, expected_trading_date="2026-07-29", **stale)["status"] == "missing_batch", "previous trading date cannot mask a missing batch", checks)
    mismatch = healthy_inputs("2026-07-29")
    mismatch["public_sync"] = {"snapshot_id": "stale", "revision": 1, "source_payload_hash": "hash-1", "status": "verified"}
    assessed = assess_window(now=datetime(2026, 7, 29, 7, 11, tzinfo=TAIPEI), spec=spec, expected_trading_date="2026-07-29", **mismatch)
    check(assessed["status"] == "missing_batch" and assessed["stages"]["dashboard_publish"] == "MISSING", "public identity mismatch fails closed", checks)
    check(len(WINDOW_SPECS) == 7 and {item.market for item in WINDOW_SPECS} == {"TW", "US"}, "monitor covers seven market-isolated windows", checks)
    with tempfile.TemporaryDirectory() as temp:
        before = list(Path(temp).iterdir())
        assess_window(now=datetime(2026, 7, 29, 7, 11, tzinfo=TAIPEI), **base)
        check(before == list(Path(temp).iterdir()), "health assessment is non-mutating", checks)

    result = {"schema_version": "validate_tw_0700_missing_batch_recovery_v1", "ok": all(item["ok"] for item in checks), "checks": checks, "safety": {"notification_sent": False, "production_pipeline_executed": False, "archive_history_rewritten": False, "scheduler_changed": False}}
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
