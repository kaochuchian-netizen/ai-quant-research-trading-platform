#!/usr/bin/env python3
"""Build a safe dry-run plan for Codex handoff auto execution.

The helper reads sanitized repo handoff markdown and writes a sanitized result
artifact. It does not call Codex by default and does not execute commands from
handoff text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HANDOFF_ROOT = ROOT / "docs" / "mobile_issue_handoffs"
TASK_ID = "AI-DEV-067"
SUPPORTED_COMMAND = "codex exec"

SECRET_VALUE_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,}\"']+"),
]

NEGATION_RE = re.compile(
    r"(?i)(^|[\s:;,.()\[\]`'\"])(no|not|never|without|do\s+not|don't|must\s+not|禁止|不得|不要|不可|不|無|未|no\s+runtime|no\s+production)"
)

RISK_RULES = [
    ("secret_material_request", re.compile(r"(?i)\b(read|print|show|dump|commit|upload|expose)\b.{0,40}\b(secret|token|credential|\.env)\b")),
    ("line_send", re.compile(r"(?i)\b(send|push|deliver)\b.{0,30}\b(line|notification|email|webhook)\b|發送.{0,8}(LINE|通知|Email|郵件)")),
    ("trading_or_order", re.compile(r"(?i)\b(place|submit|route|execute)\b.{0,30}\b(order|trade)\b|下單|執行.{0,8}交易")),
    ("production_db_mutation", re.compile(r"(?i)\b(update|delete|insert|write|migrate|mutate|drop)\b.{0,40}\b(production|prod)\b.{0,20}\b(db|database)\b|修改.{0,8}production DB")),
    ("scheduler_mutation", re.compile(r"(?i)\b(modify|create|enable|start|stop|restart|install)\b.{0,40}\b(cron|systemd|timer)\b|修改.{0,8}(cron|systemd|timer)")),
    ("n8n_mutation", re.compile(r"(?i)\b(start|stop|modify|restart|enable)\b.{0,20}\bn8n\b|修改.{0,8}n8n")),
    ("dify_runtime", re.compile(r"(?i)\b(call|invoke|run|execute)\b.{0,30}\bdify\b")),
    ("openai_runtime", re.compile(r"(?i)\b(call|invoke|run|execute)\b.{0,30}\b(openai|chatgpt)\b")),
    ("gemini_runtime", re.compile(r"(?i)\b(call|invoke|run|execute)\b.{0,30}\bgemini\b")),
    ("shell_from_handoff", re.compile(r"(?i)\b(execute|run)\b.{0,30}\b(shell|bash|command from issue|command from handoff)\b|執行.{0,12}(shell|指令)")),
]


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def validate_handoff_path(path_text: str) -> tuple[Path | None, list[str]]:
    errors: list[str] = []
    path = (ROOT / path_text).resolve()
    try:
        path.relative_to(HANDOFF_ROOT.resolve())
    except ValueError:
        errors.append("handoff path must be under docs/mobile_issue_handoffs/")
        return None, errors
    if not path.exists():
        errors.append(f"handoff path does not exist: {path_text}")
        return None, errors
    if not path.is_file():
        errors.append(f"handoff path is not a file: {path_text}")
        return None, errors
    return path, errors


def load_handoff(path: Path) -> tuple[str, list[str]]:
    try:
        return path.read_text(encoding="utf-8"), []
    except Exception as exc:
        return "", [f"failed to read handoff: {exc}"]


def is_negated(line: str, start: int) -> bool:
    prefix = line[max(0, start - 32):start]
    return bool(NEGATION_RE.search(prefix))


def scan_handoff(text: str) -> list[str]:
    reasons: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for label, pattern in RISK_RULES:
            match = pattern.search(line)
            if match and not is_negated(line, match.start()):
                reasons.append(f"handoff contains positive high-risk intent: {label}")
    rendered = json.dumps({"handoff": text}, ensure_ascii=False)
    if any(pattern.search(rendered) for pattern in SECRET_VALUE_PATTERNS):
        reasons.append("handoff appears to contain secret-like values")
    return sorted(set(reasons))


def extract_summary(text: str) -> str:
    title = None
    summary = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- Title:"):
            title = stripped.replace("- Title:", "", 1).strip()
        elif stripped.startswith("AI-DEV-") and summary is None:
            summary = stripped[:240]
    return summary or title or "Sanitized mobile handoff for repo-side Codex execution."


def side_effects() -> dict[str, bool]:
    return {
        "called_codex_runtime": False,
        "called_external_ai_runtime": False,
        "sent_notification": False,
        "modified_production_db": False,
        "modified_cron_systemd_timer": False,
        "mutated_github_issue": False,
    }


def feasibility() -> dict[str, Any]:
    return {
        "which_codex": "/home/kaochuchian/.local/bin/codex",
        "codex_version": "codex-cli 0.142.3",
        "codex_help_available": True,
        "codex_exec_help_available": True,
        "codex_run_help_available": False,
        "sanitized_help_notes": [
            "top-level help lists exec as non-interactive",
            "exec help says Run Codex non-interactively",
            "run help returned top-level help; no dedicated run command was identified",
        ],
    }


def execution_plan() -> dict[str, Any]:
    return {
        "default_calls_codex": False,
        "requires_execute_headless_flag": True,
        "prompt_artifact_only": True,
        "execute_shell_from_handoff": False,
    }


def build_result(
    *,
    args: argparse.Namespace,
    handoff_path: Path | None,
    handoff_text: str,
    path_errors: list[str],
    read_errors: list[str],
) -> dict[str, Any]:
    blocked_reasons = scan_handoff(handoff_text) if handoff_text else []
    validation_errors = path_errors + read_errors
    if validation_errors:
        decision = "invalid_handoff_path"
        ok = False
    elif blocked_reasons:
        decision = "blocked"
        ok = False
    elif args.execute_headless:
        decision = "plan_created"
        ok = False
        validation_errors.append("execute-headless is intentionally not implemented in Safe Executor V1")
    else:
        decision = "headless_supported_manual_only"
        ok = True

    rel_handoff = args.handoff_path
    if handoff_path is not None:
        rel_handoff = repo_relative(handoff_path)
    return {
        "task_id": TASK_ID,
        "ok": ok,
        "mode": "dry_run" if args.dry_run else "plan_only",
        "handoff_path": rel_handoff,
        "headless_supported": True,
        "supported_command": SUPPORTED_COMMAND,
        "manual_one_shot_viable": True,
        "schedule_ready": False,
        "tmux_paste_required": False,
        "decision": decision,
        "safe_to_schedule": False,
        "safe_to_execute": False,
        "blocked_reasons": blocked_reasons,
        "validation_errors": validation_errors,
        "feasibility": feasibility(),
        "execution_plan": execution_plan(),
        "sanitized_prompt": {
            "source": "sanitized_handoff_markdown",
            "summary": extract_summary(handoff_text) if handoff_text else "No valid handoff was loaded.",
            "raw_handoff_included": False,
        },
        "side_effects": side_effects(),
        "next_recommendation": (
            "Use manual GCP resident Codex handoff execution until a separately reviewed manual-only codex exec proof is completed."
            if ok
            else "Do not execute this handoff automatically; resolve validation or safety blockers first."
        ),
    }


def write_result(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a safe Codex handoff auto executor dry-run result.")
    parser.add_argument("--dry-run", action="store_true", help="Generate a plan/result artifact without calling Codex.")
    parser.add_argument("--handoff-path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute-headless", action="store_true", help="Reserved explicit flag; V1 still fails closed.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    handoff_path, path_errors = validate_handoff_path(args.handoff_path)
    handoff_text = ""
    read_errors: list[str] = []
    if handoff_path is not None:
        handoff_text, read_errors = load_handoff(handoff_path)
    result = build_result(
        args=args,
        handoff_path=handoff_path,
        handoff_text=handoff_text,
        path_errors=path_errors,
        read_errors=read_errors,
    )
    write_result(result, Path(args.output))
    json.dump({
        "ok": result["ok"],
        "decision": result["decision"],
        "output": args.output,
        "blocked_reasons": result["blocked_reasons"],
        "validation_errors": result["validation_errors"],
        "side_effects": result["side_effects"],
    }, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
