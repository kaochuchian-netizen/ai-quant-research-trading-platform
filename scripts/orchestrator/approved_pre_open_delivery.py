#!/usr/bin/env python3
"""Approved all-day scheduler delivery runner.

This runner supports explicitly approved scheduler delivery windows after an
operator has set STOCK_AI_APPROVED_DELIVERY=1 in the scheduler entry.
"""

from __future__ import annotations

import argparse
import html
import importlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.reports.multi_window_formatter import line_notification_text  # noqa: E402
from app.reports.report_content_contract import build_report_content_artifact  # noqa: E402
from app.reports.window_context import get_window_context  # noqa: E402
from app.runtime.production_run_guard import evaluate_pre_open_run_guard  # noqa: E402
from app.runtime.runtime_diagnostics import build_guard_result, write_json  # noqa: E402
from app.runtime.timeout_policy import TimeoutPolicy, timeout_policy_from_env  # noqa: E402
from scripts.orchestrator.notify_stage_report import (  # noqa: E402
    build_message,
    load_env_file,
    load_mail_config,
    send_message,
)


SCHEMA_VERSION = "approved_scheduler_delivery_v1"
TASK_ID = "AI-DEV-112"
DEFAULT_DASHBOARD_DIR = Path("/var/www/stock-ai-dashboard")
DEFAULT_MAIL_ENV_FILE = Path("~/.config/stock-ai-orchestrator/mail.env")
DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL = "http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html"
EMAIL_BODY_LIMIT = 14000
LINE_BODY_LIMIT = 520
TRACEBACK_MARKERS = (
    "Traceback (most recent call last):",
    "ShioajiClientError:",
    "Exception:",
)

WINDOW_TIMEOUT_SECONDS = {
    "pre_open_0700": 30 * 60,
    "intraday_1305": 10 * 60,
    "pre_close_1335": 10 * 60,
    "post_close_1500": 15 * 60,
}
WINDOW_GRACE_PERIOD_SECONDS = {
    "pre_open_0700": 30 * 60,
    "intraday_1305": 15 * 60,
    "pre_close_1335": 15 * 60,
    "post_close_1500": 20 * 60,
}
PROGRESS_ARTIFACTS = {
    "intraday_1305": Path("artifacts/runtime/delivery_progress_intraday_1305_latest.json"),
    "pre_close_1335": Path("artifacts/runtime/delivery_progress_pre_close_1335_latest.json"),
    "post_close_1500": Path("artifacts/runtime/delivery_progress_prediction_review_1500_latest.json"),
    "pre_open_0700": Path("artifacts/runtime/delivery_progress_pre_open_0700_latest.json"),
}

WINDOWS = {
    "pre_open_0700": {
        "label": "07:00 pre-open",
        "local_time": "07:00",
        "pipeline_type": "pre_open",
        "line_policy": "link-only notification handled by production pre_open pipeline",
        "line_mode": "handled_by_pipeline",
        "email_policy": "PM-readable scheduled summary with Dashboard link",
        "dashboard_policy": "publish latest full scheduler snapshot",
        "fallback_state": "pipeline output tail is included if report content is partial",
    },
    "intraday_1305": {
        "label": "13:05 intraday",
        "local_time": "13:05",
        "pipeline_type": "intraday",
        "line_policy": "link-only notification with dashboard URL only",
        "line_mode": "concise_reminder",
        "email_policy": "PM-readable window summary with Dashboard link",
        "dashboard_policy": "publish latest intraday scheduler snapshot",
        "fallback_state": "report content pending / insufficient data if pipeline only returns context summary",
    },
    "pre_close_1335": {
        "label": "13:35 pre-close",
        "local_time": "13:35",
        "pipeline_type": "pre_close",
        "line_policy": "link-only close snapshot notification with dashboard URL only",
        "line_mode": "concise_reminder",
        "email_policy": "PM-readable window summary with Dashboard link",
        "dashboard_policy": "publish latest pre-close scheduler snapshot",
        "fallback_state": "report content pending / insufficient data if pipeline only returns context summary",
    },
    "post_close_1500": {
        "label": "15:00 post-close / prediction review",
        "local_time": "15:00",
        "pipeline_type": "post_close",
        "line_policy": "link-only post-close review notification with dashboard URL only",
        "line_mode": "concise_reminder",
        "email_policy": "PM-readable post-close review summary with Dashboard link",
        "dashboard_policy": "publish latest post-close / prediction review snapshot",
        "fallback_state": "prediction review pending / insufficient data when review records are unavailable",
    },
}



