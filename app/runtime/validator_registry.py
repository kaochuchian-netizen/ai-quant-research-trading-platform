"""Authoritative validator lifecycle registry and executable gate policy."""
from __future__ import annotations

import json
import hashlib
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "config/governance/validator_registry_v1.json"
VALID_STATES = {"ACTIVE", "SUPERSEDED", "DEPRECATED", "HISTORICAL_ONLY"}
VALID_EXECUTION_ROLES = {"leaf", "orchestrator"}
GATE_FIELDS = {"branch": "required_in_branch_gate", "post_merge": "required_in_post_merge"}
ProgressCallback = Callable[[dict[str, Any]], None]


def load_validator_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_validator_registry(path: Path = REGISTRY_PATH, *, root: Path = ROOT) -> dict[str, Any]:
    registry = load_validator_registry(path)
    rows = registry.get("validators") if isinstance(registry.get("validators"), list) else []
    errors: list[str] = []
    ids: set[str] = set()
    paths: set[str] = set()
    by_id = {str(row.get("validator_id")): row for row in rows if isinstance(row, dict)}
    required = {
        "validator_id", "path", "status", "execution_role", "scope", "introduced_by",
        "reason", "required_in_branch_gate", "required_in_post_merge", "last_contract_version",
    }
    for row in rows:
        if not isinstance(row, dict):
            errors.append("NON_OBJECT_ENTRY"); continue
        missing = sorted(required - set(row))
        validator_id, relative = str(row.get("validator_id") or ""), str(row.get("path") or "")
        if missing: errors.append(f"{validator_id}:MISSING:{','.join(missing)}")
        if validator_id in ids: errors.append(f"{validator_id}:DUPLICATE_ID")
        if relative in paths: errors.append(f"{validator_id}:DUPLICATE_PATH")
        ids.add(validator_id); paths.add(relative)
        if row.get("status") not in VALID_STATES: errors.append(f"{validator_id}:INVALID_STATUS")
        if row.get("execution_role") not in VALID_EXECUTION_ROLES: errors.append(f"{validator_id}:INVALID_EXECUTION_ROLE")
        if not (root / relative).is_file(): errors.append(f"{validator_id}:PATH_MISSING")
        if row.get("status") == "SUPERSEDED":
            replacement = str(row.get("superseded_by") or "")
            if not replacement or replacement not in by_id: errors.append(f"{validator_id}:REPLACEMENT_MISSING")
            elif by_id[replacement].get("status") != "ACTIVE": errors.append(f"{validator_id}:REPLACEMENT_NOT_ACTIVE")
        if row.get("status") in {"DEPRECATED", "HISTORICAL_ONLY"} and not row.get("reason"):
            errors.append(f"{validator_id}:REASON_REQUIRED")
    return {
        "schema_version": "validator_registry_validation_v2", "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "counts": {state: sum(row.get("status") == state for row in rows if isinstance(row, dict)) for state in sorted(VALID_STATES)},
    }


def _semantic_result(stdout: str) -> dict[str, Any] | None:
    try:
        value = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _summary(value: Any, limit: int = 2000) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def normalize_validator_failure_text(text: str, *, root: Path = ROOT) -> str:
    value = str(text or "")
    venv_path = str(ROOT / "venv")
    value = re.sub(r"/private/tmp/ai-dev-[^/]+/(base|head)", "/TMP/WORKTREE", value)
    value = re.sub(r"/tmp/ai-dev-[^/]+/(base|head)", "/TMP/WORKTREE", value)
    roots = {str(ROOT), str(ROOT.resolve()), str(root), str(root.resolve())}
    roots |= {"/private" + item for item in roots if item.startswith("/var/")}
    for item in sorted(roots, key=len, reverse=True):
        if item:
            value = value.replace(item, "/TMP/WORKTREE")
    value = value.replace("/TMP/WORKTREE/venv", venv_path)
    value = re.sub(r"/private/var/folders/(?:[^/]+/)+T/ai-dev-[^/]+", "/TMP/AI_DEV_TEMP", value)
    value = re.sub(r"/var/folders/(?:[^/]+/)+T/ai-dev-[^/]+", "/TMP/AI_DEV_TEMP", value)
    value = re.sub(r"/private/tmp/ai-dev-[^/]+", "/TMP/AI_DEV_TEMP", value)
    value = re.sub(r"/tmp/ai-dev-[^/]+", "/TMP/AI_DEV_TEMP", value)
    value = value.replace("/TMP/WORKTREE", "/ENV_ROOT")
    value = value.replace("/TMP/AI_DEV_TEMP", "/ENV_ROOT")
    value = re.sub(r"revision_(\d{3})_[0-9a-f]{12}\.json", r"revision_\1_<RUNTIME_ID>.json", value)
    value = re.sub(r'("visual_evidence_id"\s*:\s*")[0-9a-f]{64}(")', r"\1<VISUAL_EVIDENCE_ID>\2", value)
    value = re.sub(r"line \d+", "line N", value)
    return value


def validator_failure_fingerprint(stdout: str, stderr: str, *, root: Path = ROOT) -> str:
    text = stderr if str(stderr or "").strip() else stdout
    return hashlib.sha256(normalize_validator_failure_text(text, root=root).encode("utf-8")).hexdigest()


