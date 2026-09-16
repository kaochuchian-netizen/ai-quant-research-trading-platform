"""Governed base/head quarantine for known validator failures.

The mechanism is intentionally narrow: it never skips validators by name. A
failure can be treated as pre-existing only when the same validator fails on
both base and head with an exact, active, machine-recorded fingerprint.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tarfile
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from app.runtime.validator_registry import (
    evaluate_validator_entry,
    load_validator_registry,
    normalize_validator_failure_text,
    validator_failure_fingerprint,
)

ROOT = Path(__file__).resolve().parents[2]
KNOWN_FAILURES_PATH = ROOT / "config/governance/known_validator_failures_v1.json"
REQUIRED_ENTRY_FIELDS = {
    "validator_id",
    "failure_fingerprint",
    "reason",
    "issue_owner",
    "baseline_reference",
    "introduced_by",
    "expires_at",
    "review_condition",
}


def normalize_failure_text(text: str, *, root: Path | None = None) -> str:
    """Normalize deterministic environment noise while preserving failure shape."""
    return normalize_validator_failure_text(text or "", root=root or ROOT)


def failure_fingerprint_from_output(stdout: str, stderr: str, *, root: Path | None = None) -> str:
    return validator_failure_fingerprint(stdout, stderr, root=root or ROOT)


def load_known_failures(path: Path = KNOWN_FAILURES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_known_failures_config(path: Path = KNOWN_FAILURES_PATH, *, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    errors: list[str] = []
    try:
        data = load_known_failures(path)
    except Exception as exc:
        return {"schema_version": "known_validator_failures_validation_v1", "status": "FAIL", "errors": [f"LOAD_FAILED:{type(exc).__name__}"]}
    if data.get("schema_version") != "known_validator_failures_v1":
        errors.append("INVALID_SCHEMA_VERSION")
    entries = data.get("entries")
    if not isinstance(entries, list):
        errors.append("ENTRIES_NOT_LIST")
        entries = []
    seen: set[tuple[str, str]] = set()
    hex_re = re.compile(r"^[0-9a-f]{64}$")
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry[{idx}]:NOT_OBJECT")
            continue
        missing = sorted(REQUIRED_ENTRY_FIELDS - set(entry))
        validator_id = str(entry.get("validator_id") or f"entry[{idx}]")
        if missing:
            errors.append(f"{validator_id}:MISSING:{','.join(missing)}")
        fingerprint = str(entry.get("failure_fingerprint") or "")
        if not hex_re.match(fingerprint):
            errors.append(f"{validator_id}:INVALID_FINGERPRINT")
        key = (validator_id, fingerprint)
        if key in seen:
            errors.append(f"{validator_id}:DUPLICATE_FINGERPRINT")
        seen.add(key)
        for field in ("reason", "issue_owner", "baseline_reference", "introduced_by", "review_condition"):
            if not str(entry.get(field) or "").strip():
                errors.append(f"{validator_id}:EMPTY:{field}")
        try:
            expires_at = date.fromisoformat(str(entry.get("expires_at") or ""))
        except ValueError:
            errors.append(f"{validator_id}:INVALID_EXPIRES_AT")
            continue
        if expires_at < today:
            errors.append(f"{validator_id}:EXPIRED")
    return {
        "schema_version": "known_validator_failures_validation_v1",
        "status": "PASS" if not errors else "FAIL",
        "entry_count": len(entries),
        "errors": errors,
    }


def _entry_by_id(registry_path: Path, validator_id: str) -> dict[str, Any] | None:
    for entry in load_validator_registry(registry_path).get("validators") or []:
        if str(entry.get("validator_id")) == validator_id:
            return entry
    return None


def _extract_archive(repo_root: Path, ref: str, destination: Path) -> None:
    archive = subprocess.run(
        ["git", "archive", ref],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if archive.returncode != 0:
        raise RuntimeError(archive.stderr.decode("utf-8", errors="replace") or f"git archive failed for {ref}")
    import io

    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
        tar.extractall(destination)


def _evaluate_entry_at_ref(repo_root: Path, registry_path: Path, validator_id: str, ref: str) -> dict[str, Any]:
    entry = _entry_by_id(registry_path, validator_id)
    if entry is None:
        return {"status": "FAIL", "pass": False, "reason": "VALIDATOR_NOT_IN_REGISTRY", "validator_id": validator_id}
    with tempfile.TemporaryDirectory(prefix=f"known-failure-{validator_id}-") as raw:
        root = Path(raw)
        _extract_archive(repo_root, ref, root)
        evaluated = evaluate_validator_entry(entry, root=root)
        evaluated["validator_id"] = validator_id
        return evaluated


def _fingerprint_for_evaluated(evaluated: dict[str, Any], *, root: Path) -> str | None:
    if evaluated.get("pass"):
        return None
    fingerprint = evaluated.get("failure_fingerprint")
    return str(fingerprint) if fingerprint else None


def classify_known_failure_pair(
    *,
    validator_id: str,
    base_pass: bool,
    head_pass: bool,
    base_fingerprint: str | None,
    head_fingerprint: str | None,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify one base/head validator result pair using exact quarantine metadata."""
    matched = next(
        (
            entry for entry in entries
            if entry.get("validator_id") == validator_id
            and entry.get("failure_fingerprint") == base_fingerprint == head_fingerprint
        ),
        None,
    )
    if base_pass and head_pass:
        return {"classification": "RECOVERED_VALIDATOR", "decision": "PASS_STALE_QUARANTINE_REMOVABLE", "quarantine_match": False}
    if base_pass and not head_pass:
        return {"classification": "HEAD_ONLY_FAILURE", "decision": "FAIL", "quarantine_match": False}
    if not base_pass and not head_pass and base_fingerprint == head_fingerprint and matched:
        return {"classification": "PRE_EXISTING_IDENTICAL", "decision": "ALLOW", "quarantine_match": True}
    if not base_pass and not head_pass and base_fingerprint != head_fingerprint:
        return {"classification": "PRE_EXISTING_BUT_CHANGED", "decision": "FAIL", "quarantine_match": False}
    return {"classification": "UNKNOWN_FAILURE", "decision": "FAIL", "quarantine_match": False}


