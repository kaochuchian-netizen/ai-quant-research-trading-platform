#!/usr/bin/env python3
"""Private static dashboard publish helper for controlled delivery runtime."""

from __future__ import annotations

import argparse
import html
import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_INPUT = Path("templates/dashboard_delivery_gate_result.example.json")
SCHEMA_VERSION = "private_static_dashboard_publish_v1"
TASK_ID = "AI-DEV-107"
SIDE_EFFECTS_BASE = {
    "read_secrets": False,
    "sent_notification": False,
    "sent_email": False,
    "called_smtp": False,
    "called_gmail_api": False,
    "sent_line_push": False,
    "called_line_api": False,
    "deployed_dashboard": False,
    "created_api_server": False,
    "placed_trade_order": False,
    "modified_portfolio": False,
    "wrote_persistent_store": False,
    "modified_cron": False,
    "modified_systemd": False,
    "modified_timer": False,
    "modified_service": False,
    "modified_schedule_or_service": False,
}
SAFETY = {
    "controlled_delivery_runtime": True,
    "dry_run_default": True,
    "delivery_gate_required": True,
    "no_token_printing": True,
    "no_secret_logging": True,
    "no_secret_read": True,
    "no_line_push_by_default": True,
    "no_email_send_by_default": True,
    "no_dashboard_publish_by_default": True,
    "no_smtp_call_by_default": True,
    "no_gmail_api_call_by_default": True,
    "no_api_server_created": True,
    "no_persistent_store_writes": True,
    "no_portfolio_actions": True,
    "no_cron_modification": True,
    "no_systemd_modification": True,
    "no_timer_modification": True,
    "no_service_modification": True,
    "no_schedule_service_changes": True,
    "trading_instruction": False,
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("input JSON root must be an object")
    return payload


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def stable_json(payload: Any, pretty: bool) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    return f"{text}\n" if pretty else text


def now_taipei() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat()


def render_html(gate_result: dict[str, Any], generated_at: str) -> str:
    gate = as_dict(gate_result.get("dashboard_delivery_gate"))
    static_summary = as_dict(gate.get("static_page_summary"))
    title = str(static_summary.get("page_title") or "Stock AI Private Dashboard")
    rows = [
        ("Generated At", generated_at),
        ("Review Status", gate.get("review_status")),
        ("Delivery Allowed", gate.get("delivery_allowed")),
        ("Dashboard Channel Enabled", gate.get("dashboard_channel_enabled")),
        ("Publish Status", gate.get("publish_status")),
        ("Preview ID", gate.get("preview_id")),
        ("Report Date", gate.get("report_date")),
        ("Warning Badges", len(gate.get("warning_badges") or [])),
    ]
    body = "\n".join(
        f"<tr><th>{html.escape(str(label))}</th><td>{html.escape(str(value))}</td></tr>" for label, value in rows
    )
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #17202a; }}
    main {{ max-width: 920px; margin: 0 auto; }}
    h1 {{ font-size: 28px; margin-bottom: 8px; }}
    .status {{ margin: 0 0 24px; color: #566573; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #d6dbdf; padding: 12px; text-align: left; vertical-align: top; }}
    th {{ width: 260px; background: #f8f9f9; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(title)}</h1>
  <p class="status">Private static dashboard preview. No API server is created.</p>
  <table>{body}</table>
</main>
</body>
</html>
"""


def publish_files(gate_result: dict[str, Any], publish_dir: Path, generated_at: str) -> list[str]:
    publish_dir.mkdir(parents=True, exist_ok=True)
    index_path = publish_dir / "index.html"
    manifest_path = publish_dir / "publish_manifest.json"
    index_path.write_text(render_html(gate_result, generated_at), encoding="utf-8")
    manifest = {
        "schema_version": "private_static_dashboard_publish_manifest_v1",
        "generated_at": generated_at,
        "source_run_id": gate_result.get("run_id"),
        "source_decision": gate_result.get("decision"),
        "index_path": str(index_path),
    }
    manifest_path.write_text(stable_json(manifest, True), encoding="utf-8")
    return [str(index_path), str(manifest_path)]


def build_result(gate_result: dict[str, Any], publish_dir: Path, publish: bool) -> dict[str, Any]:
    generated_at = now_taipei()
    gate = as_dict(gate_result.get("dashboard_delivery_gate"))
    delivery_allowed = gate.get("delivery_allowed") is True
    channel_enabled = gate.get("dashboard_channel_enabled") is True
    publish_allowed = delivery_allowed and channel_enabled
    dry_run = not publish
    side_effects = deepcopy(SIDE_EFFECTS_BASE)
    written_files: list[str] = []
    if publish and publish_allowed:
        written_files = publish_files(gate_result, publish_dir, generated_at)
        side_effects["deployed_dashboard"] = True
    publish_status = (
        "published_private_static_dashboard"
        if written_files
        else "blocked_by_dashboard_gate"
        if publish
        else "dry_run_not_published"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": f"private-static-dashboard-publish-{generated_at}",
        "generated_at": generated_at,
        "mode": "publish_private_static_dashboard" if publish else "dry_run_no_publish",
        "gate_status": {
            "delivery_allowed": delivery_allowed,
            "dashboard_channel_enabled": channel_enabled,
            "publish_allowed": publish_allowed,
            "blocked_reasons": [
                key
                for key, value in {
                    "delivery_allowed": delivery_allowed,
                    "dashboard_channel_enabled": channel_enabled,
                }.items()
                if value is not True
            ],
        },
        "dashboard_publish_path": str(publish_dir),
        "dashboard_private_url_hint": f"file://{publish_dir.resolve()}/index.html",
        "publish_requested": publish,
        "dry_run": dry_run,
        "publish_status": publish_status,
        "written_files": written_files,
        "side_effects": side_effects,
        "safety": deepcopy(SAFETY),
        "ok": True,
        "decision": "private_static_dashboard_publish_completed"
        if written_files
        else "private_static_dashboard_publish_blocked_pending_approval"
        if publish
        else "private_static_dashboard_publish_dry_run_completed",
        "next_recommendation": "Open the file URL after manual publish, or keep dashboard publish blocked until explicit confirmation and gate approval.",
    }


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish a private static dashboard after gate approval.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--publish-dir", default="/tmp/stock_ai_private_static_dashboard")
    parser.add_argument("--output", required=True)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Do not publish. This is the default.")
    parser.add_argument("--publish", action="store_true", help="Write private static files only if the dashboard gate is open.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run and args.publish:
        raise SystemExit("--dry-run and --publish cannot be used together")
    result = build_result(load_json(Path(args.input)), Path(args.publish_dir), args.publish)
    rendered = write_json(result, Path(args.output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
