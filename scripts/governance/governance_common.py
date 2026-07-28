"""Shared read-only helpers for versioned platform governance validators."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TASK_SECTIONS = (
    "Platform Context", "Current Phase", "Phase Objective", "Task Role",
    "User-visible Target", "Production Target", "Problem", "Root Cause",
    "Scope", "Non-goals", "Implementation Contract", "Evidence Contract",
    "Rendering Contract", "Engineering Gate", "Product Quality Gate",
    "Operational Gate", "Natural Verification", "Completion",
    "Phase Contribution", "Limitations", "Deferred Scope", "Completion Report", "Safety",
)

COMPLETION_SECTIONS = (
    "Implementation", "User-visible Outcome", "Evidence", "Quality Gate",
    "Known Limitations", "Deferred Enhancements", "Natural Verification",
    "Phase Contribution", "Regression", "Production Usability", "Final Status", "Safety",
)

FINAL_STATUSES = {"OPEN", "IMPLEMENTED_PENDING_NATURAL_VERIFICATION", "CLOSED"}
PHASE_STATUSES = {"PLANNED", "IN_PROGRESS", "CLOSED"}
EXIT_CLASSIFICATIONS = {"MUST_FIX_BEFORE_CLOSE", "ACCEPTABLE_LIMITATION", "DEFERRED_ENHANCEMENT"}
EXIT_STATUSES = {"OPEN", "IN_PROGRESS", "CLOSED", "ACCEPTED", "DEFERRED"}
PENDING_STATES = {"VERIFIED", "PENDING", "ACCEPTED", "DEFERRED"}
TRENDS = {"improving", "stable", "declining"}


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"json_read:{exc.__class__.__name__}"]
    return (value, []) if isinstance(value, dict) else (None, ["json_root_must_be_object"])


def markdown_headings(text: str) -> set[str]:
    return {match.group(1).strip() for match in re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE)}


def validate_markdown_sections(path: Path, sections: tuple[str, ...]) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"read:{exc.__class__.__name__}"]
    headings = markdown_headings(text)
    errors = [f"missing_section:{section}" for section in sections if section not in headings]
    if not re.search(r"^Task ID:\s*AI-DEV-(?:\d{3}|NNN)\s*$", text, re.MULTILINE):
        errors.append("missing_or_invalid_task_id")
    for section in sections:
        match = re.search(rf"^##\s+{re.escape(section)}\s*$\n(.*?)(?=^##\s+|\Z)", text, re.MULTILINE | re.DOTALL)
        if match and not match.group(1).strip():
            errors.append(f"empty_section:{section}")
    return errors


def result_payload(name: str, errors: list[str], evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "validator": name,
        "ok": not errors,
        "errors": sorted(set(errors)),
        "evidence": evidence,
        "side_effects": {
            "production_pipeline": False, "notification": False, "trading": False,
            "scheduler": False, "secrets": False, "repository_write": False,
        },
    }
