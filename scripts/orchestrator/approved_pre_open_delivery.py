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
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
EMAIL_BODY_LIMIT = 14000
LINE_BODY_LIMIT = 520
TRACEBACK_MARKERS = (
    "Traceback (most recent call last):",
    "ShioajiClientError:",
    "Exception:",
)
WINDOWS = {
    "pre_open_0700": {
        "label": "07:00 pre-open",
        "local_time": "07:00",
        "pipeline_type": "pre_open",
        "line_policy": "full report handled by production pre_open pipeline",
        "line_mode": "handled_by_pipeline",
        "email_policy": "full scheduled delivery summary",
        "dashboard_policy": "publish latest full scheduler snapshot",
        "fallback_state": "pipeline output tail is included if report content is partial",
    },
    "intraday_1305": {
        "label": "13:05 intraday",
        "local_time": "13:05",
        "pipeline_type": "intraday",
        "line_policy": "concise reminder only with key status and dashboard URL",
        "line_mode": "concise_reminder",
        "email_policy": "full report from validated pipeline output when available",
        "dashboard_policy": "publish latest intraday scheduler snapshot",
        "fallback_state": "report content pending / insufficient data if pipeline only returns context summary",
    },
    "pre_close_1335": {
        "label": "13:35 pre-close",
        "local_time": "13:35",
        "pipeline_type": "pre_close",
        "line_policy": "concise risk / market status reminder only; no trading instruction",
        "line_mode": "concise_reminder",
        "email_policy": "full report from validated pipeline output when available",
        "dashboard_policy": "publish latest pre-close scheduler snapshot",
        "fallback_state": "report content pending / insufficient data if pipeline only returns context summary",
    },
    "post_close_1500": {
        "label": "15:00 post-close / prediction review",
        "local_time": "15:00",
        "pipeline_type": "post_close",
        "line_policy": "one concise summary reminder with dashboard URL",
        "line_mode": "concise_reminder",
        "email_policy": "full post-close / prediction review report, including pending state",
        "dashboard_policy": "publish latest post-close / prediction review snapshot",
        "fallback_state": "prediction review pending / insufficient data when review records are unavailable",
    },
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
        return (
            f"{cfg['label']} pipeline did not produce validated report content. "
            "The delivery artifact keeps error details in diagnostics for operator review."
        )
    if contains_traceback(output_tail):
        return (
            "Validated report content is unavailable because the pipeline output included "
            "runtime diagnostics. See the delivery artifact diagnostics."
        )
    return tail_text(output_tail, EMAIL_BODY_LIMIT)


def build_pipeline_diagnostics(completed: subprocess.CompletedProcess[str], output: str) -> dict[str, Any]:
    return {
        "pipeline_returncode": completed.returncode,
        "raw_output_tail": tail_text(output, EMAIL_BODY_LIMIT),
        "raw_output_contains_traceback": contains_traceback(output),
        "raw_output_chars": len(output),
    }


def render_dashboard(window_id: str, run_id: str, generated_at: str, pipeline_status: str, output_tail: str) -> str:
    cfg = window_config(window_id)
    report_content = user_facing_report_content(window_id, pipeline_status, output_tail)
    escaped_report_content = html.escape(report_content)
    rows = [
        ("Generated At", generated_at),
        ("Run ID", run_id),
        ("Scheduler Window", window_id),
        ("Local Time", cfg["local_time"]),
        ("Pipeline", cfg["pipeline_type"]),
        ("Pipeline Status", pipeline_status),
        ("Content State", content_state(window_id, output_tail, pipeline_status)),
        ("LINE", cfg["line_policy"]),
        ("Email", cfg["email_policy"]),
        ("Dashboard", cfg["dashboard_policy"]),
        ("Diagnostics", "stored in delivery artifact; not rendered as the main report"),
        ("Trading", "disabled"),
    ]
    body = "\n".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
        for label, value in rows
    )
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stock AI Scheduler Dashboard</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 28px; color: #17202a; }}
    main {{ max-width: 1040px; margin: 0 auto; }}
    h1 {{ font-size: 28px; margin: 0 0 8px; }}
    .status {{ margin: 0 0 22px; color: #566573; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border-bottom: 1px solid #d6dbdf; padding: 12px; text-align: left; vertical-align: top; }}
    th {{ width: 230px; background: #f8f9f9; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #f8f9f9; border: 1px solid #d6dbdf; padding: 14px; }}
  </style>
</head>
<body>
<main>
  <h1>Stock AI {html.escape(cfg["label"])} Dashboard</h1>
  <p class="status">Approved scheduler delivery snapshot. Advisory only; no trading action is authorized.</p>
  <table>{body}</table>
  <h2>Report Content</h2>
  <pre>{escaped_report_content}</pre>
</main>
</body>
</html>
"""


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


def build_email_body(window_id: str, run_id: str, generated_at: str, pipeline_status: str, dashboard_url: str, output_tail: str) -> str:
    cfg = window_config(window_id)
    report_content = user_facing_report_content(window_id, pipeline_status, output_tail)
    return (
        f"Stock AI approved {cfg['label']} delivery completed.\n\n"
        f"run_id: {run_id}\n"
        f"generated_at: {generated_at}\n"
        f"scheduler_window: {window_id}\n"
        f"pipeline_type: {cfg['pipeline_type']}\n"
        f"pipeline_status: {pipeline_status}\n"
        f"content_state: {content_state(window_id, output_tail, pipeline_status)}\n"
        f"dashboard_url: {dashboard_url}\n"
        f"line_policy: {cfg['line_policy']}\n"
        f"email_policy: {cfg['email_policy']}\n"
        f"dashboard_policy: {cfg['dashboard_policy']}\n"
        "trading/order/portfolio action: no\n\n"
        "Report content:\n"
        f"{tail_text(report_content, EMAIL_BODY_LIMIT)}"
    )


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
    cfg = window_config(window_id)
    message = (
        f"[Stock AI] {cfg['label']} update\n"
        f"status: {pipeline_status}\n"
        f"state: {content_state(window_id, output_tail, pipeline_status)}\n"
        f"dashboard: {dashboard_url}\n"
        "advisory only; no trading instruction."
    )
    return tail_text(message, LINE_BODY_LIMIT)


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


def run_pipeline(python_bin: str, window_id: str) -> subprocess.CompletedProcess[str]:
    cfg = window_config(window_id)
    return subprocess.run(
        [python_bin, "scripts/run_pipeline.py", cfg["pipeline_type"], "--production-approved"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


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
    parser.add_argument("--dashboard-url", default="http://35.201.242.167/stock-ai-dashboard/index.html")
    parser.add_argument("--mail-env-file", default=str(DEFAULT_MAIL_ENV_FILE))
    parser.add_argument("--output", default="/tmp/approved_pre_open_delivery_result.json")
    parser.add_argument("--dry-run", action="store_true")
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

    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
    completed = run_pipeline(python_bin, args.window)
    output = completed.stdout or ""
    if output:
        print(output, end="" if output.endswith("\n") else "\n")

    pipeline_status = "completed" if completed.returncode == 0 else "failed"
    output_tail = tail_text(output, EMAIL_BODY_LIMIT)
    pipeline_diagnostics = build_pipeline_diagnostics(completed, output)
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
        "line_delivery": line,
        "line_delivery_status": line.get("send_status"),
        "line_delivery_reason": line.get("reason"),
        "email_delivery": email,
        "email_delivery_status": email.get("send_status"),
        "dashboard_delivery": dashboard,
        "dashboard_delivery_status": dashboard.get("publish_status"),
        "dashboard_url": args.dashboard_url,
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
