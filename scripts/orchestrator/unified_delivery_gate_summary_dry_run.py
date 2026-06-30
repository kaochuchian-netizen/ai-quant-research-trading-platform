#!/usr/bin/env python3
"""Build deterministic Unified Delivery Gate Summary V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/unified_delivery_gate_summary_input.example.json")
SCHEMA_VERSION = "unified_delivery_gate_summary_v1"
SUMMARY_SCHEMA_VERSION = "unified_delivery_gate_summary_only_v1"
CONTRACT_NAME = "unified_delivery_gate_summary"
CONTRACT_VERSION = "v1"
CHANNELS = ["email", "line", "dashboard"]
SOURCE_SCHEMAS = {
    "email": "controlled_email_delivery_contract_v1",
    "line": "line_delivery_gate_contract_v1",
    "dashboard": "dashboard_delivery_gate_v1",
}
SOURCE_KEYS = {
    "email": "controlled_email_delivery",
    "line": "line_delivery_gate",
    "dashboard": "dashboard_delivery_gate",
}
SOURCE_PATH_KEYS = {
    "email": "email_delivery_result_path",
    "line": "line_delivery_gate_result_path",
    "dashboard": "dashboard_delivery_gate_result_path",
}
CHANNEL_ENABLED_KEYS = {
    "email": "email_channel_enabled",
    "line": "line_channel_enabled",
    "dashboard": "dashboard_channel_enabled",
}
ACTION_STATUS_KEYS = {
    "email": "send_status",
    "line": "push_status",
    "dashboard": "publish_status",
}
ADVISORY_DISCLAIMER = (
    "This unified delivery gate summary is repo-only fixture output for preview review. "
    "It is advisory-only and does not authorize email sending, LINE push, dashboard "
    "deployment, API server creation, SMTP, Gmail API, model runtime, market data, "
    "portfolio action, or external system mutation."
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
    "no_email_send": True,
    "no_line_push": True,
    "no_dashboard_deploy": True,
    "no_smtp_call": True,
    "no_gmail_api_call": True,
    "no_api_server_created": True,
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


def source_summary(channel: str, path: Path, source: dict[str, Any]) -> dict[str, Any]:
    return {
        "channel": channel,
        "source_path": str(path),
        "source_schema_expected": SOURCE_SCHEMAS[channel],
        "source_schema_version": source.get("schema_version"),
        "source_schema_matched": source.get("schema_version") == SOURCE_SCHEMAS[channel],
        "source_task_id": source.get("task_id"),
        "source_run_id": source.get("run_id"),
        "source_generated_at": source.get("generated_at"),
        "source_mode": source.get("mode"),
        "source_ok": source.get("ok") is True,
        "source_decision": source.get("decision"),
    }


def warning_badges(channel: str, source_gate: dict[str, Any]) -> list[dict[str, Any]]:
    badges: list[dict[str, Any]] = []
    for badge in as_list(source_gate.get("warning_badges")):
        if not isinstance(badge, dict):
            continue
        badges.append(
            {
                "channel": channel,
                "badge_id": badge.get("badge_id"),
                "source": badge.get("source"),
                "label": badge.get("label"),
                "severity": badge.get("severity", "warning"),
            }
        )
    return sorted(badges, key=lambda item: (str(item.get("channel")), str(item.get("source")), str(item.get("badge_id"))))


def channel_status(channel: str, path: Path, source: dict[str, Any]) -> dict[str, Any]:
    gate = as_dict(source.get(SOURCE_KEYS[channel]))
    approval_gate = as_dict(gate.get("approval_gate"))
    review_status = gate.get("review_status")
    delivery_allowed = gate.get("delivery_allowed") is True
    channel_enabled = gate.get(CHANNEL_ENABLED_KEYS[channel]) is True
    source_ok = source.get("ok") is True
    source_schema_matched = source.get("schema_version") == SOURCE_SCHEMAS[channel]
    approved_and_enabled = (
        source_ok
        and source_schema_matched
        and review_status == "approved"
        and delivery_allowed
        and channel_enabled
        and approval_gate.get("gate_open") is True
    )
    blockers = [str(item) for item in as_list(gate.get("delivery_blockers")) if str(item).strip()]
    if not source_schema_matched:
        blockers.append("source_schema_mismatch")
    if not source_ok:
        blockers.append("source_result_not_ok")
    if review_status != "approved":
        blockers.append("review_status_not_approved")
    if not delivery_allowed:
        blockers.append("delivery_not_allowed")
    if not channel_enabled:
        blockers.append(f"{channel}_channel_disabled")
    if approval_gate.get("gate_open") is not True:
        blockers.append("source_approval_gate_closed")
    blockers = sorted(set(blockers))
    return {
        "channel": channel,
        "source": source_summary(channel, path, source),
        "status": "ready" if approved_and_enabled else "blocked",
        "review_status": review_status,
        "approval_gate_open": approval_gate.get("gate_open") is True,
        "delivery_allowed": delivery_allowed,
        "channel_enabled": channel_enabled,
        "approved_and_enabled": approved_and_enabled,
        "blocked": not approved_and_enabled,
        "delivery_blockers": blockers,
        "warning_badge_count": len(as_list(gate.get("warning_badges"))),
        "human_review_required": gate.get("human_review_required") is True or not approved_and_enabled,
        "action_status": gate.get(ACTION_STATUS_KEYS[channel]),
    }


def build_approval_gate(statuses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    approved_channels = [channel for channel in CHANNELS if statuses[channel]["approved_and_enabled"]]
    blocked_channels = [channel for channel in CHANNELS if statuses[channel]["blocked"]]
    gate_open = len(approved_channels) == len(CHANNELS)
    return {
        "gate_id": "unified_delivery_gate_summary_approval_gate_v1",
        "required_review_status": "approved",
        "required_channels": deepcopy(CHANNELS),
        "approved_and_enabled_channels": approved_channels,
        "blocked_channels": blocked_channels,
        "all_source_gates_approved_and_enabled": gate_open,
        "delivery_allowed": gate_open,
        "gate_open": gate_open,
        "approval_required": True,
        "reason": "Unified delivery remains blocked until email, LINE, and dashboard gates are approved and enabled."
        if not gate_open
        else "All source gates are approved and enabled; this fixture still performs no delivery action.",
    }


def aggregate_blockers(statuses: dict[str, dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for channel in CHANNELS:
        for blocker in as_list(statuses[channel].get("delivery_blockers")):
            blockers.append(f"{channel}:{blocker}")
    blockers.append("fixture_mode_no_delivery_actions")
    return sorted(set(blockers))


def final_delivery_decision(blocked_channels: list[str], warning_count: int) -> str:
    if blocked_channels:
        return "blocked_pending_approval"
    if warning_count:
        return "approved_with_warnings_preview_only"
    return "approved_preview_only"


def build_unified_summary(data: dict[str, Any], sources: dict[str, tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    statuses = {channel: channel_status(channel, path, source) for channel, (path, source) in sources.items()}
    blocked_channels = [channel for channel in CHANNELS if statuses[channel]["blocked"]]
    ready_channels = [channel for channel in CHANNELS if not statuses[channel]["blocked"]]
    warnings: list[dict[str, Any]] = []
    for channel, (_, source) in sources.items():
        warnings.extend(warning_badges(channel, as_dict(source.get(SOURCE_KEYS[channel]))))
    warnings = sorted(warnings, key=lambda item: (str(item.get("channel")), str(item.get("source")), str(item.get("badge_id"))))
    first_gate = as_dict(sources["email"][1].get(SOURCE_KEYS["email"]))
    approval = build_approval_gate(statuses)
    return {
        "summary_id": f"unified_delivery_gate_summary_{slug(first_gate.get('report_date'))}",
        "report_date": first_gate.get("report_date"),
        "payload_id": first_gate.get("payload_id"),
        "review_id": first_gate.get("review_id"),
        "review_status": "approved" if approval["gate_open"] else "pending_approval",
        "approval_gate": approval,
        "delivery_allowed": approval["gate_open"],
        "channels": deepcopy(CHANNELS),
        "channel_statuses": {channel: statuses[channel] for channel in CHANNELS},
        "blocked_channels": blocked_channels,
        "ready_channels": ready_channels,
        "delivery_blockers": aggregate_blockers(statuses),
        "warning_badges": warnings,
        "human_review_required": bool(blocked_channels) or bool(warnings),
        "advisory_disclaimer": ADVISORY_DISCLAIMER,
        "final_delivery_decision": final_delivery_decision(blocked_channels, len(warnings)),
    }


def build_delivery_readiness_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(result.get("unified_delivery_gate_summary"))
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "summary_id": summary.get("summary_id"),
        "report_date": summary.get("report_date"),
        "payload_id": summary.get("payload_id"),
        "review_id": summary.get("review_id"),
        "review_status": summary.get("review_status"),
        "delivery_allowed": summary.get("delivery_allowed"),
        "final_delivery_decision": summary.get("final_delivery_decision"),
        "blocked_channels": deepcopy(summary.get("blocked_channels")),
        "ready_channels": deepcopy(summary.get("ready_channels")),
        "channel_count": len(as_list(summary.get("channels"))),
        "blocked_channel_count": len(as_list(summary.get("blocked_channels"))),
        "ready_channel_count": len(as_list(summary.get("ready_channels"))),
        "delivery_blocker_count": len(as_list(summary.get("delivery_blockers"))),
        "warning_badge_count": len(as_list(summary.get("warning_badges"))),
        "human_review_required": summary.get("human_review_required"),
        "deterministic_output": as_dict(result.get("validation_summary")).get("deterministic_output"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "safety": deepcopy(result.get("safety")),
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    input_sources = as_dict(data.get("input_sources"))
    sources = {
        channel: (repo_path(input_sources.get(SOURCE_PATH_KEYS[channel])), None)
        for channel in CHANNELS
    }
    loaded_sources = {channel: (path, load_json(path)) for channel, (path, _) in sources.items()}
    unified = build_unified_summary(data, loaded_sources)
    statuses = as_dict(unified.get("channel_statuses"))
    source_summaries = {channel: statuses[channel]["source"] for channel in CHANNELS}
    delivery_allowed_policy_enforced = unified["delivery_allowed"] is all(
        statuses[channel]["approved_and_enabled"] is True for channel in CHANNELS
    )
    blocked_requires_pending = not unified["blocked_channels"] or unified["final_delivery_decision"] == "blocked_pending_approval"
    validation_summary = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "preview_only": True,
        "advisory_only": True,
        "source_summaries": source_summaries,
        "required_channels_present": list(statuses.keys()) == CHANNELS,
        "source_schemas_matched": all(source_summaries[channel]["source_schema_matched"] for channel in CHANNELS),
        "source_results_ok": all(source_summaries[channel]["source_ok"] for channel in CHANNELS),
        "approval_gate_required": True,
        "delivery_allowed_policy_enforced": delivery_allowed_policy_enforced,
        "blocked_requires_pending_approval": blocked_requires_pending,
        "no_delivery_actions": True,
        "warning_count": len(as_list(unified.get("warning_badges"))),
        "delivery_blocker_count": len(as_list(unified.get("delivery_blockers"))),
        "blocked_channel_count": len(as_list(unified.get("blocked_channels"))),
        "ready_channel_count": len(as_list(unified.get("ready_channels"))),
        "warnings": [str(item.get("label")) for item in as_list(unified.get("warning_badges")) if isinstance(item, dict)],
    }
    ok = (
        validation_summary["required_channels_present"]
        and validation_summary["source_schemas_matched"]
        and validation_summary["source_results_ok"]
        and validation_summary["delivery_allowed_policy_enforced"]
        and validation_summary["blocked_requires_pending_approval"]
        and all(value is False for value in SIDE_EFFECTS.values())
    )
    if not ok:
        decision = "validation_failed"
    elif unified["blocked_channels"]:
        decision = "unified_delivery_blocked_pending_approval"
    elif validation_summary["warning_count"] > 0:
        decision = "unified_delivery_gate_summary_completed_with_warnings"
    else:
        decision = "unified_delivery_gate_summary_completed"
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-097"),
        "run_id": data.get("run_id", "unified-delivery-gate-summary-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "unified_delivery_gate_summary": unified,
        "delivery_readiness_summary": {},
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision,
        "next_recommendation": "Keep unified delivery blocked until Email, LINE, and Dashboard gates are approved and enabled; do not send, push, deploy, serve, or persist this fixture.",
    }
    result["delivery_readiness_summary"] = build_delivery_readiness_summary(result)
    return result


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Unified Delivery Gate Summary V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["delivery_readiness_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
