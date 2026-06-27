#!/usr/bin/env python3
"""Read-only health inspector for scheduled GitHub Issue pickup dry-runs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STATE_DIR = Path("/home/kaochuchian/.local/state/stock-ai-orchestrator")
DEFAULT_TIMER_NAME = "stock-ai-github-issue-scheduled-pickup-dry-run.timer"
DEFAULT_SERVICE_NAME = "stock-ai-github-issue-scheduled-pickup-dry-run.service"
ROLLBACK_COMMANDS = [
    "systemctl --user disable --now stock-ai-github-issue-scheduled-pickup-dry-run.timer",
    "systemctl --user reset-failed stock-ai-github-issue-scheduled-pickup-dry-run.service",
    "systemctl --user daemon-reload",
]
SAFETY_CONFIRMATION = (
    "Read-only health inspection only. No runtime action, GitHub Issue mutation, "
    "schedule mutation, daemon creation, comment-back, notification, Dify, OpenAI, "
    "n8n, trading, production pipeline, or production database action was performed."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_systemctl(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(["systemctl", "--user", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return proc.returncode, proc.stdout.strip()


def summarize_status(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    active_line = next((line for line in lines if line.startswith("Active:")), "")
    loaded_line = next((line for line in lines if line.startswith("Loaded:")), "")
    trigger_line = next((line for line in lines if line.startswith("Trigger:")), "")
    process_line = next((line for line in lines if "ExecStart=" in line), "")
    return {
        "loaded_line": loaded_line,
        "active_line": active_line,
        "trigger_line": trigger_line,
        "process_line": process_line,
    }


def parse_timer_status(name: str) -> tuple[bool, bool, bool, str, dict[str, Any]]:
    code, output = run_systemctl(["status", name])
    present = code in {0, 3} and "could not be found" not in output
    summary = summarize_status(output)
    loaded_line = summary.get("loaded_line", "")
    active_line = summary.get("active_line", "")
    enabled = " enabled" in loaded_line or "; enabled;" in loaded_line
    active = "active (waiting)" in active_line or "active (elapsed)" in active_line
    next_trigger = summary.get("trigger_line") or "not scheduled"
    return present, enabled, active, next_trigger, summary


def parse_service_status(name: str) -> tuple[bool, dict[str, Any]]:
    code, output = run_systemctl(["status", name])
    present = code in {0, 3} and "could not be found" not in output
    return present, summarize_status(output)


def load_latest_artifact(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, ["latest artifact is missing"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"latest artifact JSON parse failed: {exc}"]
    if not isinstance(data, dict):
        return None, ["latest artifact root must be an object"]
    return data, []


def latest_summary(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    return {
        "run_id": data.get("run_id"),
        "source": data.get("source"),
        "total_issues_seen": data.get("total_issues_seen"),
        "eligible_count": data.get("eligible_count"),
        "rejected_count": data.get("rejected_count"),
        "needs_manual_review_count": data.get("needs_manual_review_count"),
        "candidate_issue_numbers": data.get("candidate_issue_numbers", []),
        "errors": data.get("errors", []),
        "warnings": data.get("warnings", []),
    }


def artifact_side_effect_flags(data: dict[str, Any] | None) -> dict[str, bool]:
    if not data:
        return {
            "github_issue_mutated": False,
            "runtime_action_performed": False,
            "daemon_or_background_service_created": False,
        }
    return {
        "github_issue_mutated": bool(data.get("github_issue_mutated")),
        "runtime_action_performed": bool(data.get("runtime_action_performed")),
        "daemon_or_background_service_created": bool(data.get("daemon_or_background_service_created")),
    }


def artifact_valid(data: dict[str, Any] | None, load_errors: list[str]) -> bool:
    if load_errors or not data:
        return False
    expected_false_fields = [
        "runtime_action_performed",
        "github_issue_mutated",
        "daemon_or_background_service_created",
    ]
    return (
        data.get("dry_run") is True
        and data.get("scheduler_enabled") is False
        and isinstance(data.get("total_issues_seen"), int)
        and isinstance(data.get("eligible_count"), int)
        and isinstance(data.get("rejected_count"), int)
        and isinstance(data.get("needs_manual_review_count"), int)
        and all(data.get(field) is False for field in expected_false_fields)
    )


def file_state(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "present": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
    }


def build_report(state_dir: Path, timer_name: str, service_name: str) -> dict[str, Any]:
    timer_present, timer_enabled, timer_active, next_trigger, timer_status = parse_timer_status(timer_name)
    service_present, service_status = parse_service_status(service_name)
    latest_path = state_dir / "github_issue_scheduled_pickup_latest.json"
    lock_path = state_dir / "github_issue_scheduled_pickup.lock"
    idempotency_path = state_dir / "github_issue_scheduled_pickup_idempotency.json"
    log_path = state_dir / "github_issue_scheduled_pickup.log"
    latest, latest_errors = load_latest_artifact(latest_path)
    valid = artifact_valid(latest, latest_errors)
    side_effects = artifact_side_effect_flags(latest)
    side_effect_flags_ok = valid and not any(side_effects.values())

    recommended_action = None
    if not timer_present:
        recommended_action = "timer_missing_review_ai_dev_061_enablement"
    elif not timer_enabled or not timer_active:
        recommended_action = "timer_not_active_or_enabled_review_systemd_status"
    elif not valid:
        recommended_action = "latest_artifact_invalid_rerun_dry_run_and_validator"
    elif not side_effect_flags_ok:
        recommended_action = "side_effect_flag_violation_disable_timer_and_review"

    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "state_dir": str(state_dir),
        "timer_name": timer_name,
        "service_name": service_name,
        "timer_present": timer_present,
        "timer_enabled": timer_enabled,
        "timer_active": timer_active,
        "next_trigger_summary": next_trigger,
        "service_present": service_present,
        "last_service_status_summary": service_status,
        "latest_artifact_path": str(latest_path),
        "latest_artifact_present": latest_path.exists(),
        "latest_artifact_valid": valid,
        "latest_artifact_summary": latest_summary(latest),
        "latest_artifact_errors": latest_errors,
        "lock_file_path": str(lock_path),
        "lock_file_present": lock_path.exists(),
        "idempotency_file_path": str(idempotency_path),
        "idempotency_file_present": idempotency_path.exists(),
        "log_file_path": str(log_path),
        "log_file_present": log_path.exists(),
        "file_states": {
            "lock": file_state(lock_path),
            "idempotency": file_state(idempotency_path),
            "log": file_state(log_path),
        },
        "side_effect_flags_ok": side_effect_flags_ok,
        "github_issue_mutated": side_effects["github_issue_mutated"],
        "runtime_action_performed": side_effects["runtime_action_performed"],
        "daemon_or_background_service_created": side_effects["daemon_or_background_service_created"],
        "recommended_operator_action": recommended_action,
        "rollback_disable_commands": ROLLBACK_COMMANDS,
        "safety_confirmation": SAFETY_CONFIRMATION,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect scheduled GitHub Issue pickup dry-run health.")
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--timer-name", default=DEFAULT_TIMER_NAME)
    parser.add_argument("--service-name", default=DEFAULT_SERVICE_NAME)
    parser.add_argument("--output")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(Path(args.state_dir), args.timer_name, args.service_name)
    text = json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
