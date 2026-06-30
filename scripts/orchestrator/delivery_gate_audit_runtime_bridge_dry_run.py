#!/usr/bin/env python3
"""Build deterministic Delivery Gate Audit + Runtime Bridge V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/delivery_gate_audit_runtime_bridge_input.example.json")
SCHEMA_VERSION = "delivery_gate_audit_runtime_bridge_v1"
SUMMARY_SCHEMA_VERSION = "delivery_gate_audit_runtime_bridge_summary_v1"
CONTRACT_NAME = "delivery_gate_audit_runtime_bridge"
CONTRACT_VERSION = "v1"
CHANNELS = ["email", "line", "dashboard"]
SOURCE_SCHEMAS = {
    "unified": "unified_delivery_gate_summary_v1",
    "email": "controlled_email_delivery_contract_v1",
    "line": "line_delivery_gate_contract_v1",
    "dashboard": "dashboard_delivery_gate_v1",
}
SOURCE_KEYS = {
    "email": "controlled_email_delivery",
    "line": "line_delivery_gate",
    "dashboard": "dashboard_delivery_gate",
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
RUNTIME_ACTIONS = {
    "email": "email_send",
    "line": "line_push",
    "dashboard": "dashboard_publish",
}
DRY_RUN_ENTRYPOINTS = {
    "email": "scripts/orchestrator/controlled_email_delivery_dry_run.py",
    "line": "scripts/orchestrator/line_delivery_gate_dry_run.py",
    "dashboard": "scripts/orchestrator/dashboard_delivery_gate_dry_run.py",
}
ADVISORY_DISCLAIMER = (
    "This delivery gate audit runtime bridge is repo-only fixture output for preview review. "
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
    "external_side_effects_allowed": False,
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
    "external_side_effects_allowed": False,
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
    expected = SOURCE_SCHEMAS[channel]
    return {
        "channel": channel,
        "source_path": str(path),
        "source_schema_expected": expected,
        "source_schema_version": source.get("schema_version"),
        "source_schema_matched": source.get("schema_version") == expected,
        "source_task_id": source.get("task_id"),
        "source_run_id": source.get("run_id"),
        "source_generated_at": source.get("generated_at"),
        "source_mode": source.get("mode"),
        "source_ok": source.get("ok") is True,
        "source_decision": source.get("decision"),
    }


def channel_gate(channel: str, source: dict[str, Any]) -> dict[str, Any]:
    return as_dict(source.get(SOURCE_KEYS[channel]))


def channel_audit_entry(channel: str, path: Path, source: dict[str, Any], unified_status: dict[str, Any]) -> dict[str, Any]:
    gate = channel_gate(channel, source)
    approval_gate = as_dict(gate.get("approval_gate"))
    source_info = source_summary(channel, path, source)
    delivery_allowed = gate.get("delivery_allowed") is True
    channel_enabled = gate.get(CHANNEL_ENABLED_KEYS[channel]) is True
    gate_open = approval_gate.get("gate_open") is True
    source_ready = (
        source_info["source_schema_matched"]
        and source_info["source_ok"]
        and gate.get("review_status") == "approved"
        and delivery_allowed
        and channel_enabled
        and gate_open
    )
    blockers = [str(item) for item in as_list(gate.get("delivery_blockers")) if str(item).strip()]
    blockers.extend(str(item) for item in as_list(unified_status.get("delivery_blockers")) if str(item).strip())
    if not source_info["source_schema_matched"]:
        blockers.append("source_schema_mismatch")
    if not source_info["source_ok"]:
        blockers.append("source_result_not_ok")
    if gate.get("review_status") != "approved":
        blockers.append("review_status_not_approved")
    if not delivery_allowed:
        blockers.append("delivery_not_allowed")
    if not channel_enabled:
        blockers.append(f"{channel}_channel_disabled")
    if not gate_open:
        blockers.append("approval_gate_closed")
    blockers.append("runtime_bridge_external_side_effects_disabled")
    return {
        "channel": channel,
        "source": source_info,
        "review_status": gate.get("review_status"),
        "approval_gate_open": gate_open,
        "delivery_allowed": delivery_allowed,
        "channel_enabled": channel_enabled,
        "action_status": gate.get(ACTION_STATUS_KEYS[channel]),
        "unified_status": unified_status.get("status"),
        "runtime_bridge_status": "ready_for_gated_dry_run" if source_ready else "blocked",
        "ready_for_runtime_bridge": source_ready,
        "blocked": not source_ready,
        "blockers": sorted(set(blockers)),
        "warning_badge_count": len(as_list(gate.get("warning_badges"))),
        "human_review_required": gate.get("human_review_required") is True or not source_ready,
    }


def build_audit_log(
    unified: dict[str, Any],
    sources: dict[str, tuple[Path, dict[str, Any]]],
) -> dict[str, Any]:
    unified_summary = as_dict(unified.get("unified_delivery_gate_summary"))
    unified_statuses = as_dict(unified_summary.get("channel_statuses"))
    entries = {
        channel: channel_audit_entry(channel, path, source, as_dict(unified_statuses.get(channel)))
        for channel, (path, source) in sources.items()
    }
    blocked_channels = [channel for channel in CHANNELS if entries[channel]["blocked"]]
    ready_channels = [channel for channel in CHANNELS if not entries[channel]["blocked"]]
    delivery_allowed = unified_summary.get("delivery_allowed") is True and not blocked_channels
    final_decision = unified_summary.get("final_delivery_decision")
    return {
        "audit_id": f"delivery_gate_audit_{slug(unified_summary.get('report_date'))}",
        "report_date": unified_summary.get("report_date"),
        "payload_id": unified_summary.get("payload_id"),
        "review_id": unified_summary.get("review_id"),
        "review_status": unified_summary.get("review_status"),
        "approval_gate": deepcopy(unified_summary.get("approval_gate")),
        "delivery_allowed": delivery_allowed,
        "final_delivery_decision": final_decision,
        "channel_audit_entries": {channel: entries[channel] for channel in CHANNELS},
        "blocked_channels": blocked_channels,
        "ready_channels": ready_channels,
        "human_review_required": bool(blocked_channels) or unified_summary.get("human_review_required") is True,
        "audit_decision": "blocked_pending_approval" if blocked_channels else "ready_for_gated_runtime_preview",
        "audit_notes": [
            "Repo-only fixture audit; no runtime delivery action is authorized.",
            "Runtime bridge remains dry-run and gated; external side effects are disabled.",
            ADVISORY_DISCLAIMER,
        ],
    }


def channel_bridge_spec(channel: str, audit_entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "channel": channel,
        "bridge_status": "enabled_for_dry_run_only" if audit_entry.get("ready_for_runtime_bridge") else "blocked",
        "allowed_runtime_action": None,
        "blocked_runtime_action": RUNTIME_ACTIONS[channel],
        "dry_run_entrypoint": DRY_RUN_ENTRYPOINTS[channel],
        "requires_delivery_allowed": True,
        "requires_approval_gate_open": True,
        "requires_review_status": "approved",
        "requires_runtime_flag": f"ENABLE_{channel.upper()}_DELIVERY_DRY_RUN",
        "requires_approval_fields": ["review_id", "review_status", "delivery_allowed", "approval_gate.gate_open"],
        "source_action_status": audit_entry.get("action_status"),
        "external_side_effects_allowed": False,
        "guards": [
            "dry_run_only",
            "approval_gate_required",
            "fixture_input_required",
            "no_external_delivery_action",
        ],
    }


def build_runtime_bridge_plan(audit_log: dict[str, Any]) -> dict[str, Any]:
    entries = as_dict(audit_log.get("channel_audit_entries"))
    channel_specs = {channel: channel_bridge_spec(channel, as_dict(entries.get(channel))) for channel in CHANNELS}
    return {
        "bridge_id": f"runtime_bridge_{slug(audit_log.get('report_date'))}",
        "bridge_mode": "dry_run_gated_preview_only",
        "allowed_channels": deepcopy(audit_log.get("ready_channels")),
        "blocked_channels": deepcopy(audit_log.get("blocked_channels")),
        "runtime_preconditions": [
            "repo_fixture_result_validated",
            "all_channel_approval_gates_open",
            "review_status_approved",
            "delivery_allowed_true",
            "runtime_flags_explicitly_enabled_for_dry_run",
            "external_side_effects_allowed_false",
        ],
        "channel_bridge_specs": channel_specs,
        "dry_run_entrypoints": deepcopy(DRY_RUN_ENTRYPOINTS),
        "required_runtime_flags": [
            "DELIVERY_GATE_RUNTIME_BRIDGE_DRY_RUN_ONLY=true",
            "DELIVERY_GATE_RUNTIME_BRIDGE_REQUIRE_APPROVAL=true",
            "DELIVERY_GATE_RUNTIME_BRIDGE_EXTERNAL_SIDE_EFFECTS=false",
        ],
        "required_approval_fields": ["review_id", "review_status", "delivery_allowed", "approval_gate.gate_open"],
        "safety_guards": [
            "repo_only",
            "fixture_only",
            "preview_only",
            "advisory_only",
            "no_email_send",
            "no_line_push",
            "no_dashboard_deploy",
            "no_smtp_call",
            "no_gmail_api_call",
            "no_api_server_created",
            "no_persistent_store_writes",
            "no_schedule_service_changes",
        ],
        "external_side_effects_allowed": False,
    }


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    audit = as_dict(result.get("delivery_gate_audit_log"))
    bridge = as_dict(result.get("runtime_bridge_plan"))
    validation = as_dict(result.get("validation_summary"))
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "audit_id": audit.get("audit_id"),
        "bridge_id": bridge.get("bridge_id"),
        "report_date": audit.get("report_date"),
        "payload_id": audit.get("payload_id"),
        "review_id": audit.get("review_id"),
        "review_status": audit.get("review_status"),
        "delivery_allowed": audit.get("delivery_allowed"),
        "final_delivery_decision": audit.get("final_delivery_decision"),
        "audit_decision": audit.get("audit_decision"),
        "bridge_mode": bridge.get("bridge_mode"),
        "blocked_channels": deepcopy(audit.get("blocked_channels")),
        "ready_channels": deepcopy(audit.get("ready_channels")),
        "blocked_channel_count": len(as_list(audit.get("blocked_channels"))),
        "ready_channel_count": len(as_list(audit.get("ready_channels"))),
        "human_review_required": audit.get("human_review_required"),
        "external_side_effects_allowed": bridge.get("external_side_effects_allowed"),
        "deterministic_output": validation.get("deterministic_output"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "safety": deepcopy(result.get("safety")),
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    input_sources = as_dict(data.get("input_sources"))
    unified_path = repo_path(input_sources.get("unified_delivery_gate_summary_result_path"))
    channel_paths = {
        "email": repo_path(input_sources.get("email_delivery_result_path")),
        "line": repo_path(input_sources.get("line_delivery_gate_result_path")),
        "dashboard": repo_path(input_sources.get("dashboard_delivery_gate_result_path")),
    }
    unified = load_json(unified_path)
    sources = {channel: (path, load_json(path)) for channel, path in channel_paths.items()}
    audit_log = build_audit_log(unified, sources)
    bridge_plan = build_runtime_bridge_plan(audit_log)
    source_summaries = {"unified": source_summary("unified", unified_path, unified)}
    source_summaries.update(
        {channel: source_summary(channel, path, source) for channel, (path, source) in sources.items()}
    )
    channel_entries = as_dict(audit_log.get("channel_audit_entries"))
    validation_summary = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "preview_only": True,
        "advisory_only": True,
        "source_summaries": source_summaries,
        "required_channels_present": list(channel_entries.keys()) == CHANNELS,
        "source_schemas_matched": all(source_summaries[key]["source_schema_matched"] for key in source_summaries),
        "source_results_ok": all(source_summaries[key]["source_ok"] for key in source_summaries),
        "approval_gate_required": True,
        "delivery_allowed_policy_enforced": audit_log["delivery_allowed"] is (len(audit_log["blocked_channels"]) == 0),
        "runtime_bridge_dry_run_only": bridge_plan["bridge_mode"] == "dry_run_gated_preview_only",
        "runtime_entrypoints_dry_run_only": all("dry_run" in value for value in bridge_plan["dry_run_entrypoints"].values()),
        "external_side_effects_allowed": False,
        "no_delivery_actions": True,
        "blocked_channel_count": len(as_list(audit_log.get("blocked_channels"))),
        "ready_channel_count": len(as_list(audit_log.get("ready_channels"))),
        "warning_count": sum(as_dict(channel_entries.get(channel)).get("warning_badge_count", 0) for channel in CHANNELS),
        "human_review_required": audit_log.get("human_review_required") is True,
    }
    ok = (
        validation_summary["required_channels_present"]
        and validation_summary["source_schemas_matched"]
        and validation_summary["source_results_ok"]
        and validation_summary["delivery_allowed_policy_enforced"]
        and validation_summary["runtime_bridge_dry_run_only"]
        and validation_summary["runtime_entrypoints_dry_run_only"]
        and bridge_plan["external_side_effects_allowed"] is False
        and all(value is False for value in SIDE_EFFECTS.values())
    )
    if not ok:
        decision = "validation_failed"
    elif audit_log["blocked_channels"] or audit_log["human_review_required"]:
        decision = "delivery_gate_runtime_bridge_blocked_pending_approval"
    elif validation_summary["warning_count"] > 0:
        decision = "delivery_gate_audit_runtime_bridge_completed_with_warnings"
    else:
        decision = "delivery_gate_audit_runtime_bridge_completed"
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-098"),
        "run_id": data.get("run_id", "delivery-gate-audit-runtime-bridge-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "delivery_gate_audit_log": audit_log,
        "runtime_bridge_plan": bridge_plan,
        "delivery_gate_audit_runtime_bridge_summary": {},
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision,
        "next_recommendation": "Keep runtime bridge blocked pending approval; do not send, push, deploy, serve, schedule, persist, or mutate external systems from this fixture.",
    }
    result["delivery_gate_audit_runtime_bridge_summary"] = build_summary(result)
    return result


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Delivery Gate Audit + Runtime Bridge V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["delivery_gate_audit_runtime_bridge_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
