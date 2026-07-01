#!/usr/bin/env python3
"""Approved 07:00 pre-open delivery runner.

This runner is intentionally narrow: it only supports the pre_open_0700 window
after an operator has set STOCK_AI_APPROVED_DELIVERY=1 in the scheduler entry.
"""

from __future__ import annotations

import argparse
import html
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


SCHEMA_VERSION = "approved_pre_open_delivery_v1"
TASK_ID = "AI-DEV-111"
WINDOW = "pre_open_0700"
DEFAULT_DASHBOARD_DIR = Path("/var/www/stock-ai-dashboard")
DEFAULT_MAIL_ENV_FILE = Path("~/.config/stock-ai-orchestrator/mail.env")
EMAIL_BODY_LIMIT = 14000


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


def render_dashboard(run_id: str, generated_at: str, pipeline_status: str, output_tail: str) -> str:
    escaped_tail = html.escape(output_tail)
    rows = [
        ("Generated At", generated_at),
        ("Run ID", run_id),
        ("Scheduler Window", WINDOW),
        ("Pipeline", "pre_open"),
        ("Pipeline Status", pipeline_status),
        ("LINE", "sent by production pre_open pipeline"),
        ("Email", "scheduled delivery summary"),
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
  <title>Stock AI 07:00 Pre-open Dashboard</title>
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
  <h1>Stock AI 07:00 Pre-open Dashboard</h1>
  <p class="status">Approved scheduler delivery snapshot. Advisory only; no trading action is authorized.</p>
  <table>{body}</table>
  <h2>Run Output Tail</h2>
  <pre>{escaped_tail}</pre>
</main>
</body>
</html>
"""


def publish_dashboard(publish_dir: Path, run_id: str, generated_at: str, pipeline_status: str, output_tail: str) -> dict[str, Any]:
    publish_dir.mkdir(parents=True, exist_ok=True)
    index_path = publish_dir / "index.html"
    manifest_path = publish_dir / "publish_manifest.json"
    index_path.write_text(
        render_dashboard(run_id, generated_at, pipeline_status, output_tail),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "approved_pre_open_dashboard_manifest_v1",
        "task_id": TASK_ID,
        "run_id": run_id,
        "generated_at": generated_at,
        "scheduler_window": WINDOW,
        "pipeline_status": pipeline_status,
        "index_path": str(index_path),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "publish_attempted": True,
        "publish_status": "published",
        "index_path": str(index_path),
        "manifest_path": str(manifest_path),
    }


def build_email_body(run_id: str, generated_at: str, pipeline_status: str, dashboard_url: str, output_tail: str) -> str:
    return (
        "Stock AI approved 07:00 pre-open delivery completed.\n\n"
        f"run_id: {run_id}\n"
        f"generated_at: {generated_at}\n"
        f"scheduler_window: {WINDOW}\n"
        f"pipeline_status: {pipeline_status}\n"
        f"dashboard_url: {dashboard_url}\n"
        "trading/order/portfolio action: no\n\n"
        "Run output tail:\n"
        f"{tail_text(output_tail, EMAIL_BODY_LIMIT)}"
    )


def send_delivery_email(env_file: Path, run_id: str, generated_at: str, pipeline_status: str, dashboard_url: str, output_tail: str) -> dict[str, Any]:
    expanded = env_file.expanduser()
    if expanded.exists():
        load_env_file(expanded)
    config = load_mail_config()
    subject = f"[Stock AI] 07:00 pre-open approved delivery {generated_at}"
    message = build_message(
        config,
        subject,
        build_email_body(run_id, generated_at, pipeline_status, dashboard_url, output_tail),
    )
    send_message(config, message)
    return {
        "send_attempted": True,
        "send_status": "sent",
        "env_file_checked": True,
        "env_file_exists": expanded.exists(),
        "secret_values_printed": False,
    }


def run_pipeline(python_bin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [python_bin, "scripts/run_pipeline.py", "pre_open", "--production-approved"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def dry_run_result(args: argparse.Namespace, generated_at: str, run_id: str) -> dict[str, Any]:
    dashboard_dir = Path(args.dashboard_publish_dir)
    mail_env = Path(args.mail_env_file).expanduser()
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": run_id,
        "generated_at": generated_at,
        "mode": "dry_run_no_delivery",
        "scheduler_window": args.window,
        "approved_delivery_env": env_enabled("STOCK_AI_APPROVED_DELIVERY"),
        "pipeline_would_run": args.window == WINDOW,
        "line_would_send": args.window == WINDOW,
        "email_would_send": args.window == WINDOW,
        "dashboard_would_publish": args.window == WINDOW,
        "dashboard_publish_dir": str(dashboard_dir),
        "dashboard_publish_dir_exists": dashboard_dir.exists(),
        "dashboard_publish_dir_writable": dashboard_dir.exists() and os.access(dashboard_dir, os.W_OK),
        "mail_env_file_exists": mail_env.exists(),
        "secret_values_printed": False,
        "trading_order_portfolio_action": False,
        "ok": args.window == WINDOW,
        "decision": "approved_pre_open_delivery_dry_run_completed" if args.window == WINDOW else "unsupported_window",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run approved 07:00 pre-open delivery.")
    parser.add_argument("--window", required=True)
    parser.add_argument("--dashboard-publish-dir", default=str(DEFAULT_DASHBOARD_DIR))
    parser.add_argument("--dashboard-url", default="http://35.201.242.167/stock-ai-dashboard/index.html")
    parser.add_argument("--mail-env-file", default=str(DEFAULT_MAIL_ENV_FILE))
    parser.add_argument("--output", default="/tmp/approved_pre_open_delivery_result.json")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated = now_taipei()
    generated_at = generated.isoformat()
    run_id = f"approved-pre-open-delivery-{generated.strftime('%Y%m%d-%H%M%S')}"

    if args.window != WINDOW:
        raise SystemExit(f"unsupported approved delivery window: {args.window}")

    if args.dry_run:
        result = dry_run_result(args, generated_at, run_id)
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(stable_json(result))
        return 0 if result["ok"] else 1

    if not env_enabled("STOCK_AI_APPROVED_DELIVERY"):
        raise SystemExit("STOCK_AI_APPROVED_DELIVERY=1 is required for approved delivery")

    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
    completed = run_pipeline(python_bin)
    output = completed.stdout or ""
    if output:
        print(output, end="" if output.endswith("\n") else "\n")

    pipeline_status = "completed" if completed.returncode == 0 else "failed"
    output_tail = tail_text(output, EMAIL_BODY_LIMIT)
    dashboard = publish_dashboard(Path(args.dashboard_publish_dir), run_id, generated_at, pipeline_status, output_tail)
    try:
        email = send_delivery_email(Path(args.mail_env_file), run_id, generated_at, pipeline_status, args.dashboard_url, output_tail)
        email_ok = True
    except Exception as exc:  # pragma: no cover - runtime SMTP/config failure path
        email = {
            "send_attempted": True,
            "send_status": "failed",
            "error_type": exc.__class__.__name__,
            "secret_values_printed": False,
        }
        email_ok = False
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": run_id,
        "generated_at": generated_at,
        "mode": "approved_delivery",
        "scheduler_window": args.window,
        "pipeline_returncode": completed.returncode,
        "pipeline_status": pipeline_status,
        "line_delivery": "handled_by_pre_open_pipeline",
        "email_delivery": email,
        "dashboard_delivery": dashboard,
        "dashboard_url": args.dashboard_url,
        "secret_values_printed": False,
        "trading_order_portfolio_action": False,
        "ok": completed.returncode == 0 and email_ok,
        "decision": "approved_pre_open_delivery_completed"
        if completed.returncode == 0 and email_ok
        else "approved_pre_open_delivery_completed_with_delivery_failure",
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(stable_json({key: result[key] for key in ["schema_version", "task_id", "run_id", "scheduler_window", "pipeline_status", "dashboard_url", "secret_values_printed", "trading_order_portfolio_action", "ok", "decision"]}))
    return completed.returncode if completed.returncode != 0 else 0 if email_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
