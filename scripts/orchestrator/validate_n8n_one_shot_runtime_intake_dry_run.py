#!/usr/bin/env python3
"""Validate the n8n one-shot runtime intake dry-run package."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DOC_PATH = Path("docs/n8n_one_shot_runtime_intake_dry_run.md")
ONE_SHOT_DOC_PATH = Path("docs/ai_dev_one_shot_multi_agent_automation.md")
RUNBOOK_PATH = Path("docs/ai_task_queue_runbook.md")
PAYLOAD_PATH = Path("templates/n8n_one_shot_intake_payload.example.json")
RESULT_PATH = Path("templates/n8n_one_shot_intake_result.example.json")
WORKFLOW_PATH = Path("templates/n8n_ai_dev_one_shot_orchestration_workflow.sanitized.example.json")
RUNNER_PATH = Path("scripts/orchestrator/run_ai_dev_one_shot_plan.py")

REQUIRED_PAYLOAD_KEYS = [
    "task_id",
    "dry_run",
    "intake_source",
    "entry_points",
    "chatgpt_task_request_metadata",
    "safety_gates",
    "autonomous_permission_profile",
    "conditional_auto_merge_policy",
    "codex_one_shot_runner_command",
    "expected_outputs",
    "stop_conditions",
]

REQUIRED_SAFETY_TRUE = [
    "no_n8n_start",
    "no_dify_runtime_call",
    "no_chatgpt_openai_api_call",
    "no_api_key_token_secret_env_credential_use",
    "no_line_email_notification",
    "no_production_db_change",
    "no_cron_systemd_timer_change",
    "no_python3_main_py",
    "no_trading_or_order_execution",
    "no_ai_dev_050",
]

DOC_REQUIRED_PHRASES = [
    "webhook",
    "manual trigger",
    "task_id",
    "dry_run=true",
    "AI-DEV-050",
    "does not start n8n",
    "does not grant runtime access",
]

SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+\/-]{12,}", re.IGNORECASE),
    re.compile(r"Authorization\s*[:=]\s*(?!placeholder|credential_placeholder_only|\[REDACTED\])[A-Za-z0-9._~+\/-]{8,}", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*(?!placeholder|redacted|false|true)[A-Za-z0-9._~+\/-]{8,}", re.IGNORECASE),
    re.compile(r"token\s*[:=]\s*(?!placeholder|redacted|false|true)[A-Za-z0-9._~+\/-]{8,}", re.IGNORECASE),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

FORBIDDEN_TEXT = [
    "n8n-nodes-base.cron",
    "n8n-nodes-base.emailSend",
    "n8n-nodes-base.line",
    "n8n-nodes-base.postgres",
    "n8n-nodes-base.mysql",
    "n8n-nodes-base.sqlite",
    "send_line_report" + "(",
    "place_" + "order(",
    "api." + "place_order",
]


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def has_secret_value(text: str) -> bool:
    scrubbed = text.replace("DIFY_WORKFLOW_API_CREDENTIAL_STORED_IN_N8N_ONLY", "")
    scrubbed = scrubbed.replace("GITHUB_READONLY_CREDENTIAL_STORED_IN_N8N_ONLY", "")
    return any(pattern.search(scrubbed) for pattern in SECRET_PATTERNS)


def run_runner(repo_root: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "scripts/orchestrator/run_ai_dev_one_shot_plan.py", "--pretty"],
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr or proc.stdout}
    try:
        data = json.loads(proc.stdout)
        return data if isinstance(data, dict) else {"ok": False, "error": "runner output not object"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate n8n one-shot intake dry-run package.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    required_files = [DOC_PATH, ONE_SHOT_DOC_PATH, RUNBOOK_PATH, PAYLOAD_PATH, RESULT_PATH, WORKFLOW_PATH, RUNNER_PATH]
    file_checks = {str(path): (repo_root / path).is_file() for path in required_files}
    for rel_path, exists in file_checks.items():
        if not exists:
            errors.append(f"required file missing: {rel_path}")

    payload: dict[str, Any] = {}
    result_payload: dict[str, Any] = {}
    workflow: dict[str, Any] = {}
    for path in [PAYLOAD_PATH, RESULT_PATH, WORKFLOW_PATH]:
        if not file_checks.get(str(path)):
            continue
        data, err = load_json(repo_root / path)
        if err:
            errors.append(f"JSON parse failed for {path}: {err}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{path} root must be object")
            continue
        if has_secret_value(json.dumps(data, ensure_ascii=False, sort_keys=True)):
            errors.append(f"secret-like value found in {path}")
        if path == PAYLOAD_PATH:
            payload = data
        elif path == RESULT_PATH:
            result_payload = data
        else:
            workflow = data

    for key in REQUIRED_PAYLOAD_KEYS:
        if key not in payload:
            errors.append(f"intake payload missing key: {key}")
    if payload.get("dry_run") is not True:
        errors.append("intake payload dry_run must be true")
    entry = payload.get("entry_points", {})
    if not isinstance(entry, dict) or entry.get("webhook_supported") is not True or entry.get("manual_trigger_supported") is not True:
        errors.append("entry_points must support webhook and manual trigger")
    safety = payload.get("safety_gates", {})
    for flag in REQUIRED_SAFETY_TRUE:
        if not isinstance(safety, dict) or safety.get(flag) is not True:
            errors.append(f"safety_gates.{flag} must be true")
    if payload.get("conditional_auto_merge_policy", {}).get("enabled") is not True:
        errors.append("conditional_auto_merge_policy.enabled must be true")

    side_effects = result_payload.get("runtime_side_effects", {}) if isinstance(result_payload, dict) else {}
    for key in ["n8n_started", "dify_runtime_called", "chatgpt_openai_api_called", "notification_sent", "production_db_modified", "cron_systemd_timer_modified", "runtime_queue_modified", "trading_execution_run"]:
        if side_effects.get(key) is not False:
            errors.append(f"runtime_side_effects.{key} must be false")

    workflow_text = json.dumps(workflow, ensure_ascii=False).lower()
    if workflow.get("sanitized_example") is not True:
        errors.append("workflow sanitized_example must be true")
    if "webhook" not in workflow_text or "manual trigger" not in workflow_text:
        errors.append("workflow must contain webhook/manual trigger concepts")
    if "normalize one-shot intake payload" not in workflow_text:
        errors.append("workflow must contain intake normalization")
    if "safety gate router" not in workflow_text:
        errors.append("workflow must contain safety gate router")
    if workflow.get("workflow_policy", {}).get("unconditional_auto_merge") is not False:
        errors.append("workflow must not allow unconditional auto-merge")

    for rel_path in [DOC_PATH, ONE_SHOT_DOC_PATH, RUNBOOK_PATH, RUNNER_PATH]:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if has_secret_value(text):
            errors.append(f"secret-like value found in {rel_path}")
        if rel_path == DOC_PATH:
            lower = text.lower()
            for phrase in DOC_REQUIRED_PHRASES:
                if phrase.lower() not in lower:
                    errors.append(f"intake doc missing phrase: {phrase}")

    all_text = "\n".join((repo_root / path).read_text(encoding="utf-8") for path in [DOC_PATH, PAYLOAD_PATH, RESULT_PATH, WORKFLOW_PATH, RUNNER_PATH] if (repo_root / path).is_file())
    for forbidden in FORBIDDEN_TEXT:
        if forbidden in all_text:
            errors.append(f"forbidden runtime/send/order term found: {forbidden}")

    runner = run_runner(repo_root)
    if runner.get("ok") is not True:
        errors.append("one-shot runner did not return ok:true")
    intake_summary = runner.get("n8n_intake_contract", {})
    if intake_summary.get("available") is not True:
        errors.append("runner n8n intake contract summary must be available")
    if intake_summary.get("dry_run") is not True:
        errors.append("runner n8n intake dry_run must be true")
    external_calls = runner.get("external_calls", {})
    for key in ["n8n_started", "dify_runtime_called", "chatgpt_openai_api_called", "notification_sent"]:
        if external_calls.get(key) is not False:
            errors.append(f"runner external_calls.{key} must be false")

    output = {
        "ok": not errors,
        "passed": not errors,
        "file_checks": file_checks,
        "payload_task_id": payload.get("task_id"),
        "entry_points": payload.get("entry_points"),
        "runner_intake_summary": intake_summary,
        "errors": errors,
        "warnings": warnings,
        "side_effects": {
            "files_modified": False,
            "n8n_started": False,
            "dify_called": False,
            "chatgpt_openai_api_called": False,
            "notification_sent": False,
            "runtime_queue_modified": False,
            "production_db_modified": False,
            "trading_execution_run": False,
        },
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if output["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
