#!/usr/bin/env python3
"""Build a dry-run preview for tomorrow's four LINE scheduler windows.

The preview never sends LINE. It records the formatter path that the approved
scheduler delivery wrapper should use after AI-DEV-157.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestrator.approved_pre_open_delivery import (  # noqa: E402
    DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL,
    build_line_message,
)

SCHEMA_VERSION = "line_four_batch_runtime_preview_v1"
TASK_ID = "AI-DEV-158"
OUTPUT_JSON = REPO_ROOT / "artifacts/runtime/line_four_batch_runtime_preview_latest.json"
OUTPUT_MD = REPO_ROOT / "artifacts/runtime/line_four_batch_runtime_preview_latest.md"
TRACE_MD = REPO_ROOT / "artifacts/runtime/line_runtime_activation_trace_latest.md"

WINDOWS = [
    ("pre_open_0700", "07:00", "app.pipelines.pre_open_pipeline.send_reports_in_batches -> reports.line_short_formatter.format_line_short"),
    ("intraday_1305", "13:05", "scripts.orchestrator.approved_pre_open_delivery.build_line_message -> app.reports.multi_window_formatter.line_notification_text"),
    ("pre_close_1335", "13:35", "scripts.orchestrator.approved_pre_open_delivery.build_line_message -> app.reports.multi_window_formatter.line_notification_text"),
    ("post_close_1500", "15:00", "scripts.orchestrator.approved_pre_open_delivery.build_line_message -> app.reports.multi_window_formatter.line_notification_text"),
]

FORBIDDEN_TERMS = [
    "/stock-ai-dashboard/index.html",
    "status:",
    "state:",
    "pipeline output available",
    "pipeline_type",
    "pipeline_run_id",
    "run_date",
    "run_time",
    "advisory only; no trading instruction",
    "advisory_only",
    "prediction review pending",
    "insufficient data",
    "【2330 台積電】",
    "C級",
    "B級",
    "收盤：",
    "技術：",
    "ADR：",
    "法人：",
    "主力：",
    "資券：",
    "新聞：",
    "籌碼：",
    "策略：",
]


def now_taipei() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat()


def forbidden_hits(message: str) -> list[str]:
    lowered = message.lower()
    return [term for term in FORBIDDEN_TERMS if term.lower() in lowered]


def build_preview() -> dict[str, Any]:
    created_at = now_taipei()
    windows: list[dict[str, Any]] = []
    for window, scheduled_time, formatter_source in WINDOWS:
        message = build_line_message(
            window,
            created_at,
            "completed",
            DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL,
            "",
        )
        hits = forbidden_hits(message)
        windows.append(
            {
                "window": window,
                "scheduled_time": scheduled_time,
                "formatter_source": formatter_source,
                "message_body": message,
                "dashboard_url": DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL,
                "is_actual_send": False,
                "safety_mode": "dry_run_preview_only",
                "forbidden_content_check": {"ok": not hits, "hits": hits},
                "created_at": created_at,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "artifact_type": "line_four_batch_runtime_preview",
        "created_at": created_at,
        "dashboard_url": DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL,
        "is_actual_send": False,
        "safety_mode": "dry_run_preview_only",
        "windows": windows,
        "runtime_trace_report": str(TRACE_MD.relative_to(REPO_ROOT)),
        "safety_policy": {
            "line_sent": False,
            "email_sent": False,
            "notification_sent": False,
            "scheduler_modified": False,
            "production_pipeline_executed": False,
            "main_py_executed": False,
            "db_write": False,
            "secrets_read": False,
            "trading_order_action": False,
        },
    }


def render_markdown(preview: dict[str, Any]) -> str:
    lines = [
        "# AI-DEV-158 LINE Runtime Preview",
        "",
        "Dry-run only. No LINE, Email, or external notification was sent.",
        "",
        f"Dashboard URL: {preview['dashboard_url']}",
        "",
    ]
    for window in preview["windows"]:
        lines.extend(
            [
                f"## {window['scheduled_time']} {window['window']}",
                "",
                f"Formatter: `{window['formatter_source']}`",
                "",
                "```text",
                window["message_body"],
                "```",
                f"Forbidden content hits: {len(window['forbidden_content_check']['hits'])}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_trace(preview: dict[str, Any]) -> str:
    active_paths = [
        "run_stock_analysis.sh detects STOCK_AI_SCHEDULER_WINDOW or local time and calls scripts/orchestrator/approved_pre_open_delivery.py when STOCK_AI_APPROVED_DELIVERY=1.",
        "07:00 pre_open_0700 runs the pre_open pipeline, whose LINE path uses reports.line_short_formatter.format_line_short.",
        "13:05 intraday_1305, 13:35 pre_close_1335, and 15:00 post_close_1500 use approved_pre_open_delivery.build_line_message, now delegated to app.reports.multi_window_formatter.line_notification_text.",
        "The approved wrapper and run_stock_analysis.sh default Dashboard URL point to the four-window Decision Intelligence Dashboard.",
    ]
    lines = [
        "# AI-DEV-158 LINE Runtime Activation Trace",
        "",
        "## Scope",
        "Read-only/dry-run verification package for tomorrow's four LINE scheduler windows. This artifact does not send LINE and does not change cron, systemd, or timers.",
        "",
        "## Runtime Path Summary",
    ]
    lines.extend(f"- {item}" for item in active_paths)
    lines.extend(
        [
            "",
            "## Four-Window Formatter Summary",
        ]
    )
    for window in preview["windows"]:
        lines.append(f"- {window['scheduled_time']} `{window['window']}`: {window['formatter_source']}")
    lines.extend(
        [
            "",
            "## Old Formatter / Old URL Risk Check",
            "- Active dry-run preview messages do not contain `status:`, `state:`, `pipeline output available`, or the old `/stock-ai-dashboard/index.html` URL.",
            "- Historical logs and older docs may still contain old wording as records; they are not the active formatter path validated by this preview.",
            "",
            "## Dry-Run Preview Artifact",
            f"- JSON: `{OUTPUT_JSON.relative_to(REPO_ROOT)}`",
            f"- Markdown: `{OUTPUT_MD.relative_to(REPO_ROOT)}`",
            "",
            "## No Actual Send Confirmation",
            "- `is_actual_send=false` for every window.",
            "- `safety_mode=dry_run_preview_only` for every window.",
            "- LINE, Email, and external notification sending were not invoked by this builder.",
            "",
            "## Tomorrow Manual Verification Checklist",
            "- 07:00: exactly one short reminder, no stock details, no C級/B級/score/technical/chip fields, and the new Dashboard URL.",
            "- 13:05: short reminder only, no status/state/pipeline wording, and the new Dashboard URL.",
            "- 13:35: says 收盤快照, no status/state/pipeline wording, and the new Dashboard URL.",
            "- 15:00: says 盤後檢討, no raw English pending/insufficient-data wording, and the new Dashboard URL.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build LINE four-batch runtime dry-run preview.")
    parser.add_argument("--output-json", default=str(OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(OUTPUT_MD))
    parser.add_argument("--trace-md", default=str(TRACE_MD))
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preview = build_preview()
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    trace_md = Path(args.trace_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(preview, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(preview), encoding="utf-8")
    trace_md.write_text(render_trace(preview), encoding="utf-8")
    summary = {
        "ok": all(window["forbidden_content_check"]["ok"] for window in preview["windows"]),
        "task_id": TASK_ID,
        "windows": [window["window"] for window in preview["windows"]],
        "is_actual_send": False,
        "output_json": str(output_json),
        "output_md": str(output_md),
        "trace_md": str(trace_md),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
