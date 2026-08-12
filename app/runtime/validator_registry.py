"""Authoritative validator lifecycle registry and executable gate policy."""
from __future__ import annotations

import json
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
    *, root: Path = ROOT,
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
        result = runner(path) if runner else _subprocess_runner(path, root=root)
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
    return {
        "status": "PASS" if passed else "FAIL", "execution_status": "PASS" if passed else "FAIL",
        "reason": None if passed else "SEMANTIC_VALIDATOR_FAILURE" if semantic_fail else "VALIDATOR_EXIT_FAILURE",
        "returncode": returncode, "semantic_result": semantic,
        "stdout_summary": _summary(result.get("stdout")), "stderr_summary": _summary(result.get("stderr")),
        "duration_seconds": result.get("duration_seconds", round(time.monotonic() - started, 4)),
        "command": result.get("command") or [sys.executable, str(path)], "pass": passed,
    }


def execute_validator_gate(
    gate: str, *, caller_validator_id: str, registry_path: Path = REGISTRY_PATH,
    root: Path = ROOT, runner: Callable[[Path], dict[str, Any]] | None = None,
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
    for entry in selected:
        validator_id = str(entry.get("validator_id"))
        if entry.get("execution_role") == "orchestrator":
            if validator_id != caller_validator_id:
                errors.append(f"{validator_id}:UNEXPECTED_REQUIRED_ORCHESTRATOR")
                results.append({"validator_id": validator_id, "execution_status": "FAIL", "reason": "UNEXPECTED_REQUIRED_ORCHESTRATOR", "pass": False})
            else:
                results.append({
                    "validator_id": validator_id, "execution_status": "SKIPPED_RECURSION_GUARD",
                    "reason": "CALLER_ORCHESTRATOR_SELF_EXCLUDED", "pass": True,
                })
            continue
        evaluated = evaluate_validator_entry(entry, runner, root=root)
        evaluated["validator_id"] = validator_id
        results.append(evaluated)
        if not evaluated.get("pass"):
            errors.append(f"{validator_id}:{evaluated.get('reason') or 'FAIL'}")
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
        "results": results, "errors": errors,
    }
