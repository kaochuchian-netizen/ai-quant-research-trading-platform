#!/usr/bin/env python3
"""Build deterministic Dashboard Delivery Gate V1 fixture results."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/dashboard_delivery_gate_input.example.json")
SCHEMA_VERSION = "dashboard_delivery_gate_v1"
SUMMARY_SCHEMA_VERSION = "dashboard_delivery_gate_summary_v1"
DELIVERY_PAYLOAD_SCHEMA_VERSION = "delivery_payload_builder_v1"
DASHBOARD_STATIC_PAGE_SCHEMA_VERSION = "daily_report_dashboard_static_page_v1"
CONTRACT_NAME = "dashboard_delivery_gate"
CONTRACT_VERSION = "v1"
ADVISORY_DISCLAIMER = (
    "This dashboard delivery gate is repo-only fixture output for preview review. "
    "It is advisory-only and does not authorize dashboard deployment, API server "
    "creation, email, LINE, SMTP, Gmail API, trading, portfolio action, or external "
    "system mutation."
)
SIDE_EFFECTS = {
    "read_secrets": False,
    "called_external_model_runtime": False,
    "called_market_data_runtime": False,
    "sent_notification": False,
    "sent_email": False,
    "sent_line_push": False,
    "called_smtp": False,
    "called_gmail_api": False,
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
    "no_dashboard_deploy": True,
    "no_api_server_created": True,
    "no_email_send": True,
    "no_line_push": True,
    "no_smtp_call": True,
    "no_gmail_api_call": True,
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


def source_summary(source_path: Path, source: dict[str, Any], expected_schema: str) -> dict[str, Any]:
    return {
        "source_path": str(source_path),
        "source_schema_expected": expected_schema,
        "source_schema_version": source.get("schema_version"),
        "source_schema_matched": source.get("schema_version") == expected_schema,
        "source_task_id": source.get("task_id"),
        "source_run_id": source.get("run_id"),
        "source_generated_at": source.get("generated_at"),
        "source_mode": source.get("mode"),
        "source_ok": source.get("ok") is True,
        "source_decision": source.get("decision"),
    }


def approval_gate(delivery_payload: dict[str, Any], input_policy: dict[str, Any]) -> dict[str, Any]:
    review_status = str(delivery_payload.get("review_status") or "unknown")
    delivery_allowed = delivery_payload.get("delivery_allowed") is True and review_status == "approved"
    return {
        "gate_id": "dashboard_delivery_gate_approval_gate_v1",
        "required_review_status": input_policy.get("required_review_status", "approved"),
        "current_review_status": review_status,
        "source_gate_id": as_dict(delivery_payload.get("approval_gate")).get("gate_id"),
        "source_gate_open": as_dict(delivery_payload.get("approval_gate")).get("gate_open") is True,
        "delivery_allowed": delivery_allowed,
        "gate_open": delivery_allowed,
        "reason": "Dashboard delivery remains blocked until review_status is approved and delivery_allowed is true."
        if not delivery_allowed
        else "Dashboard delivery gate is open by approved review status and delivery_allowed policy.",
    }


def static_page_summary(static_page: dict[str, Any]) -> dict[str, Any]:
    dashboard_page = as_dict(static_page.get("dashboard_page"))
    metrics = as_dict(static_page.get("overview_metrics"))
    return {
        "page_id": dashboard_page.get("page_id"),
        "page_title": dashboard_page.get("page_title"),
        "latest_preview_card_ref": dashboard_page.get("latest_preview_card_ref"),
        "preview_card_count": metrics.get("preview_card_count"),
        "warning_badge_count": metrics.get("warning_badge_count"),
        "requires_human_review_count": metrics.get("requires_human_review_count"),
        "manifest_ref": dashboard_page.get("manifest_ref"),
        "markdown_ref": dashboard_page.get("markdown_ref"),
        "renderer_source_ref": dashboard_page.get("renderer_source_ref"),
    }


def publish_target_policy(policy: dict[str, Any], delivery_allowed: bool) -> dict[str, Any]:
    return {
        "policy_id": policy.get("policy_id", "dashboard_delivery_publish_target_policy_v1"),
        "allowed_targets": deepcopy(as_list(policy.get("allowed_targets")) or ["private_dashboard_preview"]),
        "blocked_targets": deepcopy(
            as_list(policy.get("blocked_targets"))
            or ["public_dashboard", "production_dashboard", "api_server", "email", "line", "smtp", "gmail_api"]
        ),
        "requires_approval_gate": True,
        "requires_delivery_allowed": True,
        "requires_review_status": policy.get("required_review_status", "approved"),
        "fixture_mode_publish_status": "not_published",
        "delivery_allowed": delivery_allowed,
        "deployment_permitted": False,
    }


def publish_preview(gate: dict[str, Any], static_page: dict[str, Any], delivery_allowed: bool) -> dict[str, Any]:
    page = as_dict(static_page.get("dashboard_page"))
    return {
        "preview_id": gate.get("preview_id"),
        "dashboard_page_ref": gate.get("dashboard_page_ref"),
        "page_id": page.get("page_id"),
        "page_title": page.get("page_title"),
        "manifest_ref": page.get("manifest_ref"),
        "markdown_ref": page.get("markdown_ref"),
        "renderer_source_ref": page.get("renderer_source_ref"),
        "preview_only": True,
        "delivery_allowed": delivery_allowed,
        "publish_action_performed": False,
        "publish_status": "not_published",
    }


def delivery_blockers(
    delivery_payload: dict[str, Any],
    static_page: dict[str, Any],
    delivery_allowed: bool,
    dashboard_channel_enabled: bool,
) -> list[str]:
    blockers = list(dict.fromkeys(str(item) for item in as_list(delivery_payload.get("delivery_blockers"))))
    if delivery_payload.get("review_status") != "approved":
        blockers.append("review_status_not_approved")
    if not delivery_allowed:
        blockers.append("dashboard_delivery_gate_closed")
    if dashboard_channel_enabled is not True:
        blockers.append("dashboard_channel_disabled")
    if static_page.get("ok") is not True:
        blockers.append("dashboard_static_page_not_ok")
    if as_dict(static_page.get("overview_metrics")).get("requires_human_review_count", 0):
        blockers.append("dashboard_static_page_requires_human_review")
    return sorted(dict.fromkeys(blockers))


def warning_badges(delivery_payload: dict[str, Any], static_page: dict[str, Any]) -> list[dict[str, Any]]:
    badges: list[dict[str, Any]] = []
    for badge in as_list(delivery_payload.get("warning_badges")):
        if isinstance(badge, dict):
            badges.append(
                {
                    "badge_id": badge.get("badge_id"),
                    "source": "delivery_payload",
                    "label": badge.get("label"),
                    "severity": badge.get("severity", "warning"),
                }
            )
    for badge in as_list(static_page.get("warning_badges")):
        if isinstance(badge, dict):
            badges.append(
                {
                    "badge_id": badge.get("badge_id"),
                    "source": "dashboard_static_page",
                    "label": badge.get("label"),
                    "severity": badge.get("severity", "warning"),
                }
            )
    return sorted(badges, key=lambda item: (str(item.get("source")), str(item.get("badge_id"))))


def build_dashboard_delivery_gate(data: dict[str, Any], payload_result: dict[str, Any], static_page: dict[str, Any]) -> dict[str, Any]:
    delivery_payload = as_dict(payload_result.get("delivery_payload"))
    policy = as_dict(data.get("publish_target_policy"))
    gate = {
        "dashboard_delivery_id": f"dashboard_delivery_gate_{delivery_payload.get('report_date', 'unknown')}",
        "payload_id": delivery_payload.get("payload_id"),
        "preview_id": delivery_payload.get("preview_id"),
        "report_date": delivery_payload.get("report_date"),
        "review_id": delivery_payload.get("review_id"),
        "review_status": delivery_payload.get("review_status"),
        "approval_gate": {},
        "delivery_allowed": False,
        "dashboard_channel_enabled": False,
        "preview_only": True,
        "dashboard_page_ref": as_dict(static_page.get("dashboard_page")).get("page_id"),
        "static_page_summary": static_page_summary(static_page),
        "publish_target_policy": {},
        "publish_preview": {},
        "delivery_blockers": [],
        "warning_badges": [],
        "human_review_required": True,
        "advisory_disclaimer": ADVISORY_DISCLAIMER,
        "publish_intent": data.get("publish_intent", "preview_contract_only"),
        "publish_status": "not_published",
    }
    gate["approval_gate"] = approval_gate(delivery_payload, policy)
    gate["delivery_allowed"] = gate["approval_gate"]["delivery_allowed"]
    gate["dashboard_channel_enabled"] = False
    gate["publish_target_policy"] = publish_target_policy(policy, gate["delivery_allowed"])
    gate["publish_preview"] = publish_preview(gate, static_page, gate["delivery_allowed"])
    gate["warning_badges"] = warning_badges(delivery_payload, static_page)
    gate["human_review_required"] = (
        delivery_payload.get("human_review_required") is True
        or as_dict(static_page.get("overview_metrics")).get("requires_human_review_count", 0) > 0
        or not gate["delivery_allowed"]
    )
    gate["delivery_blockers"] = delivery_blockers(
        delivery_payload,
        static_page,
        gate["delivery_allowed"],
        gate["dashboard_channel_enabled"],
    )
    return gate


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    gate = as_dict(result.get("dashboard_delivery_gate"))
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "dashboard_delivery_id": gate.get("dashboard_delivery_id"),
        "payload_id": gate.get("payload_id"),
        "preview_id": gate.get("preview_id"),
        "report_date": gate.get("report_date"),
        "review_id": gate.get("review_id"),
        "review_status": gate.get("review_status"),
        "delivery_allowed": gate.get("delivery_allowed"),
        "dashboard_channel_enabled": gate.get("dashboard_channel_enabled"),
        "publish_status": gate.get("publish_status"),
        "publish_intent": gate.get("publish_intent"),
        "warning_badge_count": len(as_list(gate.get("warning_badges"))),
        "delivery_blocker_count": len(as_list(gate.get("delivery_blockers"))),
        "human_review_required": gate.get("human_review_required"),
        "deterministic_output": as_dict(result.get("validation_summary")).get("deterministic_output"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "safety": deepcopy(result.get("safety")),
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    sources = as_dict(data.get("input_sources"))
    payload_path = repo_path(sources.get("delivery_payload_builder_result_path"))
    static_page_path = repo_path(sources.get("dashboard_static_page_result_path"))
    payload_result = load_json(payload_path)
    static_page = load_json(static_page_path)
    gate = build_dashboard_delivery_gate(data, payload_result, static_page)
    validation_summary = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "preview_only": True,
        "advisory_only": True,
        "delivery_payload_source": source_summary(payload_path, payload_result, DELIVERY_PAYLOAD_SCHEMA_VERSION),
        "dashboard_static_page_source": source_summary(static_page_path, static_page, DASHBOARD_STATIC_PAGE_SCHEMA_VERSION),
        "approval_gate_required": True,
        "approval_gate_open": gate["approval_gate"]["gate_open"],
        "delivery_allowed_policy_enforced": gate["delivery_allowed"] is (gate["review_status"] == "approved"),
        "dashboard_channel_policy_enforced": gate["dashboard_channel_enabled"] is False
        or (gate["delivery_allowed"] is True and gate["review_status"] == "approved"),
        "publish_status_not_published": gate["publish_status"] == "not_published",
        "no_publish_action_performed": as_dict(gate.get("publish_preview")).get("publish_action_performed") is False,
        "warning_count": len(as_list(gate.get("warning_badges"))),
        "delivery_blocker_count": len(as_list(gate.get("delivery_blockers"))),
        "warnings": [str(item.get("label")) for item in as_list(gate.get("warning_badges")) if isinstance(item, dict)],
    }
    ok = (
        as_dict(validation_summary["delivery_payload_source"]).get("source_schema_matched") is True
        and as_dict(validation_summary["delivery_payload_source"]).get("source_ok") is True
        and as_dict(validation_summary["dashboard_static_page_source"]).get("source_schema_matched") is True
        and as_dict(validation_summary["dashboard_static_page_source"]).get("source_ok") is True
        and validation_summary["delivery_allowed_policy_enforced"]
        and validation_summary["dashboard_channel_policy_enforced"]
        and validation_summary["publish_status_not_published"]
        and validation_summary["no_publish_action_performed"]
        and all(value is False for value in SIDE_EFFECTS.values())
    )
    if not ok:
        decision = "validation_failed"
    elif not gate["delivery_allowed"]:
        decision = "dashboard_delivery_blocked_pending_approval"
    elif validation_summary["warning_count"] > 0:
        decision = "dashboard_delivery_gate_contract_completed_with_warnings"
    else:
        decision = "dashboard_delivery_gate_contract_completed"
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-096"),
        "run_id": data.get("run_id", "dashboard-delivery-gate-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "dashboard_delivery_gate": gate,
        "dashboard_delivery_summary": {},
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision,
        "next_recommendation": "Keep dashboard publication blocked until review_status is approved and delivery_allowed is true; do not deploy, serve, send, or persist this fixture.",
    }
    result["dashboard_delivery_summary"] = build_summary(result)
    return result


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Dashboard Delivery Gate V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["dashboard_delivery_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
