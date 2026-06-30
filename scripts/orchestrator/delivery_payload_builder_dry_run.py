#!/usr/bin/env python3
"""Build deterministic Delivery Payload Builder V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/delivery_payload_builder_input.example.json")
SCHEMA_VERSION = "delivery_payload_builder_v1"
SUMMARY_SCHEMA_VERSION = "delivery_payload_summary_v1"
CONTRACT_NAME = "delivery_payload_builder"
CONTRACT_VERSION = "v1"
REVIEW_SCHEMA_VERSION = "daily_report_preview_review_workflow_v1"
EXPLAINABILITY_SCHEMA_VERSION = "forecast_explainability_layer_v1"
DECISION_COMPLETED = "delivery_payload_builder_completed"
DECISION_WARNINGS = "delivery_payload_builder_completed_with_warnings"
DECISION_PENDING = "delivery_blocked_pending_approval"
ADVISORY_DISCLAIMER = (
    "This delivery payload is repo-only fixture output for preview review. "
    "It is advisory-only and does not authorize email, LINE, dashboard deployment, "
    "trading, portfolio action, or external system mutation."
)
CHANNELS = ("email", "line", "dashboard")
SIDE_EFFECTS = {
    "read_secrets": False,
    "called_external_model_runtime": False,
    "called_market_data_runtime": False,
    "sent_notification": False,
    "sent_email": False,
    "sent_line_push": False,
    "deployed_dashboard": False,
    "created_api_server": False,
    "placed_trade_order": False,
    "modified_portfolio": False,
    "wrote_persistent_store": False,
    "modified_schedule_or_service": False,
    "modified_github_remote": False,
}
SAFETY = {
    "repo_only": True,
    "fixture_only": True,
    "advisory_only": True,
    "preview_only": True,
    "no_external_model_calls": True,
    "no_market_data_calls": True,
    "no_delivery_actions": True,
    "no_email_send": True,
    "no_line_push": True,
    "no_dashboard_deploy": True,
    "no_persistent_store_writes": True,
    "no_portfolio_actions": True,
    "no_schedule_service_changes": True,
    "dashboard_deploy": False,
    "api_server_created": False,
    "trading_instruction": False,
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


def repo_path(raw_path: Any) -> Path:
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


def slug(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return text.strip("-") or "unknown"


def compact_warning_badges(review: dict[str, Any], explainability: dict[str, Any]) -> list[dict[str, Any]]:
    badges: list[dict[str, Any]] = []
    workflow = as_dict(review.get("preview_review_workflow"))
    for badge in as_list(workflow.get("warning_badges")):
        if not isinstance(badge, dict):
            continue
        badges.append(
            {
                "badge_id": badge.get("badge_id"),
                "source": "preview_review_workflow",
                "label": badge.get("label"),
                "severity": badge.get("severity", "warning"),
            }
        )
    for warning in sorted(str(item) for item in as_list(as_dict(explainability.get("validation_summary")).get("warnings"))):
        badges.append(
            {
                "badge_id": f"delivery_payload_explainability_warning_{slug(warning)}",
                "source": "forecast_explainability_layer",
                "label": warning,
                "severity": "warning",
            }
        )
    return badges


def build_explainability_refs(explainability: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in sorted(
        as_list(explainability.get("forecast_explanations")),
        key=lambda value: str(as_dict(value).get("explanation_id")),
    ):
        if not isinstance(item, dict):
            continue
        refs.append(
            {
                "explanation_id": item.get("explanation_id"),
                "forecast_id": item.get("forecast_id"),
                "stock_id": item.get("stock_id"),
                "horizon": item.get("horizon"),
                "requires_human_review": item.get("requires_human_review") is True,
                "source_trace_ref_count": len(as_list(item.get("source_trace_refs"))),
                "advisory_only": item.get("advisory_only") is True,
            }
        )
    return refs


def channel_descriptor(name: str, delivery_allowed: bool) -> dict[str, Any]:
    return {
        "channel": name,
        "enabled": False,
        "preview_only": True,
        "delivery_allowed": delivery_allowed,
        "delivery_action_performed": False,
        "disabled_reason": "Preview-only fixture channel. No delivery action is performed.",
    }


def channel_payload(channel: str, delivery_allowed: bool, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "channel": channel,
        "enabled": False,
        "preview_only": True,
        "delivery_allowed": delivery_allowed,
        "delivery_action_performed": False,
        "subject": f"Daily Report Preview {payload.get('report_date')}",
        "preview_text": "Delivery preview is blocked until the approval gate is open."
        if not delivery_allowed
        else "Delivery preview is approved by fixture review status, but this helper still sends nothing.",
        "body_refs": {
            "preview_id": payload.get("preview_id"),
            "review_id": payload.get("review_id"),
            "explainability_ref_count": len(as_list(payload.get("explainability_refs"))),
        },
        "advisory_disclaimer": ADVISORY_DISCLAIMER,
    }


def approval_gate(review_status: str, delivery_allowed: bool, review_gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate_id": "delivery_payload_builder_approval_gate_v1",
        "required_review_status": "approved",
        "current_review_status": review_status,
        "source_gate_id": review_gate.get("gate_id"),
        "delivery_allowed": delivery_allowed,
        "gate_open": delivery_allowed,
        "reason": "Explicit approved review status is present."
        if delivery_allowed
        else "Delivery remains blocked until review_status is approved.",
    }


def delivery_blockers(
    review_status: str,
    delivery_allowed: bool,
    human_review_required: bool,
    warning_badges: list[dict[str, Any]],
) -> list[str]:
    blockers: list[str] = []
    if review_status != "approved":
        blockers.append("review_status_not_approved")
    if not delivery_allowed:
        blockers.append("approval_gate_closed")
    if human_review_required:
        blockers.append("human_review_required")
    if warning_badges:
        blockers.append("warning_badges_present")
    return blockers


def build_delivery_payload(data: dict[str, Any], review: dict[str, Any], explainability: dict[str, Any]) -> dict[str, Any]:
    workflow = as_dict(review.get("preview_review_workflow"))
    review_status = str(review.get("review_status") or workflow.get("review_status") or "pending_review")
    delivery_allowed = review_status == "approved"
    warning_badges = compact_warning_badges(review, explainability)
    explainability_refs = build_explainability_refs(explainability)
    human_review_required = (
        workflow.get("requires_human_review") is True
        or as_dict(explainability.get("explainability_summary")).get("human_review_required_count", 0) > 0
        or not delivery_allowed
    )
    payload = {
        "payload_id": f"delivery_payload_{workflow.get('report_date', 'unknown')}",
        "report_date": workflow.get("report_date"),
        "preview_id": workflow.get("preview_id"),
        "review_id": workflow.get("review_id"),
        "review_status": review_status,
        "approval_gate": approval_gate(review_status, delivery_allowed, as_dict(review.get("approval_gate"))),
        "delivery_allowed": delivery_allowed,
        "channels": [channel_descriptor(channel, delivery_allowed) for channel in CHANNELS],
        "email_payload": {},
        "line_payload": {},
        "dashboard_payload": {},
        "explainability_refs": explainability_refs,
        "warning_badges": warning_badges,
        "human_review_required": human_review_required,
        "delivery_blockers": [],
        "advisory_disclaimer": ADVISORY_DISCLAIMER,
    }
    payload["email_payload"] = channel_payload("email", delivery_allowed, payload)
    payload["line_payload"] = channel_payload("line", delivery_allowed, payload)
    payload["dashboard_payload"] = channel_payload("dashboard", delivery_allowed, payload)
    payload["delivery_blockers"] = delivery_blockers(
        review_status,
        delivery_allowed,
        human_review_required,
        warning_badges,
    )
    return payload


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    payload = as_dict(result.get("delivery_payload"))
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "payload_id": payload.get("payload_id"),
        "report_date": payload.get("report_date"),
        "preview_id": payload.get("preview_id"),
        "review_id": payload.get("review_id"),
        "review_status": payload.get("review_status"),
        "delivery_allowed": payload.get("delivery_allowed"),
        "channel_count": len(as_list(payload.get("channels"))),
        "enabled_channel_count": sum(1 for item in as_list(payload.get("channels")) if as_dict(item).get("enabled") is True),
        "warning_badge_count": len(as_list(payload.get("warning_badges"))),
        "explainability_ref_count": len(as_list(payload.get("explainability_refs"))),
        "human_review_required": payload.get("human_review_required"),
        "delivery_blockers": deepcopy(payload.get("delivery_blockers")),
        "deterministic_output": as_dict(result.get("validation_summary")).get("deterministic_output"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "safety": deepcopy(result.get("safety")),
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    sources = as_dict(data.get("input_sources"))
    review_path = repo_path(sources.get("preview_review_workflow_result_path"))
    explainability_path = repo_path(sources.get("forecast_explainability_layer_result_path"))
    review = load_json(review_path)
    explainability = load_json(explainability_path)
    payload = build_delivery_payload(data, review, explainability)
    validation_summary = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "preview_only": True,
        "review_source_schema_matched": review.get("schema_version") == REVIEW_SCHEMA_VERSION,
        "explainability_source_schema_matched": explainability.get("schema_version") == EXPLAINABILITY_SCHEMA_VERSION,
        "review_source_ok": review.get("ok") is True,
        "explainability_source_ok": explainability.get("ok") is True,
        "delivery_allowed_policy_enforced": payload["delivery_allowed"] is (payload["review_status"] == "approved"),
        "channels_disabled": all(as_dict(item).get("enabled") is False for item in as_list(payload.get("channels"))),
        "channels_preview_only": all(as_dict(item).get("preview_only") is True for item in as_list(payload.get("channels"))),
        "channel_payloads_disabled": all(
            as_dict(payload.get(key)).get("enabled") is False
            and as_dict(payload.get(key)).get("preview_only") is True
            and as_dict(payload.get(key)).get("delivery_action_performed") is False
            for key in ["email_payload", "line_payload", "dashboard_payload"]
        ),
        "warning_count": len(as_list(payload.get("warning_badges"))),
        "delivery_blocker_count": len(as_list(payload.get("delivery_blockers"))),
        "warnings": [str(item.get("label")) for item in as_list(payload.get("warning_badges")) if isinstance(item, dict)],
    }
    ok = (
        validation_summary["review_source_schema_matched"]
        and validation_summary["explainability_source_schema_matched"]
        and validation_summary["review_source_ok"]
        and validation_summary["explainability_source_ok"]
        and validation_summary["delivery_allowed_policy_enforced"]
        and validation_summary["channels_disabled"]
        and validation_summary["channels_preview_only"]
        and validation_summary["channel_payloads_disabled"]
        and all(value is False for value in SIDE_EFFECTS.values())
    )
    if not ok:
        decision = "validation_failed"
    elif not payload["delivery_allowed"]:
        decision = DECISION_PENDING
    elif validation_summary["warning_count"] > 0:
        decision = DECISION_WARNINGS
    else:
        decision = DECISION_COMPLETED
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-093"),
        "run_id": data.get("run_id", "delivery-payload-builder-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "delivery_payload": payload,
        "delivery_summary": build_summary(
            {
                "task_id": data.get("task_id", "AI-DEV-093"),
                "run_id": data.get("run_id", "delivery-payload-builder-fixture"),
                "generated_at": data.get("generated_at"),
                "mode": "fixture_dry_run",
                "delivery_payload": payload,
                "validation_summary": validation_summary,
                "ok": ok,
                "decision": decision,
                "safety": deepcopy(SAFETY),
            }
        ),
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision,
        "next_recommendation": "Keep all delivery channels disabled until an approved review fixture exists; do not send, deploy, serve, or persist this payload."
        if not payload["delivery_allowed"]
        else "Approved fixture may satisfy a future delivery gate, but this dry run still performs no delivery action.",
    }


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Delivery Payload Builder V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["delivery_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