def window_timeout_seconds(window_id: str) -> int:
    return WINDOW_TIMEOUT_SECONDS.get(window_id, 30 * 60)


def window_grace_period_seconds(window_id: str) -> int:
    return WINDOW_GRACE_PERIOD_SECONDS.get(window_id, 15 * 60)


def scheduled_datetime_taipei(window_id: str, reference: datetime) -> datetime:
    local_time = window_config(window_id)["local_time"]
    hour, minute = (int(part) for part in local_time.split(":", 1))
    return reference.replace(hour=hour, minute=minute, second=0, microsecond=0)


def delivery_lateness(window_id: str, reference: datetime | None = None) -> dict[str, Any]:
    current = reference or now_taipei()
    scheduled = scheduled_datetime_taipei(window_id, current)
    late_by = max(0, int((current - scheduled).total_seconds()))
    grace = window_grace_period_seconds(window_id)
    return {
        "late": late_by > grace,
        "late_by_seconds": late_by,
        "grace_period_seconds": grace,
        "scheduled_at": scheduled.isoformat(),
        "checked_at": current.isoformat(),
    }


def progress_artifact_path(window_id: str) -> Path:
    return REPO_ROOT / PROGRESS_ARTIFACTS[window_id]


def write_progress_artifact(
    window_id: str,
    started_at: str,
    current_stage: str,
    status: str,
    timeout_seconds: int,
    elapsed_seconds: int = 0,
) -> dict[str, Any]:
    payload = {
        "schema_version": "delivery_progress_artifact_v1",
        "window": window_id,
        "started_at": started_at,
        "last_heartbeat_at": now_taipei().isoformat(),
        "current_stage": current_stage,
        "elapsed_seconds": elapsed_seconds,
        "timeout_seconds": timeout_seconds,
        "status": status,
        "events": ["wrapper_started", current_stage],
    }
    path = progress_artifact_path(window_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(path), "payload": payload}


def timeout_delivery_artifact(window_id: str, timeout_seconds: int, created_at: str) -> dict[str, Any]:
    return {
        "schema_version": "delivery_timeout_artifact_v1",
        "window": window_id,
        "status": "timed_out",
        "pipeline_completed": False,
        "delivery_attempted": False,
        "line_attempted": False,
        "email_attempted": False,
        "dashboard_publish_attempted": False,
        "timeout_seconds": timeout_seconds,
        "reason": "child_pipeline_timeout",
        "safe_to_retry": True,
        "created_at": created_at,
    }


def late_delivery_artifact(window_id: str, late: dict[str, Any], created_at: str) -> dict[str, Any]:
    return {
        "schema_version": "delivery_late_suppression_artifact_v1",
        "window": window_id,
        "status": "completed_late_delivery_suppressed",
        "pipeline_completed": True,
        "delivery_attempted": False,
        "line_attempted": False,
        "email_attempted": False,
        "dashboard_publish_attempted": False,
        "late_delivery_suppressed": True,
        "late_by_seconds": late["late_by_seconds"],
        "grace_period_seconds": late["grace_period_seconds"],
        "reason": "window_grace_period_exceeded",
        "created_at": created_at,
    }


def now_taipei() -> datetime:
    return datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def tail_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def contains_traceback(text: str) -> bool:
    return any(marker in text for marker in TRACEBACK_MARKERS)


def window_config(window_id: str) -> dict[str, str]:
    try:
        return WINDOWS[window_id]
    except KeyError as exc:
        raise SystemExit(f"unsupported approved delivery window: {window_id}") from exc


def content_state(window_id: str, output_tail: str, pipeline_status: str = "completed") -> str:
    cfg = window_config(window_id)
    if pipeline_status != "completed":
        return "pipeline failed; diagnostics available"
    if contains_traceback(output_tail):
        return "validated report content unavailable; diagnostics available"
    if window_id == "post_close_1500" and "prediction" not in output_tail.lower():
        return cfg["fallback_state"]
    if output_tail.strip():
        return "pipeline output available"
    return cfg["fallback_state"]