def apply_known_failure_quarantine(
    registry_gate: dict[str, Any],
    *,
    base_ref: str,
    head_ref: str,
    repo_root: Path = ROOT,
    registry_path: Path | None = None,
    quarantine_path: Path = KNOWN_FAILURES_PATH,
    today: date | None = None,
) -> dict[str, Any]:
    """Return adjusted gate plus machine-readable quarantine evidence."""
    registry_path = registry_path or (repo_root / "config/governance/validator_registry_v1.json")
    config_validation = validate_known_failures_config(quarantine_path, today=today)
    evidence: list[dict[str, Any]] = []
    if config_validation.get("status") != "PASS":
        return {
            "status": "FAIL",
            "config_validation": config_validation,
            "evidence": evidence,
            "adjusted_registry_gate": registry_gate,
            "errors": ["KNOWN_FAILURE_QUARANTINE_INVALID"],
        }
    known = load_known_failures(quarantine_path).get("entries") or []
    by_validator: dict[str, list[dict[str, Any]]] = {}
    for entry in known:
        by_validator.setdefault(str(entry.get("validator_id")), []).append(entry)
    adjusted = json.loads(json.dumps(registry_gate))
    remaining_errors: list[str] = []
    stale: list[dict[str, Any]] = []
    allowed_validators: set[str] = set()
    results = adjusted.get("results") if isinstance(adjusted.get("results"), list) else []
    for result in results:
        validator_id = str(result.get("validator_id") or "")
        if result.get("pass"):
            if validator_id in by_validator:
                stale.append({"validator_id": validator_id, "classification": "RECOVERED_VALIDATOR", "decision": "PASS_STALE_QUARANTINE_REMOVABLE"})
            continue
        entries = by_validator.get(validator_id) or []
        if not entries:
            remaining_errors.append(f"{validator_id}:{result.get('reason') or 'FAIL'}")
            continue
        base_eval = _evaluate_entry_at_ref(repo_root, registry_path, validator_id, base_ref)
        head_eval = result if head_ref == "HEAD" else _evaluate_entry_at_ref(repo_root, registry_path, validator_id, head_ref)
        base_pass = bool(base_eval.get("pass"))
        head_pass = bool(head_eval.get("pass"))
        base_fp = _fingerprint_for_evaluated(base_eval, root=repo_root)
        head_fp = _fingerprint_for_evaluated(head_eval, root=repo_root)
        classified = classify_known_failure_pair(
            validator_id=validator_id,
            base_pass=base_pass,
            head_pass=head_pass,
            base_fingerprint=base_fp,
            head_fingerprint=head_fp,
            entries=entries,
        )
        classification = str(classified["classification"])
        decision = str(classified["decision"])
        matched = bool(classified["quarantine_match"])
        if classification == "RECOVERED_VALIDATOR":
            stale.append({"validator_id": validator_id, "classification": classification, "decision": decision})
        elif classification == "PRE_EXISTING_IDENTICAL":
            allowed_validators.add(validator_id)
            result["quarantined_known_failure"] = True
            result["pass"] = True
            result["status"] = "PASS"
            result["execution_status"] = "QUARANTINED_PRE_EXISTING_IDENTICAL"
            result["reason"] = "PRE_EXISTING_IDENTICAL_KNOWN_FAILURE"
        evidence.append({
            "validator_id": validator_id,
            "base_status": "PASS" if base_pass else "FAIL",
            "head_status": "PASS" if head_pass else "FAIL",
            "base_fingerprint": base_fp,
            "head_fingerprint": head_fp,
            "quarantine_match": bool(matched),
            "classification": classification,
            "decision": decision,
        })
        if decision == "FAIL":
            remaining_errors.append(f"{validator_id}:{classification}")
    for error in registry_gate.get("errors", []) or []:
        validator_id = str(error).split(":", 1)[0]
        if validator_id not in allowed_validators and not any(str(item).startswith(f"{validator_id}:") for item in remaining_errors):
            remaining_errors.append(str(error))
    adjusted["errors"] = remaining_errors
    adjusted["status"] = "PASS" if not remaining_errors else "FAIL"
    adjusted["failed_count"] = sum(not row.get("pass") for row in results)
    return {
        "status": adjusted["status"],
        "config_validation": config_validation,
        "evidence": evidence,
        "stale_quarantine": stale,
        "adjusted_registry_gate": adjusted,
        "errors": remaining_errors,
    }