def _subprocess_runner(path: Path, *, root: Path = ROOT, timeout_seconds: int = 300) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, str(path)], cwd=root, capture_output=True, text=True,
        timeout=timeout_seconds, check=False,
    )
    return {
        "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr,
        "duration_seconds": round(time.monotonic() - started, 4),
        "command": [sys.executable, str(path)],
    }


def evaluate_validator_entry(
    entry: dict[str, Any], runner: Callable[[Path], dict[str, Any]] | None = None,
    *, root: Path = ROOT, timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Evaluate one entry fail-closed, including semantic JSON failure."""
    status = entry.get("status")
    if status == "SUPERSEDED":
        replacement = entry.get("superseded_by")
        return {"status": "SUPERSEDED", "execution_status": "SUPERSEDED", "replacement": replacement, "pass": bool(replacement)}
    if status in {"DEPRECATED", "HISTORICAL_ONLY"}:
        return {"status": status, "execution_status": status, "reason": entry.get("reason"), "pass": bool(entry.get("reason"))}
    if status != "ACTIVE":
        return {"status": "FAIL", "execution_status": "FAIL", "reason": "INVALID_LIFECYCLE_STATE", "pass": False}
    path = root / str(entry.get("path") or "")
    if not path.is_file():
        return {"status": "FAIL", "execution_status": "FAIL", "reason": "REQUIRED_VALIDATOR_MISSING", "pass": False, "command": [sys.executable, str(path)]}
    started = time.monotonic()
    try:
        result = runner(path) if runner else _subprocess_runner(path, root=root, timeout_seconds=max(1, int(timeout_seconds or 300)))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        return {
            "status": "FAIL", "execution_status": "TIMEOUT", "reason": "VALIDATOR_TIMEOUT",
            "timeout_seconds": timeout_seconds, "returncode": None,
            "stdout_summary": _summary(stdout), "stderr_summary": _summary(stderr),
            "duration_seconds": round(time.monotonic() - started, 4),
            "command": [sys.executable, str(path)], "pass": False,
            "failure_fingerprint": validator_failure_fingerprint(stdout, stderr, root=root),
        }
    except Exception as exc:  # fail closed by contract
        return {
            "status": "FAIL", "execution_status": "FAIL", "reason": "ACTIVE_VALIDATOR_EXCEPTION",
            "exception": type(exc).__name__, "duration_seconds": round(time.monotonic() - started, 4),
            "command": [sys.executable, str(path)], "pass": False,
        }
    returncode = int(result.get("returncode", 1))
    semantic = result.get("semantic_result") if isinstance(result.get("semantic_result"), dict) else _semantic_result(str(result.get("stdout") or ""))
    semantic_fail = bool(semantic) and (
        semantic.get("status") == "FAIL" or semantic.get("passed") is False or semantic.get("ok") is False
    )
    passed = returncode == 0 and not semantic_fail
    output = {
        "status": "PASS" if passed else "FAIL", "execution_status": "PASS" if passed else "FAIL",
        "reason": None if passed else "SEMANTIC_VALIDATOR_FAILURE" if semantic_fail else "VALIDATOR_EXIT_FAILURE",
        "returncode": returncode, "semantic_result": semantic,
        "stdout_summary": _summary(result.get("stdout")), "stderr_summary": _summary(result.get("stderr")),
        "duration_seconds": result.get("duration_seconds", round(time.monotonic() - started, 4)),
        "command": result.get("command") or [sys.executable, str(path)], "pass": passed,
    }
    if not passed:
        output["failure_fingerprint"] = validator_failure_fingerprint(
            str(result.get("stdout") or ""), str(result.get("stderr") or ""), root=root,
        )
    return output


def execute_validator_gate(
    gate: str, *, caller_validator_id: str, registry_path: Path = REGISTRY_PATH,
    root: Path = ROOT, runner: Callable[[Path], dict[str, Any]] | None = None,
    overall_timeout_seconds: float | None = None,
    per_validator_timeout_seconds: float = 300,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Execute ACTIVE leaf validators selected by registry policy.

    The caller orchestrator is selected and explicitly excluded by the
    recursion guard. Any other required orchestrator is a configuration error.
    """
    gate_field = GATE_FIELDS.get(gate)
    if gate_field is None:
        return {"schema_version": "validator_gate_execution_v1", "gate": gate, "status": "FAIL", "errors": ["UNKNOWN_GATE"]}
    registry_validation = validate_validator_registry(registry_path, root=root)
    if registry_validation["status"] != "PASS":
        return {
            "schema_version": "validator_gate_execution_v1", "gate": gate, "status": "FAIL",
            "registry_validation": registry_validation, "errors": ["REGISTRY_INVALID"],
            "selected_validator_ids": [], "executed_validator_ids": [], "results": [],
        }
    rows = load_validator_registry(registry_path).get("validators") or []
    selected = sorted(
        (row for row in rows if row.get("status") == "ACTIVE" and row.get(gate_field) is True),
        key=lambda row: str(row.get("validator_id")),
    )
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    gate_started = time.monotonic()

    def emit(event: str, **payload: Any) -> None:
        if progress_callback is None:
            return
        progress_callback({
            "schema_version": "validator_gate_progress_v1",
            "event": event,
            "gate": gate,
            "caller_validator_id": caller_validator_id,
            "elapsed_seconds": round(time.monotonic() - gate_started, 4),
            **payload,
        })

    emit("gate_started", selected_count=len(selected))
    timed_out = False
    timeout_detail: dict[str, Any] | None = None
    for index, entry in enumerate(selected, start=1):
        validator_id = str(entry.get("validator_id"))
        elapsed = time.monotonic() - gate_started
        remaining = None if overall_timeout_seconds is None else overall_timeout_seconds - elapsed
        if remaining is not None and remaining <= 0:
            timed_out = True
            timeout_detail = {
                "reason": "GATE_TIMEOUT_BEFORE_VALIDATOR",
                "timeout_seconds": overall_timeout_seconds,
                "elapsed_seconds": round(elapsed, 4),
                "current_validator_id": validator_id,
                "completed_validator_count": len(results),
                "total_validator_count": len(selected),
            }
            errors.append(f"{validator_id}:GATE_TIMEOUT")
            emit("gate_timeout", **timeout_detail)
            break
        emit("validator_started", validator_id=validator_id, index=index, total=len(selected), remaining_timeout_seconds=round(remaining, 4) if remaining is not None else None)
        if entry.get("execution_role") == "orchestrator":
            if validator_id != caller_validator_id:
                errors.append(f"{validator_id}:UNEXPECTED_REQUIRED_ORCHESTRATOR")
                results.append({"validator_id": validator_id, "execution_status": "FAIL", "reason": "UNEXPECTED_REQUIRED_ORCHESTRATOR", "pass": False})
            else:
                results.append({
                    "validator_id": validator_id, "execution_status": "SKIPPED_RECURSION_GUARD",
                    "reason": "CALLER_ORCHESTRATOR_SELF_EXCLUDED", "pass": True,
                })
            emit("validator_completed", validator_id=validator_id, index=index, total=len(selected), execution_status=results[-1].get("execution_status"), duration_seconds=0.0)
            continue
        validator_timeout = per_validator_timeout_seconds
        if remaining is not None:
            validator_timeout = max(1, min(float(per_validator_timeout_seconds), remaining))
        evaluated = evaluate_validator_entry(entry, runner, root=root, timeout_seconds=validator_timeout)
        evaluated["validator_id"] = validator_id
        results.append(evaluated)
        emit("validator_completed", validator_id=validator_id, index=index, total=len(selected), execution_status=evaluated.get("execution_status"), status=evaluated.get("status"), duration_seconds=evaluated.get("duration_seconds"))
        if not evaluated.get("pass"):
            errors.append(f"{validator_id}:{evaluated.get('reason') or 'FAIL'}")
            if evaluated.get("execution_status") == "TIMEOUT":
                timed_out = True
                timeout_detail = {
                    "reason": "VALIDATOR_TIMEOUT",
                    "timeout_seconds": overall_timeout_seconds,
                    "elapsed_seconds": round(time.monotonic() - gate_started, 4),
                    "current_validator_id": validator_id,
                    "completed_validator_count": max(0, len(results) - 1),
                    "total_validator_count": len(selected),
                }
                emit("gate_timeout", **timeout_detail)
                break
    selected_ids = [str(row.get("validator_id")) for row in selected]
    executed_ids = [row["validator_id"] for row in results if row.get("execution_status") not in {"SKIPPED_RECURSION_GUARD"}]
    recursion_ids = [row["validator_id"] for row in results if row.get("execution_status") == "SKIPPED_RECURSION_GUARD"]
    unexplained_skips = [row["validator_id"] for row in results if row.get("execution_status", "").startswith("SKIPPED") and row.get("execution_status") != "SKIPPED_RECURSION_GUARD"]
    if set(selected_ids) != set(executed_ids) | set(recursion_ids):
        errors.append("SELECTED_EXECUTION_COUNT_MISMATCH")
    if unexplained_skips:
        errors.append("UNEXPLAINED_REQUIRED_VALIDATOR_SKIP")
    passed_leaf = sum(row.get("execution_status") == "PASS" for row in results)
    return {
        "schema_version": "validator_gate_execution_v1", "gate": gate,
        "caller_validator_id": caller_validator_id, "status": "PASS" if not errors else "FAIL",
        "registry_version": load_validator_registry(registry_path).get("version"),
        "selected_validator_ids": selected_ids, "executed_validator_ids": executed_ids,
        "recursion_guard_validator_ids": recursion_ids,
        "selected_count": len(selected_ids), "executed_count": len(executed_ids),
        "passed_leaf_count": passed_leaf, "recursion_guard_count": len(recursion_ids),
        "failed_count": sum(not row.get("pass") for row in results),
        "unexplained_skipped_validator_ids": unexplained_skips,
        "duration_seconds": round(time.monotonic() - gate_started, 4),
        "timed_out": timed_out,
        "timeout": timeout_detail,
        "results": results, "errors": errors,
    }