def user_facing_report_content(window_id: str, pipeline_status: str, output_tail: str) -> str:
    cfg = window_config(window_id)
    if pipeline_status != "completed":
        content_state_value = "failed"
        raw_text = (
            f"{cfg['label']} pipeline did not produce validated report content. "
            "The delivery artifact keeps error details in diagnostics for operator review."
        )
    elif contains_traceback(output_tail):
        content_state_value = "partial"
        raw_text = "Validated report content is unavailable because runtime diagnostics were suppressed."
    else:
        content_state_value = content_state(window_id, output_tail, pipeline_status)
        if content_state_value.startswith("prediction review pending"):
            content_state_value = "prediction_review_pending"
        elif content_state_value == "pipeline output available":
            content_state_value = "stock_analysis_reports_available"
        raw_text = output_tail
    artifact = build_report_content_artifact(
        window_id,
        tail_text(raw_text, EMAIL_BODY_LIMIT),
        content_state_value,
        run_id="delivery-render",
    )
    return tail_text(artifact.user_facing_report.get("rendered_text", ""), EMAIL_BODY_LIMIT)


def build_pipeline_diagnostics(completed: subprocess.CompletedProcess[str], output: str) -> dict[str, Any]:
    return {
        "pipeline_returncode": completed.returncode,
        "raw_output_tail": tail_text(output, EMAIL_BODY_LIMIT),
        "raw_output_contains_traceback": contains_traceback(output),
        "raw_output_chars": len(output),
    }


