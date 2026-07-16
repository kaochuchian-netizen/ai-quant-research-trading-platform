#!/usr/bin/env python3
"""Validate TW 13:35 immutable binding, delivery content, time semantics and URLs."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.dashboard_url_registry import get_window_archive_url
from app.dashboard.window_snapshot_archive import resolve_snapshots, write_snapshot
from app.reports.tw_1335_snapshot_delivery import render_dashboard, render_email, render_line, resolve_context
from app.reports.window_report_contract import all_window_report_contracts
from app.pipelines.afternoon_report_pipeline import _write_window_runtime


def card(stock_id: str, **state: Any) -> dict[str, Any]:
    no_trade = state.get("no_trade", False)
    action = "暫不操作" if no_trade else "降低追價" if state.get("avoid_hold") else "偏多續抱"
    return {
        "stock_id": stock_id,
        "stock_name": stock_id,
        "decision_state": {
            "hold_candidate": state.get("hold_candidate", False),
            "avoid_hold": state.get("avoid_hold", False),
            "no_trade": no_trade,
            "near_target": state.get("near_target", False),
            "near_stop": state.get("near_stop", False),
            "late_session_risk": state.get("late_session_risk", False),
            "tomorrow_watch": state.get("tomorrow_watch", False),
            "setup_triggered": state.get("setup_triggered", False),
            "setup_invalidated": state.get("setup_invalidated", False),
        },
        "strategies": {"daily_tactical": {
            "action": action,
            "entry_zone": {"low": 10, "high": 11},
            "setup_triggered": state.get("setup_triggered", False),
            "chase_risk": "high" if state.get("late_session_risk") else "low",
            "confidence": 60,
        }},
    }


def payload(window: str, cards: list[dict[str, Any]], *, source_time: str | None, prediction_available: int | None = 0) -> dict[str, Any]:
    return {
        "schema_version": "tw_1335_notification_fixture_v1",
        "artifact_type": "tw_window_decision_runtime",
        "artifact_mode": "production_runtime",
        "runtime_provenance": "scheduled_production",
        "fixture": False,
        "validator": False,
        "validation_only": False,
        "market": "TW",
        "window": window,
        "cards": cards,
        "source_data_time": source_time,
        "source_data_time_status": "available" if source_time else "unavailable_no_intraday_timestamp",
        "source_data_date": "2026-07-16",
        "generated_at": "2026-07-16T13:36:00+08:00" if window == "pre_close_1335" else "2026-07-16T13:06:00+08:00",
        "effective_batch_time": "2026-07-16T13:35:00+08:00" if window == "pre_close_1335" else "2026-07-16T13:05:00+08:00",
        "prediction_available": prediction_available,
        "prediction_total": len(cards),
    }


def put(archive: Path, window: str, data: dict[str, Any], generated_at: str, batch_time: str) -> dict[str, Any]:
    return write_snapshot(
        archive, market="TW", window=window, effective_trading_date="2026-07-16",
        generated_at=generated_at, effective_batch_time=batch_time, source_payload=data,
        status="completed", run_kind="scheduled", run_id=f"controlled-{window}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="ai-dev-181f-") as raw:
        temp = Path(raw)
        archive = temp / "archive"
        baseline_cards = [card("A", hold_candidate=True, tomorrow_watch=True, setup_triggered=True), card("B", hold_candidate=True, tomorrow_watch=True), card("C")]
        current_cards = [
            card("A", hold_candidate=True, tomorrow_watch=True, near_target=True, setup_triggered=True),
            card("B", hold_candidate=True, tomorrow_watch=True, near_stop=True),
            card("C", avoid_hold=True, late_session_risk=True, setup_invalidated=True),
            card("D", no_trade=True),
            card("E", hold_candidate=True, tomorrow_watch=True, setup_triggered=True),
        ]
        runtime_path = _write_window_runtime("pre_close", {"pipeline_run_id": "controlled-pre-close"}, current_cards, temp / "runtime")
        runtime_payload = json.loads(runtime_path.read_text())
        checks["window_runtime_binding"] = runtime_payload.get("window") == "pre_close_1335" and runtime_payload.get("pipeline_run_id") == "controlled-pre-close" and runtime_payload.get("source_data_time") is None and len(runtime_payload.get("cards") or []) == 5
        first = put(archive, "intraday_1305", payload("intraday_1305", baseline_cards, source_time="2026-07-16T13:04:00+08:00"), "2026-07-16T13:06:00+08:00", "2026-07-16T13:05:00+08:00")
        latest = put(archive, "pre_close_1335", payload("pre_close_1335", current_cards, source_time="2026-07-16T13:34:00+08:00"), "2026-07-16T13:36:00+08:00", "2026-07-16T13:35:00+08:00")
        context = resolve_context(archive)
        assert context
        email, line, dashboard = render_email(context), render_line(context), render_dashboard(context)
        canonical = get_window_archive_url("TW", "pre_close_1335")
        decision = context["projection"]["pre_close_decision"]
        checks["correct_binding"] = context["window"] == "pre_close_1335" and context["snapshot_id"] == latest["snapshot_id"]
        checks["canonical_url"] = canonical in email and canonical in line and "/dashboard/tw/index.html" not in email + line and "intraday_1305/latest" not in email + line
        checks["time_semantics"] = all(value in email for value in ("批次時間：2026-07-16 13:35", "行情資料時間：2026-07-16 13:34", "報告產生時間：2026-07-16 13:36")) and "05:42" not in email
        checks["decision_counts"] = decision["hold_candidate_count"] == 3 and decision["avoid_hold_count"] == 1 and decision["no_trade_count"] == 1 and decision["near_target_count"] == 1 and decision["near_stop_count"] == 1 and decision["late_session_risk_count"] == 1
        checks["same_day_comparison"] = context["same_day_change"]["available"] is True and context["same_day_change"]["baseline_snapshot_id"] == first["snapshot_id"] and context["same_day_change"]["added_watch"] == ["E"]
        checks["partial_prediction_clear"] = "隔日價格預測：尚未完成（0 / 5）" in email and "有效標的：5" in email
        checks["action_ranking"] = decision["ranking"][0] == "C" and "13:35 行動排序" in dashboard

        no_baseline_archive = temp / "no-baseline"
        put(no_baseline_archive, "pre_close_1335", payload("pre_close_1335", current_cards, source_time=None), "2026-07-16T13:36:00+08:00", "2026-07-16T13:35:00+08:00")
        no_baseline = resolve_context(no_baseline_archive)
        checks["no_baseline_empty_state"] = no_baseline is not None and "本次無同日 13:05 可比較基準" in render_email(no_baseline)
        checks["source_time_empty_state"] = no_baseline is not None and "行情資料時間：尚未取得" in render_email(no_baseline)

        result_path = temp / "scheduler-equivalent.json"
        env = dict(os.environ)
        env["STOCK_AI_WINDOW_SNAPSHOT_ARCHIVE"] = str(archive)
        completed = subprocess.run([
            sys.executable, "scripts/orchestrator/approved_pre_open_delivery.py",
            "--window", "pre_close_1335", "--dry-run", "--output", str(result_path),
            "--dashboard-publish-dir", str(temp / "public"), "--mail-env-file", str(temp / "missing-mail.env"),
        ], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
        dry = json.loads(result_path.read_text()) if result_path.exists() else {}
        checks["scheduler_equivalent_no_send"] = completed.returncode == 0 and dry.get("scheduler_window") == "pre_close_1335" and canonical in dry.get("line_payload_preview", "") and canonical in dry.get("email_payload_preview", "") and dry.get("line_delivery_status") == "dry_run_not_sent" and dry.get("email_delivery_status") == "dry_run_not_sent"

        expected_times = {"pre_open_0700": "07:00", "intraday_1305": "13:05", "pre_close_1335": "13:35", "post_close_1500": "15:00", "us_pre_market_2000": "20:00", "us_intraday_2300": "23:00", "us_post_close_review_0630": "06:30"}
        contracts = all_window_report_contracts()
        checks["seven_window_url_time_audit"] = len(contracts) == 7 and all(contract.dashboard_url == get_window_archive_url(contract.market, contract.window) and expected_times[contract.window] in contract.short_label and "/dashboard/tw/index.html" not in contract.dashboard_url and "/dashboard/us/index.html" not in contract.dashboard_url for contract in contracts)
        selected = resolve_snapshots(archive, "TW", "pre_close_1335").latest
        checks["snapshot_payload_parity"] = bool(selected is not None and selected["snapshot_id"] == context["snapshot_id"] and context["payload_hash"])
        evidence = {
            "window": context["window"], "snapshot_id": context["snapshot_id"], "baseline_snapshot_id": context["same_day_change"].get("baseline_snapshot_id"),
            "effective_batch_time": context["effective_batch_time"], "source_data_time": context["source_data_time"], "generated_at": context["generated_at"],
            "canonical_url": context["canonical_url"], "decision": decision, "change_summary": context["same_day_change"],
            "email_payload": email, "line_payload": line,
            "safety_flags": {"email_attempted": False, "line_attempted": False, "trading": False, "scheduler_changed": False, "production_delivery": False},
        }
    checks["temporary_fixtures_removed"] = not Path(raw).exists()
    errors = [name for name, passed in checks.items() if not passed]
    result = {"schema_version": "tw_1335_snapshot_notification_validation_v1", "task_id": "AI-DEV-181F", "ok": not errors, "errors": errors, "checks": checks, "evidence": evidence}
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
