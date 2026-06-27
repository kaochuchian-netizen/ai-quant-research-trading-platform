#!/usr/bin/env python3
"""Validate the AI-DEV one-shot multi-agent automation package."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DOC_PATH = Path("docs/ai_dev_one_shot_multi_agent_automation.md")
RUNBOOK_PATH = Path("docs/ai_task_queue_runbook.md")
RUNNER_PATH = Path("scripts/orchestrator/run_ai_dev_one_shot_plan.py")
TEMPLATE_PATHS = [
    Path("templates/chatgpt_ai_dev_task_request.example.json"),
    Path("templates/n8n_ai_dev_one_shot_orchestration_workflow.sanitized.example.json"),
    Path("templates/dify_ai_dev_one_shot_review_input.example.json"),
    Path("templates/dify_ai_dev_one_shot_review_output.example.json"),
    Path("templates/codex_ai_dev_one_shot_execution_request.example.json"),
    Path("templates/codex_ai_dev_one_shot_execution_plan.example.json"),
]

REQUIRED_CHATGPT_KEYS = [
    "task_id",
    "user_goal",
    "scope",
    "acceptance_criteria",
    "safety_constraints",
    "stop_gates",
    "autonomous_permission_profile",
    "required_outputs",
    "chatgpt_review_expectations",
    "github_facing_metadata",
    "codex_start_instruction_summary",
]

REQUIRED_DIFY_OUTPUT_KEYS = [
    "task_summary",
    "implementation_summary",
    "validation_summary",
    "pr_gate_summary",
    "safety_summary",
    "blockers",
    "next_action_recommendation",
    "chatgpt_ready_report",
    "safety_flags",
]

REQUIRED_SAFETY_TRUE = [
    "no_n8n_start",
    "no_dify_runtime_call",
    "no_chatgpt_openai_api_call",
    "no_api_key_token_secret_env_credential_use",
    "no_production_db_change",
    "no_cron_systemd_timer_change",
    "no_line_email_notification",
    "no_python3_main_py",
    "no_trading_or_order_execution",
    "no_ai_dev_049",
]

DOC_REQUIRED_PHRASES = [
    "Conditional Auto-Merge Policy",
    "ChatGPT App itself is not automatically operated by n8n",
    "backfill_completed_ai_task_record.py",
    "does not start n8n",
    "call Dify runtime",
    "call ChatGPT or OpenAI APIs",
    "Stop Gates",
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

FORBIDDEN_N8N_TERMS = [
    "n8n-nodes-base.cron",
    "n8n-nodes-base.emailSend",
    "n8n-nodes-base.line",
    "n8n-nodes-base.postgres",
    "n8n-nodes-base.mysql",
    "n8n-nodes-base.sqlite",
    "\"unconditional_auto_merge\": true",
]


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def text_has_secret_value(text: str) -> bool:
    scrubbed = text.replace("DIFY_WORKFLOW_API_CREDENTIAL_STORED_IN_N8N_ONLY", "")
    scrubbed = scrubbed.replace("GITHUB_READONLY_CREDENTIAL_STORED_IN_N8N_ONLY", "")
    return any(pattern.search(scrubbed) for pattern in SECRET_PATTERNS)


def run_runner(repo_root: Path) -> tuple[dict[str, Any], str]:
    proc = subprocess.run(
        [sys.executable, "scripts/orchestrator/run_ai_dev_one_shot_plan.py", "--pretty"],
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr or proc.stdout}, proc.stdout
    try:
        data = json.loads(proc.stdout)
        return data if isinstance(data, dict) else {"ok": False, "error": "runner output is not object"}, proc.stdout
    except Exception as exc:
        return {"ok": False, "error": str(exc)}, proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV one-shot multi-agent automation package.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    required_files = [DOC_PATH, RUNBOOK_PATH, RUNNER_PATH, *TEMPLATE_PATHS]
    file_checks = {str(path): (repo_root / path).is_file() for path in required_files}
    for rel_path, exists in file_checks.items():
        if not exists:
            errors.append(f"required file missing: {rel_path}")

    loaded: dict[str, Any] = {}
    for path in TEMPLATE_PATHS:
        if not file_checks.get(str(path)):
            continue
        data, err = load_json(repo_root / path)
        if err:
            errors.append(f"JSON parse failed for {path}: {err}")
            continue
        loaded[str(path)] = data
        serialized = json.dumps(data, ensure_ascii=False, sort_keys=True)
        if text_has_secret_value(serialized):
            errors.append(f"secret-like value found in {path}")

    chatgpt = loaded.get("templates/chatgpt_ai_dev_task_request.example.json", {})
    if isinstance(chatgpt, dict):
        for key in REQUIRED_CHATGPT_KEYS:
            if key not in chatgpt:
                errors.append(f"ChatGPT task request missing key: {key}")
        safety = chatgpt.get("safety_constraints", {})
        for flag in REQUIRED_SAFETY_TRUE:
            if not isinstance(safety, dict) or safety.get(flag) is not True:
                errors.append(f"safety_constraints.{flag} must be true")
        if chatgpt.get("autonomous_permission_profile", {}).get("conditional_auto_merge_allowed") is not True:
            errors.append("conditional auto-merge permission must be explicit")
    else:
        errors.append("ChatGPT task request root must be object")

    n8n = loaded.get("templates/n8n_ai_dev_one_shot_orchestration_workflow.sanitized.example.json", {})
    if isinstance(n8n, dict):
        text = json.dumps(n8n, ensure_ascii=False).lower()
        if n8n.get("sanitized_example") is not True:
            errors.append("n8n workflow must be marked sanitized_example=true")
        if "manual trigger" not in text or "webhook" not in text:
            errors.append("n8n workflow must include webhook/manual trigger intake")
        if "safety gate router" not in text:
            errors.append("n8n workflow must include safety gate router")
        if "conditional auto-merge gate" not in text:
            errors.append("n8n workflow must include conditional auto-merge gate")
        if n8n.get("workflow_policy", {}).get("unconditional_auto_merge") is not False:
            errors.append("n8n workflow must not allow unconditional auto-merge")
        for term in FORBIDDEN_N8N_TERMS:
            if term in text:
                errors.append(f"forbidden n8n term found: {term}")
    else:
        errors.append("n8n workflow root must be object")

    dify_output = loaded.get("templates/dify_ai_dev_one_shot_review_output.example.json", {})
    if isinstance(dify_output, dict):
        for key in REQUIRED_DIFY_OUTPUT_KEYS:
            if key not in dify_output:
                errors.append(f"Dify output missing key: {key}")
    else:
        errors.append("Dify output root must be object")

    for rel_path in [DOC_PATH, RUNBOOK_PATH, RUNNER_PATH]:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if text_has_secret_value(text):
            errors.append(f"secret-like value found in {rel_path}")
        if rel_path == DOC_PATH:
            for phrase in DOC_REQUIRED_PHRASES:
                if phrase not in text:
                    errors.append(f"one-shot doc missing phrase: {phrase}")

    runner_result, runner_stdout = run_runner(repo_root)
    if runner_result.get("ok") is not True:
        errors.append("runner dry-run output is not ok:true")
    if runner_result.get("dry_run") is not True:
        errors.append("runner dry-run output must have dry_run=true")
    external_calls = runner_result.get("external_calls", {})
    for key in ["n8n_started", "dify_runtime_called", "chatgpt_openai_api_called", "notification_sent"]:
        if external_calls.get(key) is not False:
            errors.append(f"runner external_calls.{key} must be false")

    result = {
        "ok": not errors,
        "passed": not errors,
        "file_checks": file_checks,
        "templates_checked": [str(path) for path in TEMPLATE_PATHS],
        "runner_dry_run_summary": {
            "ok": runner_result.get("ok"),
            "dry_run": runner_result.get("dry_run"),
            "task_id": runner_result.get("task_id"),
            "branch": runner_result.get("branch"),
            "external_calls": runner_result.get("external_calls"),
            "role_keys": sorted((runner_result.get("role_steps") or {}).keys()),
        },
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
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
