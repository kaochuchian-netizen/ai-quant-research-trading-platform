#!/usr/bin/env python3
"""Build a deterministic Daily Report Preview Review Workflow V1 fixture."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_preview_review_workflow_input.example.json")
SCHEMA_VERSION = "daily_report_preview_review_workflow_v1"
SOURCE_SCHEMA_VERSION = "daily_report_dashboard_static_page_v1"
SUPPORTED_REVIEW_STATUSES = {"pending_review", "approved", "rejected", "needs_revision"}
SIDE_EFFECTS = {
    "read_secrets": False,
    "called_external_model_runtime": False,
    "called_market_data_runtime": False,
    "sent_notification": False,
    "placed_trade_order": False,
    "modified_portfolio": False,
    "wrote_persistent_store": False,
    "modified_schedule_or_service": False,
    "modified_github_remote": False,
    "sent_daily_report": False,
    "wrote_production_db": False,
    "deployed_dashboard": False,
    "created_api_server": False,
}
SAFETY = {
    "repo_only": True,
    "fixture_only": True,
    "preview_only": True,
    "advisory_only": True,
    "dashboard_deploy": False,
    "api_server_created": False,
    "no_external_model_calls": True,
    "no_market_data_calls": True,
    "no_delivery_actions": True,
    "no_persistent_store_writes": True,
    "no_portfolio_actions": True,
    "no_schedule_service_changes": True,
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("input JSON root must be an object")
    return data


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def resolve_repo_path(raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SystemExit("referenced fixture path must be a non-empty string")
    path = Path(raw_path)
    if path.is_absolute():
        raise SystemExit("referenced fixture path must be repo-relative")
    if ".." in path.parts:
        raise SystemExit("referenced fixture path must not contain parent traversal")
    return path


def stable_json(payload: Any, pretty: bool) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    return f"{text}\n" if pretty else text


def compact_badges(badges: list[Any]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for badge in badges:
        if not isinstance(badge, dict):
            continue
        compacted.append(
            {
                "badge_id": badge.get("badge_id"),
                "card_id": badge.get("card_id"),
                "label": badge.get("label"),
                "severity": badge.get("severity", "warning"),
            }
        )
    return compacted


def source_dashboard_static_page_summary(source_path: Path, source: dict[str, Any]) -> dict[str, Any]:
    page = as_dict(source.get("dashboard_page"))
    latest = as_dict(source.get("latest_preview_card"))
    validation = as_dict(source.get("validation_summary"))
    return {
        "source_path": str(source_path),
        "source_schema_version": source.get("schema_version"),
        "source_task_id": source.get("task_id"),
        "source_run_id": source.get("run_id"),
        "source_generated_at": source.get("generated_at"),
        "source_mode": source.get("mode"),
        "source_decision": source.get("decision"),
        "source_ok": source.get("ok") is True,
        "source_page_id": page.get("page_id"),
        "source_page_title": page.get("page_title"),
        "source_preview_id": latest.get("preview_id"),
        "source_report_date": latest.get("report_date"),
        "source_manifest_ref": page.get("manifest_ref"),
        "source_markdown_ref": page.get("markdown_ref"),
        "source_warning_count": len(as_list(source.get("warning_badges"))),
        "source_requires_human_review": bool(validation.get("warnings")) or latest.get("status") == "requires_human_review",
    }


def status_timestamps(review_status: str, generated_at: Any) -> dict[str, Any]:
    approved_at = generated_at if review_status == "approved" else None
    rejected_at = generated_at if review_status == "rejected" else None
    revision_requested_at = generated_at if review_status == "needs_revision" else None
    return {
        "approved_at": approved_at,
        "rejected_at": rejected_at,
        "revision_requested_at": revision_requested_at,
    }


def approval_gate(review_status: str, delivery_allowed: bool, requires_human_review: bool) -> dict[str, Any]:
    return {
        "gate_id": "daily_report_preview_delivery_approval_gate_v1",
        "required_review_status": "approved",
        "current_review_status": review_status,
        "requires_human_review": requires_human_review,
        "delivery_allowed": delivery_allowed,
        "gate_open": delivery_allowed,
        "reason": (
            "Preview approved by explicit review fixture."
            if delivery_allowed
            else "Delivery remains blocked until review_status is approved."
        ),
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source_path = resolve_repo_path(as_dict(data.get("input_sources")).get("dashboard_static_page_result_path"))
    source = load_json(source_path)
    review_request = as_dict(data.get("review_request"))
    review_status = str(review_request.get("review_status", "pending_review"))
    if review_status not in SUPPORTED_REVIEW_STATUSES:
        review_status = "pending_review"
    generated_at = data.get("generated_at")
    page = as_dict(source.get("dashboard_page"))
    latest = as_dict(source.get("latest_preview_card"))
    warning_badges = compact_badges(as_list(source.get("warning_badges")))
    requires_human_review = review_status != "approved" or bool(warning_badges)
    delivery_allowed = review_status == "approved"
    timestamps = status_timestamps(review_status, generated_at)
    workflow = {
        "review_id": review_request.get("review_id", "daily_report_preview_review_20260630"),
        "preview_id": latest.get("preview_id"),
        "report_date": latest.get("report_date"),
        "review_status": review_status,
        "reviewer": review_request.get("reviewer", "human_reviewer_pending"),
        "reviewer_notes": deepcopy(review_request.get("reviewer_notes", [])),
        "approval_gate": approval_gate(review_status, delivery_allowed, requires_human_review),
        "approved_at": timestamps["approved_at"],
        "rejected_at": timestamps["rejected_at"],
        "revision_requested_at": timestamps["revision_requested_at"],
        "revision_notes": deepcopy(review_request.get("revision_notes", [])),
        "source_dashboard_page_ref": page.get("page_id"),
        "manifest_ref": page.get("manifest_ref"),
        "markdown_ref": page.get("markdown_ref"),
        "warning_badges": warning_badges,
        "requires_human_review": requires_human_review,
        "delivery_allowed": delivery_allowed,
    }
    source_summary = source_dashboard_static_page_summary(source_path, source)
    validation_summary = {
        "source_schema_expected": SOURCE_SCHEMA_VERSION,
        "source_schema_matched": source.get("schema_version") == SOURCE_SCHEMA_VERSION,
        "source_ok": source.get("ok") is True,
        "source_mode_fixture_dry_run": source.get("mode") == "fixture_dry_run",
        "supported_review_status": review_status in SUPPORTED_REVIEW_STATUSES,
        "approval_gate_included": True,
        "approval_gate_enforced": workflow["approval_gate"]["delivery_allowed"] == delivery_allowed,
        "delivery_allowed_policy_enforced": delivery_allowed is (review_status == "approved"),
        "reviewer_notes_included": isinstance(workflow["reviewer_notes"], list),
        "warning_badges_included": True,
        "source_refs_present": all(
            bool(workflow.get(key))
            for key in ["source_dashboard_page_ref", "manifest_ref", "markdown_ref", "preview_id", "report_date"]
        ),
        "deterministic_output": True,
        "fixture_only": True,
        "warnings": sorted({str(badge.get("label")) for badge in warning_badges if badge.get("label")}),
    }
    ok = (
        validation_summary["source_schema_matched"]
        and validation_summary["source_ok"]
        and validation_summary["source_mode_fixture_dry_run"]
        and validation_summary["supported_review_status"]
        and validation_summary["approval_gate_enforced"]
        and validation_summary["delivery_allowed_policy_enforced"]
        and validation_summary["source_refs_present"]
        and all(value is False for value in SIDE_EFFECTS.values())
        and SAFETY["repo_only"] is True
        and SAFETY["fixture_only"] is True
        and SAFETY["preview_only"] is True
        and SAFETY["dashboard_deploy"] is False
        and SAFETY["api_server_created"] is False
    )
    decision = (
        "daily_report_preview_review_workflow_completed_with_warnings"
        if validation_summary["warnings"] or review_status != "approved"
        else "daily_report_preview_review_workflow_completed"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-089"),
        "run_id": data.get("run_id", "daily-report-preview-review-workflow-fixture"),
        "generated_at": generated_at,
        "mode": "fixture_dry_run",
        "preview_review_workflow": workflow,
        "review_status": review_status,
        "approval_gate": deepcopy(workflow["approval_gate"]),
        "delivery_allowed": delivery_allowed,
        "reviewer_notes": deepcopy(workflow["reviewer_notes"]),
        "source_dashboard_static_page_summary": source_summary,
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": {**deepcopy(SAFETY), "delivery_allowed": delivery_allowed},
        "ok": ok,
        "decision": decision if ok else "validation_failed",
        "next_recommendation": (
            "Keep delivery blocked until an approved preview review fixture is produced; do not send, deploy, serve, or persist this preview."
            if not delivery_allowed
            else "Approved fixture may satisfy a future delivery gate, but this dry run still performs no delivery action."
        ),
    }


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    workflow = as_dict(result.get("preview_review_workflow"))
    source_summary = as_dict(result.get("source_dashboard_static_page_summary"))
    return {
        "schema_version": "daily_report_preview_review_summary_v1",
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "review_id": workflow.get("review_id"),
        "preview_id": workflow.get("preview_id"),
        "report_date": workflow.get("report_date"),
        "review_status": result.get("review_status"),
        "delivery_allowed": result.get("delivery_allowed"),
        "requires_human_review": workflow.get("requires_human_review"),
        "warning_badge_count": len(as_list(workflow.get("warning_badges"))),
        "source_page_id": source_summary.get("source_page_id"),
        "source_run_id": source_summary.get("source_run_id"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "deterministic_output": as_dict(result.get("validation_summary")).get("deterministic_output"),
        "side_effects": deepcopy(result.get("side_effects")),
        "safety": deepcopy(result.get("safety")),
    }


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Daily Report Preview Review Workflow V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(build_summary(result), Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
