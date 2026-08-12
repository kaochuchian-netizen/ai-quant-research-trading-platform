"""Authoritative validator lifecycle registry and fail-closed evaluator."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "config/governance/validator_registry_v1.json"
VALID_STATES = {"ACTIVE", "SUPERSEDED", "DEPRECATED", "HISTORICAL_ONLY"}


def load_validator_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_validator_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    registry = load_validator_registry(path)
    rows = registry.get("validators") if isinstance(registry.get("validators"), list) else []
    errors: list[str] = []
    ids: set[str] = set()
    paths: set[str] = set()
    by_id = {str(row.get("validator_id")): row for row in rows if isinstance(row, dict)}
    required = {"validator_id", "path", "status", "scope", "introduced_by", "reason", "required_in_branch_gate", "required_in_post_merge", "last_contract_version"}
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
        if not (ROOT / relative).is_file(): errors.append(f"{validator_id}:PATH_MISSING")
        if row.get("status") == "SUPERSEDED":
            replacement = str(row.get("superseded_by") or "")
            if not replacement or replacement not in by_id: errors.append(f"{validator_id}:REPLACEMENT_MISSING")
            elif by_id[replacement].get("status") != "ACTIVE": errors.append(f"{validator_id}:REPLACEMENT_NOT_ACTIVE")
        if row.get("status") in {"DEPRECATED", "HISTORICAL_ONLY"} and not row.get("reason"):
            errors.append(f"{validator_id}:REASON_REQUIRED")
    return {
        "schema_version": "validator_registry_validation_v1", "status": "PASS" if not errors else "FAIL",
        "errors": errors, "counts": {state: sum(row.get("status") == state for row in rows if isinstance(row, dict)) for state in sorted(VALID_STATES)},
    }


def _subprocess_runner(path: Path) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True, timeout=300, check=False)
    return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def evaluate_validator_entry(
    entry: dict[str, Any], runner: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """ACTIVE exceptions are failures; superseded entries name replacements."""
    status = entry.get("status")
    if status == "SUPERSEDED":
        replacement = entry.get("superseded_by")
        return {"status": "SUPERSEDED", "replacement": replacement, "pass": bool(replacement)}
    if status in {"DEPRECATED", "HISTORICAL_ONLY"}:
        return {"status": status, "reason": entry.get("reason"), "pass": bool(entry.get("reason"))}
    if status != "ACTIVE":
        return {"status": "FAIL", "reason": "INVALID_LIFECYCLE_STATE", "pass": False}
    try:
        result = (runner or _subprocess_runner)(ROOT / str(entry.get("path")))
    except Exception as exc:  # fail closed by contract
        return {"status": "FAIL", "reason": "ACTIVE_VALIDATOR_EXCEPTION", "exception": type(exc).__name__, "pass": False}
    return {
        "status": "PASS" if int(result.get("returncode", 1)) == 0 else "FAIL",
        "returncode": result.get("returncode"), "pass": int(result.get("returncode", 1)) == 0,
    }
