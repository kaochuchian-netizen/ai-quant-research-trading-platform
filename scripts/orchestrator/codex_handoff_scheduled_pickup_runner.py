#!/usr/bin/env python3
"""Integrate scheduled GitHub Issue pickup with the Codex handoff executor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TASK_ID = "AI-DEV-069"
DEFAULT_ORCHESTRATOR_STATE = Path("/home/kaochuchian/.local/state/stock-ai-orchestrator")
DEFAULT_STATE_DIR = DEFAULT_ORCHESTRATOR_STATE / "codex_handoff_scheduled_pickup"
DEFAULT_PICKUP_ARTIFACT = DEFAULT_ORCHESTRATOR_STATE / "github_issue_scheduled_pickup_latest.json"
DEFAULT_OUTPUT = DEFAULT_STATE_DIR / "latest.json"
DEFAULT_LOCK_FILE = DEFAULT_STATE_DIR / "lock"
DEFAULT_CODEX_EXECUTOR = ROOT / "scripts" / "orchestrator" / "codex_handoff_auto_executor.py"
DEFAULT_READINESS_GATE = ROOT / "scripts" / "orchestrator" / "codex_handoff_scheduled_readiness_gate.py"
PROCESSED_FILE = "processed_handoffs.json"
MAX_HANDOFFS_PER_RUN = 1

DECISIONS = {
    "executed_codex_handoff",
    "implementation_completed",
    "handoff_only_not_implemented",
    "executor_no_implementation",
    "dry_run_plan_created",
    "no_pending_handoff",
    "readiness_failed",
    "locked",
    "already_processed",
    "invalid_handoff_path",
    "unsafe_handoff",
    "codex_executor_failed",
    "validation_failed",
    "activation_completed",
}

SUCCESSFUL_EXECUTOR_DECISIONS = {"implementation_completed", "executed_codex_handoff"}

SIDE_EFFECTS_FALSE = {
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def repo_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else ROOT / path


def rel_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, [f"failed to parse JSON: {exc}"]
    if not isinstance(data, dict):
        return None, ["JSON root must be an object"]
    return data, []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_command(args: list[str], *, timeout: int = 180) -> tuple[int, str, str]:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def load_processed(path: Path) -> dict[str, Any]:
    data, errors = load_json(path)
    if data is None or errors:
        return {"schema_version": "1.0.0", "processed_keys": [], "records": []}
    if not isinstance(data.get("processed_keys"), list):
        data["processed_keys"] = []
    if not isinstance(data.get("records"), list):
        data["records"] = []
    return data


def save_processed(path: Path, data: dict[str, Any]) -> None:
    data["updated_at"] = utc_now()
    write_json(path, data)


def find_processed_record(processed: dict[str, Any], key: str) -> dict[str, Any] | None:
    for item in processed.get("records", []):
        if isinstance(item, dict) and item.get("key") == key:
            return item
    return None


def unmark_non_implementation_processed(
    *,
    processed_path: Path,
    processed: dict[str, Any],
    processed_keys: set[str],
    key: str,
    handoff_path: str,
    state_dir: Path,
) -> tuple[dict[str, Any], set[str], dict[str, Any] | None]:
    if key not in processed_keys:
        return processed, processed_keys, None
    record = find_processed_record(processed, key)
    executor_decision = str(record.get("executor_decision", "")) if record else ""
    implementation_completed = bool(record.get("implementation_completed")) if record else False
    if executor_decision in SUCCESSFUL_EXECUTOR_DECISIONS and implementation_completed:
        return processed, processed_keys, None

    repaired_keys = sorted(item for item in processed_keys if item != key)
    repaired_records = [
        item
        for item in processed.get("records", [])
        if not (isinstance(item, dict) and item.get("key") == key)
    ]
    processed["processed_keys"] = repaired_keys
    processed["records"] = repaired_records
    save_processed(processed_path, processed)
    repair = {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "handoff_path": handoff_path,
        "key": key,
        "unmarked": True,
        "unmarked_reason": "handoff_only_not_implemented",
        "previous_executor_decision": executor_decision or None,
        "source_pr": 75 if "issue_74_" in handoff_path else None,
        "safe_to_retry": True,
    }
    repair_path = state_dir / "repairs" / f"{timestamp()}_handoff_only_not_implemented.json"
    write_json(repair_path, repair)
    repair["artifact"] = str(repair_path)
    return processed, set(repaired_keys), repair


def idempotency_key(handoff_path: str, handoff_text: str) -> str:
    digest = hashlib.sha256(handoff_text.encode("utf-8")).hexdigest()[:16]
    return f"codex-handoff-scheduled-pickup:{handoff_path}:{digest}"


def read_handoff(path_text: str | None) -> tuple[str | None, str, list[str]]:
    if not path_text:
        return None, "", []
    path = repo_path(path_text).resolve()
    try:
        path.relative_to((ROOT / "docs" / "mobile_issue_handoffs").resolve())
    except ValueError:
        return path_text, "", ["handoff path must be under docs/mobile_issue_handoffs/"]
    if not path.is_file():
        return path_text, "", [f"handoff path does not exist: {path_text}"]
    return rel_path(path), path.read_text(encoding="utf-8"), []


def selected_handoff_from_pickup(pickup: dict[str, Any]) -> str | None:
    path = pickup.get("handoff_path")
    if isinstance(path, str) and path:
        return path
    candidates = pickup.get("candidates")
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict) and item.get("needs_codex_execution") is True:
                candidate_path = item.get("handoff_path")
                if isinstance(candidate_path, str) and candidate_path:
                    return candidate_path
    return None


def run_pickup(pickup_artifact: Path, state_dir: Path) -> dict[str, Any]:
    args = [
        sys.executable,
        "scripts/orchestrator/github_issue_mobile_auto_pickup.py",
        "--once",
        "--live-read-open-issues",
        "--max-issues",
        "1",
        "--execute-repo-only",
        "--output",
        str(pickup_artifact),
        "--state-dir",
        str(DEFAULT_ORCHESTRATOR_STATE),
        "--repo",
        "kaochuchian-netizen/ai-quant-research-trading-platform",
        "--pretty",
    ]
    code, stdout, stderr = run_command(args, timeout=300)
    return {
        "called": True,
        "command": " ".join(args),
        "returncode": code,
        "stdout_summary": stdout[:500],
        "stderr_summary": stderr[:500],
        "artifact": str(pickup_artifact),
        "state_dir": str(state_dir),
    }


def acquire_lock(lock_file: Path, handoff_path: str | None) -> tuple[bool, dict[str, Any]]:
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "owner": "codex_handoff_scheduled_pickup_runner",
        "pid": os.getpid(),
        "created_at": utc_now(),
        "handoff_path": handoff_path,
    }
    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        existing, errors = load_json(lock_file)
        return False, {
            "required": True,
            "acquired": False,
            "path": str(lock_file),
            "existing": existing if existing else {},
            "errors": errors,
        }
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return True, {"required": True, "acquired": True, "path": str(lock_file), "owner": payload}


def release_lock(lock_file: Path, acquired: bool) -> None:
    if acquired and lock_file.exists():
        lock_file.unlink()


def base_result(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "ok": False,
        "mode": "execute" if args.execute else "dry_run",
        "decision": "validation_failed",
        "generated_at": utc_now(),
        "pickup_artifact": str(Path(args.pickup_artifact).expanduser()),
        "handoff_path": args.handoff_path,
        "readiness": {
            "called": False,
            "decision": None,
            "safe_to_call_executor": False,
            "safe_to_schedule": False,
            "artifact": None,
        },
        "executor": {
            "called": False,
            "decision": None,
            "artifact": None,
            "returncode": None,
            "implementation_completed": False,
            "implementation_changed_files": [],
        },
        "lock": {
            "required": True,
            "acquired": False,
            "path": str(Path(args.lock_file).expanduser()),
        },
        "idempotency": {
            "required": True,
            "key": None,
            "already_processed": False,
            "marked_processed": False,
            "path": str(Path(args.state_dir).expanduser() / PROCESSED_FILE),
            "repair": {
                "unmarked": False,
                "artifact": None,
            },
        },
        "limits": {
            "max_handoffs_per_run": args.max_handoffs_per_run,
            "selected_handoff_count": 0,
        },
        "pickup": {
            "called": False,
            "decision": None,
            "needs_codex_execution": False,
            "returncode": None,
        },
        "side_effects": dict(SIDE_EFFECTS_FALSE),
        "safe_to_continue": False,
        "blocked_reasons": [],
        "activation": {
            "systemd_user_service_updated": False,
            "timer_enabled": False,
            "timer_active": False,
        },
        "next_recommendation": "Resolve validation blockers before enabling scheduled Codex handoff integration.",
    }


def call_readiness(readiness_gate: Path, handoff_path: str, output: Path) -> tuple[int, dict[str, Any] | None, str]:
    args = [
        sys.executable,
        str(readiness_gate),
        "--dry-run",
        "--handoff-path",
        handoff_path,
        "--output",
        str(output),
    ]
    code, stdout, stderr = run_command(args, timeout=120)
    data, _ = load_json(output) if output.exists() else (None, [])
    return code, data, stderr or stdout


def call_executor(codex_executor: Path, handoff_path: str, output: Path) -> tuple[int, dict[str, Any] | None, str]:
    args = [
        sys.executable,
        str(codex_executor),
        "--execute-headless",
        "--handoff-path",
        handoff_path,
        "--output",
        str(output),
    ]
    code, stdout, stderr = run_command(args, timeout=180)
    data, _ = load_json(output) if output.exists() else (None, [])
    return code, data, stderr or stdout


def non_handoff_files(paths: list[Any]) -> list[str]:
    result: list[str] = []
    for item in paths:
        if isinstance(item, str) and item and not item.startswith("docs/mobile_issue_handoffs/"):
            result.append(item)
    return sorted(set(result))


def executor_implementation_files(executor: dict[str, Any]) -> list[str]:
    direct = executor.get("implementation_changed_files")
    if isinstance(direct, list):
        files = non_handoff_files(direct)
        if files:
            return files
    headless = executor.get("headless_run")
    if isinstance(headless, dict) and isinstance(headless.get("implementation_changed_files"), list):
        return non_handoff_files(headless["implementation_changed_files"])
    return []


def persist_run_artifacts(state_dir: Path, output: Path, result: dict[str, Any]) -> Path:
    run_path = state_dir / "runs" / f"{timestamp()}.json"
    write_json(run_path, result)
    if output != run_path:
        write_json(output, result)
    return run_path


def build_result(args: argparse.Namespace) -> dict[str, Any]:
    if args.dry_run == args.execute:
        result = base_result(args)
        result["blocked_reasons"] = ["exactly one of --dry-run or --execute is required"]
        return result
    if args.max_handoffs_per_run != MAX_HANDOFFS_PER_RUN:
        result = base_result(args)
        result["blocked_reasons"] = ["max_handoffs_per_run must be 1"]
        return result

    state_dir = Path(args.state_dir).expanduser()
    pickup_artifact = Path(args.pickup_artifact).expanduser()
    lock_file = Path(args.lock_file).expanduser()
    result = base_result(args)
    state_dir.mkdir(parents=True, exist_ok=True)

    pickup_data: dict[str, Any] | None = None
    handoff_path = args.handoff_path
    if args.execute and not handoff_path:
        pickup_summary = run_pickup(pickup_artifact, state_dir)
        result["pickup"].update(pickup_summary)
        if pickup_summary["returncode"] != 0:
            result["decision"] = "validation_failed"
            result["blocked_reasons"] = ["scheduled pickup command failed"]
            return result
    if pickup_artifact.exists():
        pickup_data, pickup_errors = load_json(pickup_artifact)
        if pickup_errors:
            result["blocked_reasons"].extend(pickup_errors)
        if pickup_data:
            result["pickup"]["decision"] = pickup_data.get("decision")
            result["pickup"]["needs_codex_execution"] = bool(pickup_data.get("needs_codex_execution"))
    if not handoff_path and pickup_data:
        handoff_path = selected_handoff_from_pickup(pickup_data)

    if not handoff_path:
        result["ok"] = True
        result["decision"] = "no_pending_handoff"
        result["safe_to_continue"] = True
        result["next_recommendation"] = "No pending Codex handoff was found; keep scheduled runner enabled for future handoffs."
        return result

    normalized_handoff, handoff_text, handoff_errors = read_handoff(handoff_path)
    result["handoff_path"] = normalized_handoff or handoff_path
    result["limits"]["selected_handoff_count"] = 1 if normalized_handoff else 0
    if handoff_errors:
        result["decision"] = "invalid_handoff_path"
        result["blocked_reasons"] = handoff_errors
        return result

    key = idempotency_key(str(normalized_handoff), handoff_text)
    processed_path = state_dir / PROCESSED_FILE
    processed = load_processed(processed_path)
    processed_keys = set(str(item) for item in processed.get("processed_keys", []) if isinstance(item, str))
    processed, processed_keys, repair = unmark_non_implementation_processed(
        processed_path=processed_path,
        processed=processed,
        processed_keys=processed_keys,
        key=key,
        handoff_path=str(normalized_handoff),
        state_dir=state_dir,
    )
    result["idempotency"]["key"] = key
    if repair:
        result["idempotency"]["repair"] = {
            "unmarked": True,
            "artifact": repair.get("artifact"),
            "unmarked_reason": repair.get("unmarked_reason"),
            "source_pr": repair.get("source_pr"),
            "safe_to_retry": repair.get("safe_to_retry"),
        }
    result["idempotency"]["already_processed"] = key in processed_keys
    if key in processed_keys:
        result["ok"] = True
        result["decision"] = "already_processed"
        result["safe_to_continue"] = True
        result["executor"]["called"] = False
        result["next_recommendation"] = "Skip duplicate handoff; idempotency state already records successful executor handling."
        return result

    acquired = False
    if args.execute:
        acquired, lock_state = acquire_lock(lock_file, str(normalized_handoff))
        result["lock"] = lock_state
        if not acquired:
            result["ok"] = True
            result["decision"] = "locked"
            result["safe_to_continue"] = False
            result["next_recommendation"] = "Another scheduled Codex handoff runner is active; safe stop without executor call."
            return result

    try:
        readiness_output = state_dir / "readiness_latest.json"
        readiness_code, readiness, readiness_error = call_readiness(repo_path(args.readiness_gate), str(normalized_handoff), readiness_output)
        result["readiness"] = {
            "called": True,
            "decision": readiness.get("decision") if readiness else None,
            "safe_to_call_executor": bool(readiness.get("safe_to_call_executor")) if readiness else False,
            "safe_to_schedule": bool(readiness.get("safe_to_schedule")) if readiness else False,
            "artifact": str(readiness_output),
            "returncode": readiness_code,
        }
        if readiness_code != 0 or not readiness or readiness.get("safe_to_call_executor") is not True:
            result["decision"] = "unsafe_handoff" if readiness and readiness.get("decision") == "unsafe_handoff" else "readiness_failed"
            result["blocked_reasons"] = list(readiness.get("blocked_reasons", [])) if readiness else [readiness_error]
            return result

        if args.dry_run:
            result["ok"] = True
            result["decision"] = "dry_run_plan_created"
            result["safe_to_continue"] = True
            result["next_recommendation"] = "Run manual activation validation, then update the user-level scheduled pickup service command."
            return result

        executor_output = state_dir / "executor_latest.json"
        executor_code, executor, executor_error = call_executor(repo_path(args.codex_executor), str(normalized_handoff), executor_output)
        result["executor"] = {
            "called": True,
            "decision": executor.get("decision") if executor else None,
            "artifact": str(executor_output),
            "returncode": executor_code,
            "implementation_completed": bool(executor.get("implementation_completed")) if executor else False,
            "implementation_changed_files": executor_implementation_files(executor) if executor else [],
        }
        implementation_files = executor_implementation_files(executor) if executor else []
        if executor_code != 0 or not executor or executor.get("ok") is not True:
            result["decision"] = "codex_executor_failed"
            result["blocked_reasons"] = list(executor.get("blocked_reasons", [])) if executor else [executor_error]
            if executor and executor.get("decision") == "executor_no_implementation":
                result["decision"] = "executor_no_implementation"
                result["blocked_reasons"] = list(executor.get("validation_errors", [])) or [
                    "executor did not produce verified implementation changes"
                ]
            if executor and not implementation_files:
                result["decision"] = "handoff_only_not_implemented"
                result["blocked_reasons"] = list(executor.get("validation_errors", [])) or [
                    "executor did not produce non-handoff implementation files"
                ]
            return result
        if executor.get("implementation_completed") is not True or not implementation_files:
            result["decision"] = "handoff_only_not_implemented"
            result["blocked_reasons"] = ["executor completed without verified non-handoff implementation changes"]
            return result

        processed["processed_keys"] = sorted(processed_keys | {key})
        records = [item for item in processed.get("records", []) if not (isinstance(item, dict) and item.get("key") == key)]
        records.append(
            {
                "key": key,
                "handoff_path": normalized_handoff,
                "executor_decision": executor.get("decision"),
                "implementation_completed": True,
                "implementation_changed_files": implementation_files,
                "recorded_at": utc_now(),
            }
        )
        processed["records"] = records
        save_processed(processed_path, processed)
        result["idempotency"]["marked_processed"] = True
        result["ok"] = True
        result["decision"] = "executed_codex_handoff"
        result["implementation_completed"] = True
        result["safe_to_continue"] = True
        result["next_recommendation"] = "Keep timer enabled and monitor sanitized scheduled pickup result artifacts."
        return result
    finally:
        release_lock(lock_file, acquired)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run scheduled pickup to Codex handoff executor integration.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--pickup-artifact", default=str(DEFAULT_PICKUP_ARTIFACT))
    parser.add_argument("--handoff-path", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE))
    parser.add_argument("--max-handoffs-per-run", type=int, default=MAX_HANDOFFS_PER_RUN)
    parser.add_argument("--codex-executor", default=str(DEFAULT_CODEX_EXECUTOR))
    parser.add_argument("--readiness-gate", default=str(DEFAULT_READINESS_GATE))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser()
    state_dir = Path(args.state_dir).expanduser()
    try:
        result = build_result(args)
        run_path = persist_run_artifacts(state_dir, output, result)
        result["run_result_artifact"] = str(run_path)
        write_json(output, result)
    except Exception as exc:  # noqa: BLE001
        result = base_result(args)
        result["decision"] = "validation_failed"
        result["blocked_reasons"] = [str(exc)]
        write_json(output, result)
        json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True)
        sys.stdout.write("\n")
        return 2

    json.dump(
        {
            "ok": result["ok"],
            "decision": result["decision"],
            "mode": result["mode"],
            "handoff_path": result["handoff_path"],
            "safe_to_continue": result["safe_to_continue"],
            "output": str(output),
        },
        sys.stdout,
        ensure_ascii=False,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