def render_dashboard(window_id: str, run_id: str, generated_at: str, pipeline_status: str, output_tail: str) -> str:
    cfg = window_config(window_id)
    dashboard_url = DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL
    rows = [
        ("批次", cfg["label"]),
        ("產生時間", generated_at),
        ("狀態", pipeline_status),
        ("內容定位", "Legacy / Debug landing；正式決策內容請看四時段 Dashboard"),
        ("正式入口", dashboard_url),
    ]
    body = "\n".join(f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>" for label, value in rows)
    return f"""<!doctype html>
<html lang=\"zh-Hant\">
<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Stock AI Legacy / Debug Landing</title>
<style>body{{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;background:#f6f7fb;color:#17202a}}main{{max-width:920px;margin:0 auto;padding:32px 20px}}section{{background:#fff;border:1px solid #d6dbdf;border-radius:8px;padding:20px;margin-bottom:16px}}th,td{{border-bottom:1px solid #e5e7eb;padding:10px;text-align:left}}th{{width:180px;color:#667085}}a{{color:#075985;font-weight:700}}</style></head>
<body><main><section><h1>Stock AI Legacy / Debug Landing</h1><p>正式決策入口已移至四時段 Decision Intelligence Dashboard。此頁只保留 legacy/debug 狀態入口，不再呈現 raw pipeline report content。</p><p><a href=\"{html.escape(dashboard_url)}\">前往正式四時段 Decision Intelligence Dashboard</a></p></section><section><h2>本次批次狀態</h2><table>{body}</table><p>Raw logs / pipeline details stay in artifacts and diagnostics only.</p></section></main></body></html>"""

def publish_dashboard(publish_dir: Path, window_id: str, run_id: str, generated_at: str, pipeline_status: str, output_tail: str) -> dict[str, Any]:
    publish_dir.mkdir(parents=True, exist_ok=True)
    index_path = publish_dir / "index.html"
    manifest_path = publish_dir / "publish_manifest.json"
    index_path.write_text(
        render_dashboard(window_id, run_id, generated_at, pipeline_status, output_tail),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "approved_scheduler_dashboard_manifest_v1",
        "task_id": TASK_ID,
        "run_id": run_id,
        "generated_at": generated_at,
        "scheduler_window": window_id,
        "pipeline_status": pipeline_status,
        "content_state": content_state(window_id, output_tail, pipeline_status),
        "index_path": str(index_path),
        "user_facing_contains_traceback": contains_traceback(
            user_facing_report_content(window_id, pipeline_status, output_tail)
        ),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "publish_attempted": True,
        "publish_status": "published",
        "index_path": str(index_path),
        "manifest_path": str(manifest_path),
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _production_email_summary() -> dict[str, Any]:
    export = _load_json(REPO_ROOT / "templates/four_window_dashboard_production_runtime_export.example.json")
    prediction = _load_json(REPO_ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json")
    snapshot = _load_json(REPO_ROOT / "artifacts/archive/formal_forecast_snapshots/index/formal_forecast_snapshot_index_latest.json")
    calibration = _load_json(REPO_ROOT / "artifacts/runtime/forecast_calibration_proposal_latest.json")
    stocks = export.get("per_stock_summaries") or []
    rating_available = sum(1 for item in stocks if item.get("rating") not in (None, "", "資料待接") and item.get("total_score") not in (None, "", "資料待接"))
    pred_stocks = prediction.get("stocks") or []
    prediction_available = 0
    for item in pred_stocks:
        vals = [item.get("same_day_high_prediction"), item.get("same_day_low_prediction"), item.get("next_day_high_prediction"), item.get("next_day_low_prediction")]
        if all(isinstance(v, (int, float)) and v > 0 for v in vals):
            prediction_available += 1
    stock_count = export.get("stock_universe_count") or len(stocks) or len(pred_stocks) or 0
    return {
        "stock_count": stock_count,
        "rating_available": rating_available,
        "prediction_count": len(pred_stocks) or stock_count,
        "prediction_available": prediction_available,
        "prediction_snapshots": snapshot.get("prediction_snapshot_count", 0),
        "actual_snapshots": snapshot.get("actual_outcome_snapshot_count", 0),
        "review_snapshots": snapshot.get("review_snapshot_count", 0),
        "calibration_gate": calibration.get("tuning_gate_status") or (snapshot.get("calibration_gate_progress") or {}).get("current_gate_status") or "blocked_insufficient_sample",
        "latest_data_timestamp": export.get("latest_runtime_timestamp") or export.get("generated_at") or "資料待接",
        "top_signals": stocks[:3],
    }


def build_email_body(window_id: str, run_id: str, generated_at: str, pipeline_status: str, dashboard_url: str, output_tail: str) -> str:
    summary = _production_email_summary()
    titles = {
        "pre_open_0700": "【Stock AI】07:00 盤前決策摘要已更新",
        "intraday_1305": "【Stock AI】13:05 盤中追蹤已更新",
        "pre_close_1335": "【Stock AI】13:35 收盤快照已更新",
        "post_close_1500": "【Stock AI】15:00 盤後檢討已更新",
    }
    status_label = {
        "pre_open_0700": "盤前評等資料",
        "intraday_1305": "盤中追蹤資料",
        "pre_close_1335": "收盤快照資料",
        "post_close_1500": "盤後檢討資料",
    }.get(window_id, "批次資料")
    lines = [
        titles.get(window_id, "【Stock AI】排程摘要已更新"),
        "Dashboard：",
        dashboard_url,
        "",
        "今日狀態：",
        f"- 最新資料時間：{summary['latest_data_timestamp']}",
        f"- 追蹤標的：{summary['stock_count']} 檔",
        f"- {status_label}：{summary['rating_available']} / {summary['stock_count']} 檔可用",
        f"- 今日/隔日預測資料：{summary['prediction_available']} / {summary['prediction_count']} 檔可用",
        f"- Snapshot 累積：prediction {summary['prediction_snapshots']}、actual outcome {summary['actual_snapshots']}、review {summary['review_snapshots']}",
        f"- Calibration gate：{summary['calibration_gate']}",
    ]
    top = [s for s in summary["top_signals"] if s.get("rating") and s.get("total_score")]
    if top:
        lines += ["", "今日摘要 Top Signals："]
        for item in top[:3]:
            lines.append(f"- {item.get('stock_id','')} {item.get('stock_name','')}：{item.get('rating','資料待接')} / {item.get('action','資料待接')} / 分數 {item.get('total_score','資料待接')}")
    lines += ["", "重點提醒：", "- baseline V1 仍在回測校準。", "- 預測僅供研究參考，非交易指令。", "- 詳細個股、預測、風險與檢討請看 Dashboard。", "本信不包含下單建議。"]
    return "\n".join(lines)

def send_delivery_email(env_file: Path, window_id: str, run_id: str, generated_at: str, pipeline_status: str, dashboard_url: str, output_tail: str) -> dict[str, Any]:
    cfg = window_config(window_id)
    expanded = env_file.expanduser()
    if expanded.exists():
        load_env_file(expanded)
    config = load_mail_config()
    subject = f"[Stock AI] {cfg['label']} approved delivery {generated_at}"
    message = build_message(
        config,
        subject,
        build_email_body(window_id, run_id, generated_at, pipeline_status, dashboard_url, output_tail),
    )
    send_message(config, message)
    return {
        "send_attempted": True,
        "send_status": "sent",
        "env_file_checked": True,
        "env_file_exists": expanded.exists(),
        "secret_values_printed": False,
    }


def build_line_message(window_id: str, generated_at: str, pipeline_status: str, dashboard_url: str, output_tail: str) -> str:
    """Build the approved AI-DEV-157 link-only LINE notification.

    Runtime diagnostics, pipeline state, stock details, and raw artifact keys stay out
    of LINE. The full decision content belongs on the Dashboard.
    """
    context = get_window_context(window_id)
    return tail_text(line_notification_text(context, dashboard_url or DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL), LINE_BODY_LIMIT)


def send_concise_line(window_id: str, generated_at: str, pipeline_status: str, dashboard_url: str, output_tail: str) -> dict[str, Any]:
    cfg = window_config(window_id)
    if cfg["line_mode"] == "handled_by_pipeline":
        if pipeline_status != "completed":
            return {
                "send_attempted": False,
                "send_status": "not_sent",
                "reason": "pipeline_failed_before_pipeline_line_delivery",
                "policy": cfg["line_policy"],
                "concise_reminder": False,
                "secret_values_printed": False,
            }
        return {
            "send_attempted": False,
            "send_status": "handled_by_pipeline",
            "reason": "pre_open_pipeline_owns_full_line_delivery",
            "policy": cfg["line_policy"],
            "concise_reminder": False,
            "secret_values_printed": False,
        }
    message = build_line_message(window_id, generated_at, pipeline_status, dashboard_url, output_tail)
    line_module = importlib.import_module("reports.line_report_sender")
    line_sender = getattr(line_module, "send_line_report")
    line_sender(message)
    return {
        "send_attempted": True,
        "send_status": "sent",
        "policy": cfg["line_policy"],
        "concise_reminder": True,
        "message_chars": len(message),
        "secret_values_printed": False,
    }


def run_pipeline(python_bin: str, window_id: str, policy: TimeoutPolicy) -> dict[str, Any]:
    cfg = window_config(window_id)
    command = [python_bin, "scripts/run_pipeline.py", cfg["pipeline_type"], "--production-approved"]
    started = now_taipei()
    started_monotonic = time.monotonic()
    proc = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        output, _ = proc.communicate(timeout=policy.production_pipeline_timeout_seconds)
        ended = now_taipei()
        return {
            "status": "completed" if proc.returncode == 0 else "failed",
            "completed": subprocess.CompletedProcess(command, proc.returncode, output or ""),
            "pipeline_command": command,
            "pipeline_pid": proc.pid,
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "elapsed_seconds": int(time.monotonic() - started_monotonic),
            "timed_out": False,
            "termination": [],
        }
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode(errors="replace")
        termination = []
        proc.terminate()
        termination.append({"pid": proc.pid, "signal": "TERM", "sent": True})
        try:
            more, _ = proc.communicate(timeout=policy.terminate_grace_seconds)
            if more:
                partial += more
        except subprocess.TimeoutExpired:
            proc.kill()
            termination.append({"pid": proc.pid, "signal": "KILL", "sent": True})
            more, _ = proc.communicate()
            if more:
                partial += more
        ended = now_taipei()
        return {
            "status": "timed_out",
            "completed": subprocess.CompletedProcess(command, proc.returncode, partial or ""),
            "pipeline_command": command,
            "pipeline_pid": proc.pid,
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "elapsed_seconds": int(time.monotonic() - started_monotonic),
            "timed_out": True,
            "termination": termination,
        }


def _run_internal_artifact_command(args: list[str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    proc = subprocess.run([sys.executable, *args], cwd=REPO_ROOT, text=True, capture_output=True, timeout=180, check=False)
    return {"command": "python " + " ".join(args), "returncode": proc.returncode, "ok": proc.returncode == 0, "started_at": started, "stdout_tail": tail_text(proc.stdout, 3000), "stderr_tail": tail_text(proc.stderr, 3000)}


def post_delivery_artifact_wiring(*, window_id: str, generated_at: str) -> dict[str, Any]:
    run_date = generated_at[:10]
    commands: list[list[str]] = []
    if window_id == "pre_open_0700":
        commands.append(["scripts/orchestrator/build_formal_prediction_runtime_artifact.py", "--date", run_date, "--pretty"])
        commands.append(["scripts/orchestrator/archive_formal_forecast_daily_snapshot.py", "--date", run_date, "--pretty"])
    elif window_id == "post_close_1500":
        commands.append(["scripts/orchestrator/build_formal_prediction_review_runtime_artifact.py", "--date", run_date, "--pretty"])
        commands.append(["scripts/orchestrator/archive_formal_forecast_daily_snapshot.py", "--date", run_date, "--pretty"])
    commands.extend([
        ["scripts/orchestrator/build_four_window_dashboard_production_runtime_export_v1.py", "--pretty"],
        ["scripts/orchestrator/build_four_window_dashboard_route_preview.py", "--pretty"],
        ["scripts/orchestrator/publish_four_window_dashboard_preview_v1.py", "--pretty"],
    ])
    results = [_run_internal_artifact_command(cmd) for cmd in commands]
    return {"ok": all(item["ok"] for item in results), "window_id": window_id, "run_date": run_date, "actual_send_performed": False, "scheduler_modified": False, "commands": results}


def dry_run_result(args: argparse.Namespace, generated_at: str, run_id: str) -> dict[str, Any]:
    cfg = window_config(args.window)
    dashboard_dir = Path(args.dashboard_publish_dir)
    mail_env = Path(args.mail_env_file).expanduser()
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": run_id,
        "generated_at": generated_at,
        "mode": "dry_run_no_delivery",
        "scheduler_window": args.window,
        "schedule_time_taiwan": cfg["local_time"],
        "pipeline_type": cfg["pipeline_type"],
        "approved_delivery_env": env_enabled("STOCK_AI_APPROVED_DELIVERY"),
        "pipeline_would_run": True,
        "line_policy": cfg["line_policy"],
        "line_would_send": cfg["line_mode"] != "handled_by_pipeline",
        "email_policy": cfg["email_policy"],
        "email_would_send": True,
        "dashboard_policy": cfg["dashboard_policy"],
        "dashboard_would_publish": True,
        "fallback_state": cfg["fallback_state"],
        "content_state": cfg["fallback_state"],
        "line_delivery_status": "dry_run_not_sent",
        "line_delivery_reason": "dry_run_no_delivery",
        "email_delivery_status": "dry_run_not_sent",
        "dashboard_delivery_status": "dry_run_not_published",
        "dashboard_publish_dir": str(dashboard_dir),
        "dashboard_publish_dir_exists": dashboard_dir.exists(),
        "dashboard_publish_dir_writable": dashboard_dir.exists() and os.access(dashboard_dir, os.W_OK),
        "mail_env_file_exists": mail_env.exists(),
        "secret_values_printed": False,
        "trading_order_portfolio_action": False,
        "ok": True,
        "decision": "approved_scheduler_delivery_dry_run_completed",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run approved scheduler delivery.")
    parser.add_argument("--window", required=True, choices=sorted(WINDOWS))
    parser.add_argument("--dashboard-publish-dir", default=str(DEFAULT_DASHBOARD_DIR))
    parser.add_argument("--dashboard-url", default=DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL)
    parser.add_argument("--mail-env-file", default=str(DEFAULT_MAIL_ENV_FILE))
    parser.add_argument("--output", default="/tmp/approved_pre_open_delivery_result.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=None)
    parser.add_argument("--stale-threshold-seconds", type=int, default=None)
    parser.add_argument("--terminate-grace-seconds", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = window_config(args.window)
    generated = now_taipei()
    generated_at = generated.isoformat()
    run_id = f"approved-{args.window}-delivery-{generated.strftime('%Y%m%d-%H%M%S')}"

    if args.dry_run:
        result = dry_run_result(args, generated_at, run_id)
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(stable_json(result))
        return 0 if result["ok"] else 1

    if not env_enabled("STOCK_AI_APPROVED_DELIVERY"):
        raise SystemExit("STOCK_AI_APPROVED_DELIVERY=1 is required for approved delivery")

    base_policy = timeout_policy_from_env()
    policy = TimeoutPolicy(
        production_pipeline_timeout_seconds=args.timeout_seconds or window_timeout_seconds(args.window),
        production_pipeline_warning_seconds=base_policy.production_pipeline_warning_seconds,
        stale_process_threshold_seconds=args.stale_threshold_seconds or base_policy.stale_process_threshold_seconds,
        external_http_source_timeout_seconds=base_policy.external_http_source_timeout_seconds,
        market_data_source_timeout_seconds=base_policy.market_data_source_timeout_seconds,
        source_stage_soft_timeout_seconds=base_policy.source_stage_soft_timeout_seconds,
        terminate_grace_seconds=args.terminate_grace_seconds or base_policy.terminate_grace_seconds,
    )
    guard = evaluate_pre_open_run_guard(policy=policy) if args.window == "pre_open_0700" else None
    if guard is not None and not guard.allowed:
        result = build_guard_result(
            guard.status,
            args.window,
            policy,
            pipeline_command=[os.environ.get("PYTHON_BIN", sys.executable), "scripts/run_pipeline.py", cfg["pipeline_type"], "--production-approved"],
            log_path="logs/daily.log",
            diagnostics={"guard_decision": guard.to_dict(), "reason": guard.reason},
        )
        result.update({"task_id": TASK_ID, "run_id": run_id, "mode": "approved_delivery_guard_blocked", "pipeline_type": cfg["pipeline_type"], "line_delivery_status": "not_sent", "email_delivery_status": "not_sent", "dashboard_delivery_status": "not_published", "decision": guard.status})
        write_json(args.output, result)
        print(stable_json({key: result[key] for key in ["schema_version", "run_id", "window", "status", "ok", "decision"]}))
        return 1

    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
    progress = write_progress_artifact(args.window, generated_at, "pipeline_launched", "running", policy.production_pipeline_timeout_seconds)
    pipeline_run = run_pipeline(python_bin, args.window, policy)
    completed = pipeline_run["completed"]
    output = completed.stdout or ""
    if output:
        print(output, end="" if output.endswith("\n") else "\n")

    output_tail = tail_text(output, EMAIL_BODY_LIMIT)
    pipeline_diagnostics = build_pipeline_diagnostics(completed, output)
    pipeline_diagnostics.update({"pipeline_pid": pipeline_run["pipeline_pid"], "started_at": pipeline_run["started_at"], "ended_at": pipeline_run["ended_at"], "elapsed_seconds": pipeline_run["elapsed_seconds"], "termination": pipeline_run["termination"], "timeout_seconds": policy.production_pipeline_timeout_seconds})
    if pipeline_run["timed_out"]:
        progress = write_progress_artifact(args.window, generated_at, "pipeline_timed_out", "timed_out", policy.production_pipeline_timeout_seconds, pipeline_run["elapsed_seconds"])
        timeout_artifact = timeout_delivery_artifact(args.window, policy.production_pipeline_timeout_seconds, now_taipei().isoformat())
        result = build_guard_result(
            "timed_out",
            args.window,
            policy,
            pipeline_command=pipeline_run["pipeline_command"],
            pipeline_pid=pipeline_run["pipeline_pid"],
            started_at=pipeline_run["started_at"],
            ended_at=pipeline_run["ended_at"],
            elapsed_seconds=pipeline_run["elapsed_seconds"],
            return_code=completed.returncode,
            log_path="logs/daily.log",
            diagnostics={"pipeline": pipeline_diagnostics, "reason": "production pipeline exceeded hard timeout; delivery was not attempted"},
        )
        result.update({"task_id": TASK_ID, "run_id": run_id, "mode": "approved_delivery_timeout", "pipeline_type": cfg["pipeline_type"], "pipeline_status": "timed_out", "pipeline_completed": False, "content_state": "pipeline timed out; diagnostics available", "delivery_attempted": False, "line_delivery_status": "not_sent", "email_delivery_status": "not_sent", "dashboard_delivery_status": "not_published", "dashboard_publish_attempted": False, "late_delivery_suppressed": False, "timeout_artifact": timeout_artifact, "progress_artifact": progress, "reason": "child_pipeline_timeout", "safe_to_retry": True, "secret_values_printed": False, "trading_order_portfolio_action": False, "decision": "approved_scheduler_delivery_timed_out_no_delivery"})
        write_json(args.output, result)
        print(stable_json({key: result[key] for key in ["schema_version", "task_id", "run_id", "window", "status", "line_attempted", "email_attempted", "dashboard_attempted", "ok", "decision"]}))
        return 1

    pipeline_status = "completed" if completed.returncode == 0 else "failed"
    progress = write_progress_artifact(args.window, generated_at, "pipeline_completed", pipeline_status, policy.production_pipeline_timeout_seconds, pipeline_run["elapsed_seconds"])
    late = delivery_lateness(args.window)
    if pipeline_status == "completed" and late["late"]:
        progress = write_progress_artifact(args.window, generated_at, "late_delivery_suppressed", "completed_late_delivery_suppressed", policy.production_pipeline_timeout_seconds, pipeline_run["elapsed_seconds"])
        late_artifact = late_delivery_artifact(args.window, late, now_taipei().isoformat())
        result = {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "run_id": run_id,
            "generated_at": generated_at,
            "mode": "approved_delivery_late_suppressed",
            "scheduler_window": args.window,
            "schedule_time_taiwan": cfg["local_time"],
            "pipeline_type": cfg["pipeline_type"],
            "pipeline_returncode": completed.returncode,
            "pipeline_status": pipeline_status,
            "pipeline_completed": True,
            "delivery_attempted": False,
            "line_delivery_status": "not_sent",
            "email_delivery_status": "not_sent",
            "dashboard_delivery_status": "not_published",
            "line_attempted": False,
            "email_attempted": False,
            "dashboard_publish_attempted": False,
            "late_delivery_suppressed": True,
            "late_artifact": late_artifact,
            "progress_artifact": progress,
            "diagnostics": {"pipeline": pipeline_diagnostics, "lateness": late},
            "secret_values_printed": False,
            "trading_order_portfolio_action": False,
            "ok": True,
            "decision": "approved_scheduler_delivery_completed_late_delivery_suppressed",
        }
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(stable_json({key: result[key] for key in ["schema_version", "task_id", "run_id", "scheduler_window", "pipeline_status", "late_delivery_suppressed", "line_attempted", "email_attempted", "ok", "decision"]}))
        return 0
    try:
        post_run_artifacts = post_delivery_artifact_wiring(window_id=args.window, generated_at=generated_at)
    except Exception as exc:
        post_run_artifacts = {
            "status": "failed_non_blocking",
            "window": args.window,
            "generated_at": generated_at,
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "delivery_continues": True,
            "line_email_delivery_not_blocked": True,
        }
        print(stable_json({
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "run_id": run_id,
            "scheduler_window": args.window,
            "post_delivery_artifact_wiring_status": "failed_non_blocking",
            "error_type": exc.__class__.__name__,
            "delivery_continues": True,
            "line_email_delivery_not_blocked": True,
        }))
    dashboard = publish_dashboard(Path(args.dashboard_publish_dir), args.window, run_id, generated_at, pipeline_status, output_tail)
    try:
        email = send_delivery_email(Path(args.mail_env_file), args.window, run_id, generated_at, pipeline_status, args.dashboard_url, output_tail)
        email_ok = True
    except Exception as exc:  # pragma: no cover - runtime SMTP/config failure path
        email = {
            "send_attempted": True,
            "send_status": "failed",
            "error_type": exc.__class__.__name__,
            "secret_values_printed": False,
        }
        email_ok = False
    try:
        line = send_concise_line(args.window, generated_at, pipeline_status, args.dashboard_url, output_tail)
        line_ok = line.get("send_status") in {"sent", "handled_by_pipeline"}
    except Exception as exc:  # pragma: no cover - runtime LINE/config failure path
        line = {
            "send_attempted": True,
            "send_status": "failed",
            "policy": cfg["line_policy"],
            "error_type": exc.__class__.__name__,
            "secret_values_printed": False,
        }
        line_ok = False
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": run_id,
        "generated_at": generated_at,
        "mode": "approved_delivery",
        "scheduler_window": args.window,
        "schedule_time_taiwan": cfg["local_time"],
        "pipeline_type": cfg["pipeline_type"],
        "pipeline_returncode": completed.returncode,
        "pipeline_status": pipeline_status,
        "content_state": content_state(args.window, output_tail, pipeline_status),
        "delivery_policy": {
            "line": cfg["line_policy"],
            "email": cfg["email_policy"],
            "dashboard": cfg["dashboard_policy"],
        },
        "fallback_state": cfg["fallback_state"],
        "post_run_artifact_wiring": post_run_artifacts,
        "line_delivery": line,
        "line_delivery_status": line.get("send_status"),
        "line_delivery_reason": line.get("reason"),
        "email_delivery": email,
        "email_delivery_status": email.get("send_status"),
        "dashboard_delivery": dashboard,
        "dashboard_delivery_status": dashboard.get("publish_status"),
        "dashboard_url": args.dashboard_url,
        "pipeline_completed": pipeline_status == "completed",
        "delivery_attempted": True,
        "late_delivery_suppressed": False,
        "progress_artifact": progress,
        "diagnostics": {
            "pipeline": pipeline_diagnostics,
            "user_facing_report_contains_traceback": contains_traceback(
                user_facing_report_content(args.window, pipeline_status, output_tail)
            ),
        },
        "secret_values_printed": False,
        "trading_order_portfolio_action": False,
        "ok": completed.returncode == 0 and email_ok and line_ok,
        "decision": "approved_scheduler_delivery_completed"
        if completed.returncode == 0 and email_ok and line_ok
        else "approved_scheduler_delivery_completed_with_delivery_failure",
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(stable_json({key: result[key] for key in ["schema_version", "task_id", "run_id", "scheduler_window", "pipeline_status", "dashboard_url", "secret_values_printed", "trading_order_portfolio_action", "ok", "decision"]}))
    return completed.returncode if completed.returncode != 0 else 0 if email_ok and line_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
