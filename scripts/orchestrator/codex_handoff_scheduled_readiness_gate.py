#!/usr/bin/env python3
"""Build a dry-run readiness decision for scheduled Codex handoff integration."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HANDOFF_ROOT = ROOT / "docs" / "mobile_issue_handoffs"
TASK_ID = "AI-DEV-068"
MAX_HANDOFFS_PER_RUN = 1

DECISION_READINESS_PASS = "readiness_pass_manual_only"

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
    r"(?i)(^|[\s:;,.()\[\]`'\"])(no|not|never|without|do\s+not|don't|must\s+not|禁止|不得|不要|不可|不|無|未)"
)

RISK_RULES = [
    (
        "secret_material_request",
        re.compile(r"(?i)\b(read|print|show|dump|commit|upload|expose)\b.{0,50}\b(secret|token|credential|\.env)\b"),
    ),
    (
        "line_email_notification_send",
        re.compile(r"(?i)\b(send|push|deliver)\b.{0,40}\b(line|notification|email|webhook)\b|發送.{0,12}(LINE|通知|Email|郵件)|推播"),
    ),
    (
        "trading_or_order_placement",
        re.compile(r"(?i)\b(place|submit|route|execute)\b.{0,40}\b(order|trade|trading)\b|下單|執行.{0,12}交易"),
    ),
    (
        "production_db_mutation",
        re.compile(r"(?i)\b(update|delete|insert|write|migrate|mutate|drop|modify)\b.{0,50}\b(production|prod)\b.{0,20}\b(db|database)\b|修改.{0,12}production DB|不碰production DB"),
    ),
    (
        "cron_systemd_timer_modification",
        re.compile(r"(?i)\b(modify|create|enable|start|stop|restart|install)\b.{0,50}\b(cron|systemd|timer)\b|修改.{0,12}(cron|systemd|timer)"),
    ),
    (
        "n8n_mutation",
        re.compile(r"(?i)\b(start|stop|modify|restart|enable)\b.{0,30}\bn8n\b|修改.{0,12}n8n"),
    ),
    ("dify_runtime", re.compile(r"(?i)\b(call|invoke|run|execute)\b.{0,40}\bdify\b")),
    ("openai_runtime", re.compile(r"(?i)\b(call|invoke|run|execute)\b.{0,40}\b(openai|chatgpt)\b")),
    ("gemini_runtime", re.compile(r"(?i)\b(call|invoke|run|execute)\b.{0,40}\bgemini\b")),
    (
        "shell_command_execution_from_handoff",
        re.compile(r"(?i)\b(execute|run)\b.{0,40}\b(shell|bash|command from issue|command from handoff)\b|執行.{0,16}(shell|指令)"),
    ),
]


def load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("input JSON root must be an object")
    return data


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path.resolve()
    return (ROOT / path).resolve()


def path_under_allowed_dir(path: Path) -> bool:
    try:
        path.resolve().relative_to(HANDOFF_ROOT.resolve())
        return True
    except ValueError:
        return False


def read_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except Exception as exc:  # noqa: BLE001
        return "", f"failed to read handoff: {exc}"


def is_negated(line: str, start: int) -> bool:
    prefix = line[max(0, start - 40):start]
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


def handoff_is_sanitized(text: str) -> bool:
    if not text.strip():
        return False
    rendered = json.dumps({"handoff": text}, ensure_ascii=False)
    if any(pattern.search(rendered) for pattern in SECRET_VALUE_PATTERNS):
        return False
    markers = ["Sanitized Task Summary", "Safety Constraints", "sanitized"]
    return any(marker.lower() in text.lower() for marker in markers)


def idempotency_key(path_text: str, handoff_text: str) -> str:
    digest = hashlib.sha256(handoff_text.encode("utf-8")).hexdigest()[:16]
    return f"codex-handoff-readiness:{path_text}:{digest}"


def side_effects() -> dict[str, bool]:
    return {
        "called_codex_runtime": False,
        "called_external_ai_runtime": False,
        "sent_notification": False,
        "modified_production_db": False,
        "modified_cron_systemd_timer": False,
        "mutated_github_issue": False,
        "modified_n8n": False,
        "placed_trade_order": False,
        "executed_shell_from_handoff": False,
    }


def determine_decision(context: dict[str, Any], blocked_reasons: list[str]) -> tuple[str, bool]:
    if not context["handoff_under_allowed_dir"]:
        return "invalid_handoff_path", False
    if not context["handoff_exists"]:
        return "handoff_missing", False
    if blocked_reasons or not context["handoff_sanitized"]:
        return "unsafe_handoff", False
    if context["selected_handoff_count"] > MAX_HANDOFFS_PER_RUN:
        return "readiness_blocked", False
    if not context["single_active_lock_present"]:
        return "lock_missing", False
    if not context["idempotency_required"] or not context["idempotency_key"]:
        return "idempotency_missing", False
    if context["already_processed"]:
        return "already_processed", False
    if not context["headless_supported"] or not context["manual_one_shot_viable"]:
        return "readiness_blocked", False
    return DECISION_READINESS_PASS, True


def build_result(args: argparse.Namespace, input_data: dict[str, Any]) -> dict[str, Any]:
    handoff_path_text = args.handoff_path or str(input_data.get("handoff_path", ""))
    resolved_handoff = resolve_repo_path(handoff_path_text) if handoff_path_text else ROOT
    under_allowed = bool(handoff_path_text) and path_under_allowed_dir(resolved_handoff)
    exists = under_allowed and resolved_handoff.is_file()
    handoff_text = ""
    read_error = None
    if exists:
        handoff_text, read_error = read_text(resolved_handoff)

    rel_handoff = handoff_path_text
    if exists:
        rel_handoff = repo_relative(resolved_handoff)

    generated_key = idempotency_key(rel_handoff, handoff_text) if handoff_text else ""
    processed_keys = input_data.get("processed_idempotency_keys", [])
    if not isinstance(processed_keys, list):
        processed_keys = []

    context = {
        "handoff_exists": exists,
        "handoff_under_allowed_dir": under_allowed,
        "handoff_sanitized": handoff_is_sanitized(handoff_text) if handoff_text else False,
        "headless_supported": bool(input_data.get("headless_supported", True)),
        "manual_one_shot_viable": bool(input_data.get("manual_one_shot_viable", True)),
        "single_active_lock_required": True,
        "single_active_lock_present": bool(input_data.get("single_active_lock_present", True)),
        "idempotency_required": bool(input_data.get("idempotency_required", True)),
        "idempotency_key": generated_key,
        "already_processed": generated_key in processed_keys if generated_key else False,
        "max_handoffs_per_run": int(input_data.get("max_handoffs_per_run", MAX_HANDOFFS_PER_RUN)),
        "selected_handoff_count": int(input_data.get("selected_handoff_count", 1 if handoff_path_text else 0)),
    }

    blocked_reasons = scan_handoff(handoff_text) if handoff_text else []
    if read_error:
        blocked_reasons.append(read_error)
    if context["max_handoffs_per_run"] != MAX_HANDOFFS_PER_RUN:
        blocked_reasons.append("max_handoffs_per_run must be 1")
    if context["selected_handoff_count"] > MAX_HANDOFFS_PER_RUN:
        blocked_reasons.append("selected_handoff_count must not exceed 1")
    if exists and not context["handoff_sanitized"]:
        blocked_reasons.append("handoff does not satisfy sanitized handoff markers")

    decision, safe_to_call_executor = determine_decision(context, blocked_reasons)
    ok = decision == DECISION_READINESS_PASS

    return {
        "task_id": str(input_data.get("task_id", TASK_ID)),
        "ok": ok,
        "mode": "dry_run",
        "handoff_path": rel_handoff,
        "handoff_exists": context["handoff_exists"],
        "handoff_under_allowed_dir": context["handoff_under_allowed_dir"],
        "handoff_sanitized": context["handoff_sanitized"],
        "headless_supported": context["headless_supported"],
        "manual_one_shot_viable": context["manual_one_shot_viable"],
        "schedule_ready": False,
        "single_active_lock_required": context["single_active_lock_required"],
        "single_active_lock_present": context["single_active_lock_present"],
        "idempotency_required": context["idempotency_required"],
        "idempotency_key": context["idempotency_key"],
        "already_processed": context["already_processed"],
        "max_handoffs_per_run": MAX_HANDOFFS_PER_RUN,
        "selected_handoff_count": context["selected_handoff_count"],
        "safe_to_call_executor": safe_to_call_executor,
        "safe_to_schedule": False,
        "decision": decision,
        "blocked_reasons": sorted(set(blocked_reasons)),
        "side_effects": side_effects(),
        "next_recommendation": (
            "Keep execution manual-only; use AI-DEV-069 for separately approved scheduled activation."
            if ok
            else "Do not call the Codex handoff executor until readiness blockers are resolved."
        ),
    }


def build_activation_proposal(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "activation_ready": bool(result.get("safe_to_call_executor")),
        "schedule_ready": False,
        "requires_user_approval": True,
        "proposed_next_task": "AI-DEV-069",
        "proposed_integration": "scheduled pickup calls codex handoff executor after readiness gate passes",
        "proposed_cadence": "30m",
        "max_handoffs_per_run": MAX_HANDOFFS_PER_RUN,
        "safe_to_enable_now": False,
        "source_readiness_decision": result.get("decision"),
        "side_effects": side_effects(),
    }


def write_json(path: str, data: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Codex handoff scheduled readiness dry-run result.")
    parser.add_argument("--dry-run", action="store_true", help="Required; no runtime execution is supported.")
    parser.add_argument("--handoff-path", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--input", default=None)
    parser.add_argument("--activation-proposal-output", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        json.dump({"ok": False, "decision": "validation_failed", "errors": ["--dry-run is required"]}, sys.stdout)
        sys.stdout.write("\n")
        return 2

    try:
        input_data = load_json(args.input)
        result = build_result(args, input_data)
        write_json(args.output, result)
        if args.activation_proposal_output:
            write_json(args.activation_proposal_output, build_activation_proposal(result))
    except Exception as exc:  # noqa: BLE001
        result = {
            "ok": False,
            "decision": "validation_failed",
            "errors": [str(exc)],
            "side_effects": side_effects(),
        }
        json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True)
        sys.stdout.write("\n")
        return 2

    json.dump(
        {
            "ok": result["ok"],
            "decision": result["decision"],
            "safe_to_call_executor": result["safe_to_call_executor"],
            "safe_to_schedule": result["safe_to_schedule"],
            "output": args.output,
            "activation_proposal_output": args.activation_proposal_output,
        },
        sys.stdout,
        ensure_ascii=False,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
