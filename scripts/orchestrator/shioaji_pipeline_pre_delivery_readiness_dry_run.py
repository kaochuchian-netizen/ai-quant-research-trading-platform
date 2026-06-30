#!/usr/bin/env python3
"""Build repo-only Shioaji pipeline pre-delivery readiness repair V1 result."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/shioaji_pipeline_pre_delivery_readiness_input.example.json")
SCHEMA_VERSION = "shioaji_pipeline_pre_delivery_readiness_repair_v1"
SUMMARY_SCHEMA_VERSION = "shioaji_pipeline_pre_delivery_readiness_summary_v1"
TASK_ID = "AI-DEV-105"
DECISION_COMPLETED = "shioaji_pipeline_pre_delivery_readiness_repair_completed"
DECISION_WARNINGS = "shioaji_pipeline_pre_delivery_readiness_repair_completed_with_warnings"
DECISION_BLOCKED = "pipeline_pre_delivery_still_blocked"
DECISION_VALIDATION_FAILED = "validation_failed"
DECISION_BLOCKED_GENERIC = "blocked"
DECISIONS = {
    DECISION_COMPLETED,
    DECISION_WARNINGS,
    DECISION_BLOCKED,
    DECISION_VALIDATION_FAILED,
    DECISION_BLOCKED_GENERIC,
}
SAFETY = {
    "repo_only": True,
    "no_send": True,
    "diagnostic_and_repair_only": True,
    "no_line_push": True,
    "no_line_api_call": True,
    "no_email_send": True,
    "no_smtp_call": True,
    "no_gmail_api_call": True,
    "no_dashboard_deploy": True,
    "no_api_server_created": True,
    "no_secret_read": True,
    "no_secret_mutation": True,
    "no_persistent_store_writes": True,
    "no_portfolio_actions": True,
    "no_cron_modification": True,
    "no_systemd_modification": True,
    "no_timer_modification": True,
    "no_service_modification": True,
    "no_schedule_service_changes": True,
    "external_side_effects_allowed": False,
    "trading_instruction": False,
}
SIDE_EFFECTS = {
    "read_secrets": False,
    "mutated_secrets": False,
    "sent_line_push": False,
    "called_line_api": False,
    "sent_email": False,
    "called_smtp": False,
    "called_gmail_api": False,
    "deployed_dashboard": False,
    "created_api_server": False,
    "wrote_persistent_store": False,
    "placed_trade_order": False,
    "modified_portfolio": False,
    "modified_cron": False,
    "modified_systemd": False,
    "modified_timer": False,
    "modified_service": False,
    "modified_schedule_or_service": False,
    "called_market_data_runtime": False,
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("input JSON root must be an object")
    return payload


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stable_json(payload: Any, pretty: bool) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    return f"{text}\n" if pretty else text


def warning(code: str, message: str, severity: str = "warning", source: str = "readiness_dry_run") -> dict[str, str]:
    return {"code": code, "severity": severity, "source": source, "message": message}


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    readiness_input = as_dict(data.get("readiness_input"))
    simulated = as_dict(data.get("simulated_runtime"))
    safety = deepcopy(SAFETY)
    safety.update(as_dict(data.get("safety")))

    shioaji_login_ok = simulated.get("shioaji_login_ok") is True
    kbars_window_bounded = readiness_input.get("kbars_window_bounded") is True
    fallback_enabled = readiness_input.get("fallback_to_existing_csv") is True
    csv_inventory = as_list(readiness_input.get("historical_csv_inventory"))
    usable_csv = [item for item in csv_inventory if as_dict(item).get("usable") is True]
    requested_count = len(csv_inventory)
    usable_count = len(usable_csv)
    simulated_errors = [str(item) for item in as_list(simulated.get("errors")) if str(item).strip()]

    warnings: list[dict[str, str]] = []
    if not shioaji_login_ok:
        warnings.append(
            warning(
                "shioaji_login_or_runtime_unavailable",
                "Readiness repair keeps the pipeline report path available by using existing CSV fallback.",
                severity="error",
                source="shioaji_readiness",
            )
        )
    if simulated_errors:
        warnings.append(
            warning(
                "simulated_shioaji_runtime_errors_present",
                ", ".join(sorted(set(simulated_errors))),
                source="shioaji_readiness",
            )
        )
    if not kbars_window_bounded:
        warnings.append(
            warning(
                "kbars_window_not_bounded",
                "Kbars date range must be bounded before live Shioaji fetch.",
                severity="error",
                source="historical_data_readiness",
            )
        )
    if requested_count and usable_count < requested_count:
        warnings.append(
            warning(
                "partial_historical_csv_fallback_inventory",
                f"{usable_count}/{requested_count} configured CSV fallbacks are usable.",
                source="historical_data_readiness",
            )
        )

    shioaji_readiness = {
        "login_required_for_report_path": False,
        "login_ok": shioaji_login_ok,
        "error_classifications": sorted(set(simulated_errors)),
        "maintenance_or_version_failure_tolerated": fallback_enabled,
        "market_data_runtime_called": False,
    }
    historical_data_readiness = {
        "kbars_window_bounded": kbars_window_bounded,
        "bounded_kbars_window_days": int(readiness_input.get("bounded_kbars_window_days") or 30),
        "fallback_to_existing_csv": fallback_enabled,
        "requested_stock_count": requested_count,
        "usable_fallback_csv_count": usable_count,
        "report_ready_fallback_available": usable_count > 0,
        "persistent_store_writes": False,
    }
    report_ready = (
        kbars_window_bounded
        and fallback_enabled
        and (shioaji_login_ok or historical_data_readiness["report_ready_fallback_available"])
    )
    pipeline_pre_delivery_status = {
        "schema_version": "pipeline_pre_delivery_status_v1",
        "stage": "historical_csv_update",
        "crash_pipeline_on_shioaji_failure": False,
        "shioaji_required_for_delivery_stage": False,
        "report_ready_available": report_ready,
        "delivery_stage_reachable": report_ready,
        "status": "ready_with_fallback" if warnings else "ready",
        "blockers": [] if report_ready else ["no_shioaji_and_no_usable_historical_csv_fallback"],
    }
    fallback_policy = {
        "enabled": fallback_enabled,
        "source": "existing_historical_csv",
        "use_when": [
            "shioaji_login_failed",
            "shioaji_maintenance",
            "shioaji_version_or_upgrade_required",
            "shioaji_kbars_range_or_history_limit",
        ],
        "do_not_suppress_warnings": True,
        "preserve_existing_output_compatibility": True,
    }

    if not report_ready:
        decision = DECISION_BLOCKED
        ok = False
    elif warnings:
        decision = DECISION_WARNINGS
        ok = True
    else:
        decision = DECISION_COMPLETED
        ok = True

    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": data.get("run_id", "shioaji-readiness-repair-fixture-20260701"),
        "generated_at": data.get("generated_at", "2026-07-01T09:00:00+08:00"),
        "mode": data.get("mode", "fixture_dry_run_no_send"),
        "shioaji_readiness": shioaji_readiness,
        "historical_data_readiness": historical_data_readiness,
        "pipeline_pre_delivery_status": pipeline_pre_delivery_status,
        "fallback_policy": fallback_policy,
        "warnings": warnings,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": safety,
        "ok": ok,
        "decision": decision,
        "next_recommendation": (
            "Run the scheduled pipeline only through the approved production gate; Shioaji historical failures "
            "should now warn and fall back to existing CSV instead of crashing before delivery."
        ),
    }
    result["readiness_summary"] = build_summary(result)
    return result


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "delivery_stage_reachable": as_dict(result.get("pipeline_pre_delivery_status")).get("delivery_stage_reachable"),
        "report_ready_available": as_dict(result.get("pipeline_pre_delivery_status")).get("report_ready_available"),
        "usable_fallback_csv_count": as_dict(result.get("historical_data_readiness")).get("usable_fallback_csv_count"),
        "warning_count": len(as_list(result.get("warnings"))),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "safety": deepcopy(result.get("safety")),
    }


def write_json(payload: Any, output: Path, pretty: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(stable_json(payload, pretty), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Shioaji pre-delivery readiness repair V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    write_json(result, Path(args.output), args.pretty)
    write_json(result["readiness_summary"], Path(args.summary_output), args.pretty)
    print(stable_json(result, args.pretty), end="")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
