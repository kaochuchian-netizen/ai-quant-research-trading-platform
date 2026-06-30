#!/usr/bin/env python3
"""Build deterministic Controlled Email Delivery Contract V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/controlled_email_delivery_input.example.json")
SCHEMA_VERSION = "controlled_email_delivery_contract_v1"
SUMMARY_SCHEMA_VERSION = "controlled_email_delivery_summary_v1"
SOURCE_SCHEMA_VERSION = "delivery_payload_builder_v1"
CONTRACT_NAME = "controlled_email_delivery"
CONTRACT_VERSION = "v1"
DECISION_COMPLETED = "controlled_email_delivery_contract_completed"
DECISION_WARNINGS = "controlled_email_delivery_contract_completed_with_warnings"
DECISION_PENDING = "email_delivery_blocked_pending_approval"
SEND_STATUS = "not_sent"
SEND_INTENT = "preview_only_no_send"
ADVISORY_DISCLAIMER = (
    "This controlled email delivery contract is repo-only fixture output for preview review. "
    "It is advisory-only and does not authorize email sending, SMTP, Gmail API, LINE, "
    "dashboard deployment, trading, portfolio action, or external system mutation."
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
    "no_smtp_call": True,
    "no_gmail_api_call": True,
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


def approval_gate(delivery_payload: dict[str, Any]) -> dict[str, Any]:
    review_status = str(delivery_payload.get("review_status") or "pending_review")
    delivery_allowed = delivery_payload.get("delivery_allowed") is True and review_status == "approved"
    source_gate = as_dict(delivery_payload.get("approval_gate"))
    return {
        "gate_id": "controlled_email_delivery_approval_gate_v1",
        "required_review_status": "approved",
        "current_review_status": review_status,
        "source_gate_id": source_gate.get("gate_id"),
        "source_gate_open": source_gate.get("gate_open") is True,
        "delivery_allowed": delivery_allowed,
        "gate_open": delivery_allowed,
        "approval_required": True,
        "reason": "Email delivery remains blocked until review_status is approved and delivery_allowed is true."
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
    email_channel_enabled: bool,
    source_blockers: list[Any],
    human_review_required: bool,
    badges: list[dict[str, Any]],
) -> list[str]:
    blockers = [str(item) for item in source_blockers if str(item).strip()]
    if review_status != "approved":
        blockers.append("review_status_not_approved")
    if not delivery_allowed:
        blockers.append("approval_gate_closed")
    if not email_channel_enabled:
        blockers.append("email_channel_disabled")
    if human_review_required:
        blockers.append("human_review_required")
    if badges:
        blockers.append("warning_badges_present")
    blockers.append("fixture_mode_no_email_send")
    return sorted(set(blockers))


def build_subject_preview(delivery_payload: dict[str, Any]) -> str:
    email_payload = as_dict(delivery_payload.get("email_payload"))
    subject = str(email_payload.get("subject") or "").strip()
    if subject:
        return subject
    return f"Daily Report Preview {delivery_payload.get('report_date')}"


def build_body_preview(delivery_payload: dict[str, Any], source_result: dict[str, Any]) -> dict[str, Any]:
    email_payload = as_dict(delivery_payload.get("email_payload"))
    body_refs = as_dict(email_payload.get("body_refs"))
    return {
        "format": "text_preview_refs",
        "preview_text": str(email_payload.get("preview_text") or "Email delivery preview is blocked pending approval."),
        "payload_id": delivery_payload.get("payload_id"),
        "preview_id": body_refs.get("preview_id") or delivery_payload.get("preview_id"),
        "review_id": body_refs.get("review_id") or delivery_payload.get("review_id"),
        "source_run_id": source_result.get("run_id"),
        "explainability_ref_count": body_refs.get("explainability_ref_count", 0),
        "contains_full_email_body": False,
    }


def build_controlled_email_delivery(source_result: dict[str, Any]) -> dict[str, Any]:
    delivery_payload = as_dict(source_result.get("delivery_payload"))
    review_status = str(delivery_payload.get("review_status") or "pending_review")
    delivery_allowed = delivery_payload.get("delivery_allowed") is True and review_status == "approved"
    email_channel_enabled = delivery_allowed and review_status == "approved"
    badges = warning_badges(delivery_payload)
    human_review_required = delivery_payload.get("human_review_required") is True or not delivery_allowed
    blockers = delivery_blockers(
        review_status,
        delivery_allowed,
        email_channel_enabled,
        as_list(delivery_payload.get("delivery_blockers")),
        human_review_required,
        badges,
    )
    report_date = delivery_payload.get("report_date")
    return {
        "email_delivery_id": f"controlled_email_delivery_{slug(report_date)}",
        "payload_id": delivery_payload.get("payload_id"),
        "report_date": report_date,
        "review_id": delivery_payload.get("review_id"),
        "review_status": review_status,
        "approval_gate": approval_gate(delivery_payload),
        "delivery_allowed": delivery_allowed,
        "email_channel_enabled": email_channel_enabled,
        "preview_only": True,
        "recipients_policy": {
            "policy_id": "controlled_email_recipients_policy_v1",
            "resolution_mode": "fixture_redacted",
            "recipients_resolved": False,
            "recipient_count": 0,
            "allow_external_recipients": False,
            "requires_explicit_runtime_configuration": True,
        },
        "subject_preview": build_subject_preview(delivery_payload),
        "body_preview": build_body_preview(delivery_payload, source_result),
        "attachments_preview": [],
        "delivery_blockers": blockers,
        "warning_badges": badges,
        "human_review_required": human_review_required,
        "advisory_disclaimer": ADVISORY_DISCLAIMER,
        "send_intent": SEND_INTENT,
        "send_status": SEND_STATUS,
    }


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    delivery = as_dict(result.get("controlled_email_delivery"))
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "email_delivery_id": delivery.get("email_delivery_id"),
        "payload_id": delivery.get("payload_id"),
        "report_date": delivery.get("report_date"),
        "review_id": delivery.get("review_id"),
        "review_status": delivery.get("review_status"),
        "delivery_allowed": delivery.get("delivery_allowed"),
        "email_channel_enabled": delivery.get("email_channel_enabled"),
        "preview_only": delivery.get("preview_only"),
        "send_status": delivery.get("send_status"),
        "send_intent": delivery.get("send_intent"),
        "recipient_count": as_dict(delivery.get("recipients_policy")).get("recipient_count"),
        "attachment_count": len(as_list(delivery.get("attachments_preview"))),
        "warning_badge_count": len(as_list(delivery.get("warning_badges"))),
        "delivery_blocker_count": len(as_list(delivery.get("delivery_blockers"))),
        "human_review_required": delivery.get("human_review_required"),
        "deterministic_output": as_dict(result.get("validation_summary")).get("deterministic_output"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "safety": deepcopy(result.get("safety")),
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source_path = repo_path(as_dict(data.get("input_sources")).get("delivery_payload_builder_result_path"))
    source_result = load_json(source_path)
    delivery = build_controlled_email_delivery(source_result)
    validation_summary = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "preview_only": True,
        "source_schema_matched": source_result.get("schema_version") == SOURCE_SCHEMA_VERSION,
        "source_ok": source_result.get("ok") is True,
        "approval_gate_required": True,
        "delivery_allowed_policy_enforced": delivery["delivery_allowed"] is (delivery["review_status"] == "approved"),
        "email_channel_policy_enforced": delivery["email_channel_enabled"]
        is (delivery["delivery_allowed"] is True and delivery["review_status"] == "approved"),
        "send_status_not_sent": delivery["send_status"] == SEND_STATUS,
        "send_intent_preview_only": delivery["send_intent"] == SEND_INTENT,
        "recipients_unresolved": as_dict(delivery.get("recipients_policy")).get("recipients_resolved") is False,
        "attachments_preview_only": True,
        "warning_count": len(as_list(delivery.get("warning_badges"))),
        "delivery_blocker_count": len(as_list(delivery.get("delivery_blockers"))),
        "warnings": [str(item.get("label")) for item in as_list(delivery.get("warning_badges")) if isinstance(item, dict)],
    }
    ok = (
        validation_summary["source_schema_matched"]
        and validation_summary["source_ok"]
        and validation_summary["approval_gate_required"]
        and validation_summary["delivery_allowed_policy_enforced"]
        and validation_summary["email_channel_policy_enforced"]
        and validation_summary["send_status_not_sent"]
        and validation_summary["send_intent_preview_only"]
        and validation_summary["recipients_unresolved"]
        and all(value is False for value in SIDE_EFFECTS.values())
    )
    if not ok:
        decision = "validation_failed"
    elif not delivery["delivery_allowed"]:
        decision = DECISION_PENDING
    elif validation_summary["warning_count"] > 0:
        decision = DECISION_WARNINGS
    else:
        decision = DECISION_COMPLETED
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-094"),
        "run_id": data.get("run_id", "controlled-email-delivery-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "controlled_email_delivery": delivery,
        "email_delivery_summary": {},
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision,
        "next_recommendation": "Keep email delivery blocked until an approved review fixture exists; do not send email or call SMTP/Gmail APIs."
        if not delivery["delivery_allowed"]
        else "The fixture contract is satisfied, but this dry run still performs no email delivery action.",
    }
    result["email_delivery_summary"] = build_summary(result)
    return result


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Controlled Email Delivery Contract V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["email_delivery_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
