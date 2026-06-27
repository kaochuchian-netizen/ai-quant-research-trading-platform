#!/usr/bin/env python3
"""Dry-run GCP runtime handoff runner skeleton.

This wrapper is intentionally non-destructive. It validates a handoff request and
prints the plan a future GCP resident runner or n8n relay would follow. It never
starts n8n, calls Dify, opens SSH, sends notifications, trades, or writes
production data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from validate_gcp_runtime_handoff_request import load_request, validate_request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan a GCP runtime handoff without executing runtime actions.")
    parser.add_argument("--request", default="templates/gcp_runtime_handoff_request.example.json")
    parser.add_argument("--execute", action="store_true", help="Reserved for future GCP resident runner use.")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def build_plan(request: dict[str, Any], execute_requested: bool) -> dict[str, Any]:
    validation = validate_request(request)
    request_id = validation.get("request_id")
    ai_dev_id = validation.get("ai_dev_id")
    expected_result_path = request.get("result_collection", {}).get("sanitized_result_path")
    safety_gates_checked = sorted(request.get("safety_gates", {}).keys()) if isinstance(request.get("safety_gates"), dict) else []
    blocked_reason = None
    if not validation.get("ok"):
        blocked_reason = "request validation failed"
    elif execute_requested:
        blocked_reason = "execute mode is not implemented in repo-side skeleton; GCP resident runner must own runtime execution"

    return {
        "ok": validation.get("ok") and not execute_requested,
        "mode": "execute_requested_blocked" if execute_requested else "dry_run_plan",
        "request_id": request_id,
        "ai_dev_id": ai_dev_id,
        "would_execute": bool(validation.get("ok")),
        "executed": False,
        "blocked": blocked_reason is not None,
        "blocked_reason": blocked_reason,
        "expected_result_path": expected_result_path,
        "safety_gates_checked": safety_gates_checked,
        "plan_steps": [
            "read repo-side handoff request",
            "validate forbidden runtime actions and secret markers",
            "wait for merged repo request to be picked up by GCP resident runner or n8n relay",
            "write local-only runtime outputs under approved GCP runtime state path",
            "publish sanitized result summary back through a future repo-side package task",
        ],
        "side_effects": {
            "ssh_attempted": False,
            "n8n_started": False,
            "dify_runtime_called": False,
            "chatgpt_openai_api_called": False,
            "notification_sent": False,
            "production_db_modified": False,
            "trading_or_order_execution": False,
            "runtime_queue_modified": False,
        },
        "validation": validation,
    }


def main() -> int:
    args = parse_args()
    data, load_errors = load_request(Path(args.request))
    if data is None:
        result = {
            "ok": False,
            "mode": "dry_run_plan",
            "request_id": None,
            "ai_dev_id": None,
            "would_execute": False,
            "executed": False,
            "blocked": True,
            "blocked_reason": "request load failed",
            "expected_result_path": None,
            "safety_gates_checked": [],
            "errors": load_errors,
            "side_effects": {
                "ssh_attempted": False,
                "n8n_started": False,
                "dify_runtime_called": False,
                "notification_sent": False,
                "production_db_modified": False,
                "trading_or_order_execution": False,
            },
        }
    else:
        result = build_plan(data, args.execute)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
