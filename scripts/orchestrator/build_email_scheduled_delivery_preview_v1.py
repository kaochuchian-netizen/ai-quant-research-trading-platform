#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.orchestrator.approved_pre_open_delivery import (
    DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL,
    build_email_body,
)

OUT_JSON = ROOT / "artifacts/runtime/email_scheduled_delivery_preview_latest.json"
OUT_MD = ROOT / "artifacts/runtime/email_scheduled_delivery_preview_latest.md"
TAIPEI = ZoneInfo("Asia/Taipei")
FORBIDDEN = (
    "pipeline_type",
    "pipeline_run_id",
    "analysis/output",
    "Strategy Ranking",
    "historical CSV",
    "advisory_only",
    "sample artifact",
    "Report content:",
    "stock_analysis_reports_available",
)


def stable(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_preview() -> dict[str, object]:
    generated_at = datetime.now(TAIPEI).replace(microsecond=0).isoformat()
    body = build_email_body(
        "pre_open_0700",
        "dry-run-preview",
        generated_at,
        "completed",
        DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL,
        "",
    )
    hits = [word for word in FORBIDDEN if word in body]
    return {
        "schema_version": "email_scheduled_delivery_preview_v1",
        "task_id": "AI-DEV-161",
        "artifact_type": "email_scheduled_delivery_preview",
        "generated_at": generated_at,
        "window": "pre_open_0700",
        "is_actual_send": False,
        "safety_mode": "dry_run_preview_only",
        "dashboard_url": DEFAULT_DECISION_INTELLIGENCE_DASHBOARD_URL,
        "message_body": body,
        "forbidden_content_check": {
            "ok": not hits,
            "hits": hits,
            "checked_terms": list(FORBIDDEN),
        },
        "actual_email_sent": False,
        "actual_line_sent": False,
        "scheduler_modified": False,
        "production_pipeline_executed": False,
    }


def write_md(data: dict[str, object]) -> str:
    body = str(data["message_body"])
    return "\n".join([
        "# Email Scheduled Delivery Preview V1",
        "",
        f"- task_id: {data['task_id']}",
        f"- generated_at: {data['generated_at']}",
        f"- is_actual_send: {data['is_actual_send']}",
        f"- safety_mode: {data['safety_mode']}",
        "",
        "## Message Body",
        "",
        "```text",
        body,
        "```",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    data = build_preview()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(stable(data), encoding="utf-8")
    OUT_MD.write_text(write_md(data), encoding="utf-8")
    summary = {
        "ok": bool(data["forbidden_content_check"]["ok"]),
        "json_path": str(OUT_JSON),
        "markdown_path": str(OUT_MD),
        "is_actual_send": data["is_actual_send"],
        "forbidden_hits": data["forbidden_content_check"]["hits"],
    }
    print(stable(summary) if args.pretty else json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
