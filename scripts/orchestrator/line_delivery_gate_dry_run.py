#!/usr/bin/env python3
"""Build deterministic LINE Delivery Gate Contract V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/line_delivery_gate_input.example.json")
SCHEMA_VERSION = "line_delivery_gate_contract_v1"
SUMMARY_SCHEMA_VERSION = "line_delivery_gate_summary_v1"
SOURCE_SCHEMA_VERSION = "delivery_payload_builder_v1"
CONTRACT_NAME = "line_delivery_gate"
CONTRACT_VERSION = "v1"
DECISION_COMPLETED = "line_delivery_gate_contract_completed"
DECISION_WARNINGS = "line_delivery_gate_contract_completed_with_warnings"
DECISION_PENDING = "line_delivery_blocked_pending_approval"
PUSH_STATUS = "not_sent"
PUSH_INTENT = "preview_only_no_push"
ADVISORY_DISCLAIMER = (
    "This LINE delivery gate contract is repo-only fixture output for preview review. "
    "It is advisory-only and does not authorize LINE push, LINE API calls, email sending, "
    "SMTP, Gmail API, dashboard deployment, trading, portfolio action, or external system mutation."
)
SIDE_EFFECTS = {
    "read_secrets": False,
    "called_external_model_runtime": False,
    "called_market_data_runtime": False,
    "sent_notification": False,
    "sent_email": False,
    "called_smtp": False,
    "called_gmail_api": False,
    "sent_line_push": False,
    "called_line_api": False,
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
    "no_line_push": True,
    "no_line_api_call": True,
    "no_email_send": True,
    "no_smtp_call": True,
    "no_gmail_api_call": True,
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


def approval_gate(delivery_payload: dict[str, Any]) -> dict[str, Any]:
    review_status = str(delivery_payload.get("review_status") or "pending_review")
    delivery_allowed = delivery_payload.get("delivery_allowed") is True and review_status == "approved"
    source_gate = as_dict(delivery_payload.get("approval_gate"))
    return {
        "gate_id": "line_delivery_gate_approval_gate_v1",
        "required_review_status": "approved",
        "current_review_status": review_status,
        "source_gate_id": source_gate.get("gate_id"),
        "source_gate_open": source_gate.get("gate_open") is True,
        "delivery_allowed": delivery_allowed,
        "gate_open": delivery_allowed,
        "approval_required": True,
        "reason": "LINE delivery remains blocked until review_status is approved and delivery_allowed is true."
        if not delivery_allowed
        else "Approved review status and delivery_allowed are present; fixture mode still sends nothing.",
    }


def warning_badges(delivery_payload: dict[str, Any]) -> list[dict[str, Any]]:
    badges: list[dict[str, Any]] = []
    for item in as_list(delivery_payload.get("warning_badges")):
        if not isinstance(item, dict):
            continue
        badges.append(
            {
                "badge_id": item.get("badge_id"),
                "source": item.get("source", "delivery_payload_builder"),
                "label": item.get("label"),
                "severity": item.get("severity", "warning"),
            }
        )
    return sorted(badges, key=lambda item: str(item.get("badge_id")))


def delivery_blockers(
    review_status: str,
    delivery_allowed: bool,
    line_channel_enabled: bool,
    source_blockers: list[Any],
    human_review_required: bool,
    badges: list[dict[str, Any]],
) -> list[str]:
    blockers = [str(item) for item in source_blockers if str(item).strip()]
    if review_status != "approved":
        blockers.append("review_status_not_approved")
    if not delivery_allowed:
        blockers.append("approval_gate_closed")
    if not line_channel_enabled:
        blockers.append("line_channel_disabled")
    if human_review_required:
        blockers.append("human_review_required")
    if badges:
        blockers.append("warning_badges_present")
    blockers.append("fixture_mode_no_line_push")
    blockers.append("fixture_mode_no_line_api_call")
    return sorted(set(blockers))


def build_message_preview(delivery_payload: dict[str, Any], source_result: dict[str, Any]) -> dict[str, Any]:
    line_payload = as_dict(delivery_payload.get("line_payload"))
    body_refs = as_dict(line_payload.get("body_refs"))
    return {
        "format": "line_text_preview_refs",
        "preview_text": str(line_payload.get("preview_text") or "LINE delivery preview is blocked pending approval."),
        "subject": str(line_payload.get("subject") or f"Daily Report Preview {delivery_payload.get('report_date')}"),
        "payload_id": delivery_payload.get("payload_id"),
        "preview_id": body_refs.get("preview_id") or delivery_payload.get("preview_id"),
        "review_id": body_refs.get("review_id") or delivery_payload.get("review_id"),
        "source_run_id": source_result.get("run_id"),
        "explainability_ref_count": body_refs.get("explainability_ref_count", 0),
        "contains_full_line_message": False,
    }


def build_link_preview(delivery_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "link_policy_id": "line_delivery_gate_link_policy_v1",
        "links_resolved": False,
        "link_count": 0,
        "allow_external_links": False,
        "requires_explicit_runtime_configuration": True,
        "preview_refs": {
            "payload_id": delivery_payload.get("payload_id"),
            "preview_id": delivery_payload.get("preview_id"),
            "review_id": delivery_payload.get("review_id"),
        },
    }


def build_line_delivery_gate(source_result: dict[str, Any]) -> dict[str, Any]:
    delivery_payload = as_dict(source_result.get("delivery_payload"))
    review_status = str(delivery_payload.get("review_status") or "pending_review")
    delivery_allowed = delivery_payload.get("delivery_allowed") is True and review_status == "approved"
    line_channel_enabled = delivery_allowed and review_status == "approved"
    badges = warning_badges(delivery_payload)
    human_review_required = delivery_payload.get("human_review_required") is True or not delivery_allowed
    blockers = delivery_blockers(
        review_status,
        delivery_allowed,
        line_channel_enabled,
        as_list(delivery_payload.get("delivery_blockers")),
        human_review_required,
        badges,
    )
    report_date = delivery_payload.get("report_date")
    return {
        "line_delivery_id": f"line_delivery_gate_{slug(report_date)}",
        "payload_id": delivery_payload.get("payload_id"),
        "report_date": report_date,
        "review_id": delivery_payload.get("review_id"),
        "review_status": review_status,
        "approval_gate": approval_gate(delivery_payload),
        "delivery_allowed": delivery_allowed,
        "line_channel_enabled": line_channel_enabled,
        "preview_only": True,
        "recipient_policy": {
            "policy_id": "line_delivery_gate_recipient_policy_v1",
            "resolution_mode": "fixture_redacted",
            "recipients_resolved": False,
            "recipient_count": 0,
            "allow_external_recipients": False,
            "requires_explicit_runtime_configuration": True,
        },
        "message_preview": build_message_preview(delivery_payload, source_result),
        "link_preview": build_link_preview(delivery_payload),
        "delivery_blockers": blockers,
        "warning_badges": badges,
        "human_review_required": human_review_required,
        "advisory_disclaimer": ADVISORY_DISCLAIMER,
        "push_intent": PUSH_INTENT,
        "push_status": PUSH_STATUS,
    }


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    gate = as_dict(result.get("line_delivery_gate"))
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "line_delivery_id": gate.get("line_delivery_id"),
        "payload_id": gate.get("payload_id"),
        "report_date": gate.get("report_date"),
        "review_id": gate.get("review_id"),
        "review_status": gate.get("review_status"),
        "delivery_allowed": gate.get("delivery_allowed"),
        "line_channel_enabled": gate.get("line_channel_enabled"),
        "preview_only": gate.get("preview_only"),
        "push_status": gate.get("push_status"),
        "push_intent": gate.get("push_intent"),
        "recipient_count": as_dict(gate.get("recipient_policy")).get("recipient_count"),
        "link_count": as_dict(gate.get("link_preview")).get("link_count"),
        "warning_badge_count": len(as_list(gate.get("warning_badges"))),
        "delivery_blocker_count": len(as_list(gate.get("delivery_blockers"))),
        "human_review_required": gate.get("human_review_required"),
        "deterministic_output": as_dict(result.get("validation_summary")).get("deterministic_output"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "safety": deepcopy(result.get("safety")),
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source_path = repo_path(as_dict(data.get("input_sources")).get("delivery_payload_builder_result_path"))
    source_result = load_json(source_path)
    gate = build_line_delivery_gate(source_result)
    validation_summary = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "preview_only": True,
        "source_schema_matched": source_result.get("schema_version") == SOURCE_SCHEMA_VERSION,
        "source_ok": source_result.get("ok") is True,
        "approval_gate_required": True,
        "delivery_allowed_policy_enforced": gate["delivery_allowed"] is (gate["review_status"] == "approved"),
        "line_channel_policy_enforced": gate["line_channel_enabled"]
        is (gate["delivery_allowed"] is True and gate["review_status"] == "approved"),
        "push_status_not_sent": gate["push_status"] == PUSH_STATUS,
        "push_intent_preview_only": gate["push_intent"] == PUSH_INTENT,
        "recipients_unresolved": as_dict(gate.get("recipient_policy")).get("recipients_resolved") is False,
        "links_unresolved": as_dict(gate.get("link_preview")).get("links_resolved") is False,
        "warning_count": len(as_list(gate.get("warning_badges"))),
        "delivery_blocker_count": len(as_list(gate.get("delivery_blockers"))),
        "warnings": [str(item.get("label")) for item in as_list(gate.get("warning_badges")) if isinstance(item, dict)],
    }
    ok = (
        validation_summary["source_schema_matched"]
        and validation_summary["source_ok"]
        and validation_summary["approval_gate_required"]
        and validation_summary["delivery_allowed_policy_enforced"]
        and validation_summary["line_channel_policy_enforced"]
        and validation_summary["push_status_not_sent"]
        and validation_summary["push_intent_preview_only"]
        and validation_summary["recipients_unresolved"]
        and validation_summary["links_unresolved"]
        and all(value is False for value in SIDE_EFFECTS.values())
    )
    if not ok:
        decision = "validation_failed"
    elif not gate["delivery_allowed"]:
        decision = DECISION_PENDING
    elif validation_summary["warning_count"] > 0:
        decision = DECISION_WARNINGS
    else:
        decision = DECISION_COMPLETED
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-095"),
        "run_id": data.get("run_id", "line-delivery-gate-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "line_delivery_gate": gate,
        "line_delivery_summary": {},
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision,
        "next_recommendation": "Keep LINE delivery blocked until an approved review fixture exists; do not push LINE or call LINE APIs."
        if not gate["delivery_allowed"]
        else "The fixture contract is satisfied, but this dry run still performs no LINE delivery action.",
    }
    result["line_delivery_summary"] = build_summary(result)
    return result


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build LINE Delivery Gate Contract V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["line_delivery_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
