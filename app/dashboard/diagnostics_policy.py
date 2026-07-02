"""Diagnostics separation policy for dashboard-safe presentation."""
from __future__ import annotations
from typing import Any, Dict, Iterable

TRACEBACK_MARKERS = ["Traceback (most recent call last)", "File \\\"", "Exception:", "RuntimeError:", "ValueError:"]

def contains_raw_traceback(text: str) -> bool:
    return any(marker in text for marker in TRACEBACK_MARKERS)

def suppress_traceback(text: str) -> str:
    if contains_raw_traceback(text):
        return "A pipeline diagnostic exists and is available in operator diagnostics; raw traceback is suppressed from the main dashboard."
    return text

def build_diagnostics(inputs: Dict[str, Any]) -> Dict[str, Any]:
    diagnostics = inputs.get("diagnostics", {})
    raw_error = str(diagnostics.get("raw_error", ""))
    missing = list(diagnostics.get("missing_artifacts", []))
    warnings = list(diagnostics.get("warnings", []))
    errors = list(diagnostics.get("errors", []))
    return {
        "pipeline_status": diagnostics.get("pipeline_status", "offline_sample"),
        "artifact_status": "partial" if missing else "available",
        "missing_artifacts": missing,
        "validation_status": diagnostics.get("validation_status", "sample_valid"),
        "warnings": warnings,
        "errors": [suppress_traceback(str(error)) for error in errors],
        "raw_log_available": bool(raw_error),
        "raw_traceback_suppressed": contains_raw_traceback(raw_error) or any(contains_raw_traceback(str(e)) for e in errors),
        "operator_action_required": bool(missing or errors),
    }

def ensure_main_sections_are_safe(sections: Iterable[Dict[str, Any]]) -> bool:
    for section in sections:
        if section.get("section_id") == "diagnostics":
            continue
        if contains_raw_traceback(str(section)):
            return False
    return True
