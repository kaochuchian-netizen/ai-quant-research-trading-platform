"""Separate user-facing report content from operational diagnostics."""
from __future__ import annotations
from typing import Any
from .report_sanitizer import SanitizationResult
def build_diagnostics(pipeline_status: str, sanitization: SanitizationResult, source_warnings: list[str] | None = None, artifact_status: str = "offline_sample") -> dict[str, Any]:
    return {
        "pipeline_status": pipeline_status,
        "source_warnings": source_warnings or [],
        "raw_log_suppressed": sanitization.raw_log_suppressed,
        "raw_traceback_suppressed": sanitization.raw_traceback_suppressed,
        "operational_log_suppressed": sanitization.operational_log_suppressed,
        "suppressed_log_count": sanitization.suppressed_log_count,
        "suppressed_log_categories": sanitization.suppressed_log_categories,
        "removed_examples": sanitization.removed_examples,
        "artifact_status": artifact_status,
        "operator_action_required": sanitization.raw_traceback_suppressed or artifact_status in {"no_fresh_artifact", "pipeline_timed_out", "failed"},
    }
def raw_log_summary(raw_text: str, sanitization: SanitizationResult) -> dict[str, Any]:
    return {"raw_line_count": len(raw_text.splitlines()), "suppressed_log_count": sanitization.suppressed_log_count, "suppressed_log_categories": sanitization.suppressed_log_categories, "raw_text_retained_in_user_report": False}
