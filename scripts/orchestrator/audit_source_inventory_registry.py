#!/usr/bin/env python3
"""Read-only audit for the source inventory registry example.

This script reads the source inventory registry example and validates source
group separation, credential consistency, source-id uniqueness, and cost
governance metadata. It does not write files, call external services, modify
databases, send notifications, or run production workflows.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from source_inventory_registry_loader import (
    DEFAULT_REGISTRY_PATH,
    load_source_inventory_registry,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = DEFAULT_REGISTRY_PATH

ALLOWED_REGISTRY_STATUS = {"research_planning_only"}
ALLOWED_SOURCE_ROLES = {
    "data_source",
    "notification_output",
    "candidate_source",
}
ALLOWED_CONNECTION_STATES = {
    "connected",
    "notification_output",
    "candidate",
}
ALLOWED_COST_TIERS = {
    "free",
    "low",
    "variable",
    "internal",
    "unknown",
}
ALLOWED_SOURCE_CATEGORIES = {
    "sheet",
    "broker_api",
    "exchange_openapi",
    "news_rss",
    "llm_api",
    "market_data",
    "local_storage",
    "notification_push",
    "email_smtp",
    "market_data_candidate",
    "official_filing_candidate",
    "broker_data_candidate",
}

CONNECTED_SOURCE_IDS = {
    "google_sheet",
    "shioaji_sinopac",
    "twse_openapi",
    "google_news_rss",
    "gemini_google_generative_ai",
    "yfinance_yahoo",
    "sqlite_historical_csv",
}
NOTIFICATION_SOURCE_IDS = {
    "line_push",
    "smtp_email",
}
CANDIDATE_SOURCE_IDS = {
    "finmind",
    "mops_public_information_observatory",
    "eyuanta",
}
NOTIFICATION_CATEGORIES = {"notification_push", "email_smtp"}


def require_fields(payload: dict[str, Any], fields: list[str], *, label: str, reasons: list[str]) -> None:
    for field in fields:
        if field not in payload:
            reasons.append(f"{label}: missing field {field}")


def validate_source_group(
    items: Any,
    *,
    group_name: str,
    expected_role: str,
    expected_ids: set[str],
    reasons: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        reasons.append(f"{group_name} must be a list")
        return []

    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(items):
        label = f"{group_name}[{index}]"
        if not isinstance(item, dict):
            reasons.append(f"{label} must be an object")
            continue

        require_fields(
            item,
            [
                "source_id",
                "source_name",
                "source_category",
                "source_role",
                "connection_state",
                "credentials_required",
                "credential_fields",
                "env_vars",
                "cost_tier",
                "external_service",
                "read_only",
                "notes",
            ],
            label=label,
            reasons=reasons,
        )

        source_id = item.get("source_id")
        source_role = item.get("source_role")
        connection_state = item.get("connection_state")
        source_category = item.get("source_category")
        cost_tier = item.get("cost_tier")
        credential_fields = item.get("credential_fields")
        env_vars = item.get("env_vars")
        credentials_required = item.get("credentials_required")

        if not isinstance(source_id, str) or not source_id:
            reasons.append(f"{label}: source_id must be a non-empty string")
        elif source_id in seen_ids:
            reasons.append(f"{group_name}: duplicate source_id {source_id}")
        else:
            seen_ids.add(source_id)

        if source_role != expected_role:
            reasons.append(f"{label}: source_role must be {expected_role}")
        if connection_state not in ALLOWED_CONNECTION_STATES:
            reasons.append(f"{label}: invalid connection_state {connection_state!r}")
        if source_category not in ALLOWED_SOURCE_CATEGORIES:
            reasons.append(f"{label}: invalid source_category {source_category!r}")
        if cost_tier not in ALLOWED_COST_TIERS:
            reasons.append(f"{label}: invalid cost_tier {cost_tier!r}")
        if not isinstance(credentials_required, bool):
            reasons.append(f"{label}: credentials_required must be a boolean")
        if not isinstance(credential_fields, list):
            reasons.append(f"{label}: credential_fields must be a list")
        if not isinstance(env_vars, list):
            reasons.append(f"{label}: env_vars must be a list")

        if credentials_required and isinstance(credential_fields, list) and not credential_fields:
            reasons.append(f"{label}: credentials_required true requires credential_fields")
        if not credentials_required and isinstance(credential_fields, list) and credential_fields:
            reasons.append(f"{label}: credentials_required false requires empty credential_fields")
        if isinstance(credential_fields, list) and isinstance(env_vars, list):
            if credential_fields != env_vars:
                reasons.append(f"{label}: credential_fields must match env_vars")

        normalized.append(item)

    if seen_ids != expected_ids:
        missing = sorted(expected_ids - seen_ids)
        extra = sorted(seen_ids - expected_ids)
        if missing:
            reasons.append(f"{group_name}: missing source_ids: {', '.join(missing)}")
        if extra:
            reasons.append(f"{group_name}: unexpected source_ids: {', '.join(extra)}")

    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the source inventory registry example.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registry-path", default=str(REGISTRY_PATH))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    _ = repo_root  # Keep the argument accepted for parity with sibling tools.
    registry_path = Path(args.registry_path).resolve()

    reasons: list[str] = []
    warnings: list[str] = []

    try:
        registry = load_source_inventory_registry(registry_path)
    except Exception as exc:  # noqa: BLE001
        output = {
            "ok": False,
            "passed": False,
            "registry_path": str(registry_path),
            "reasons": [f"failed to load registry: {exc}"],
            "warnings": [],
            "side_effects": {
                "files_modified": False,
                "database_modified": False,
                "production_data_modified": False,
                "external_api_called": False,
                "notification_sent": False,
                "trading_execution_run": False,
                "production_pipeline_run": False,
                "scheduler_modified": False,
                "secrets_read_or_modified": False,
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))
        return 1

    require_fields(
        registry,
        [
            "schema_version",
            "registry_name",
            "inventory_scope",
            "production_status",
            "created_at",
            "updated_at",
            "governance_policy",
            "connected_sources",
            "notification_outputs",
            "candidate_sources",
            "summary",
            "notes",
        ],
        label="source_inventory_registry",
        reasons=reasons,
    )

    if registry.get("schema_version") != 1:
        reasons.append("schema_version must be 1")
    if registry.get("production_status") not in ALLOWED_REGISTRY_STATUS:
        reasons.append(f"invalid production_status {registry.get('production_status')!r}")

    governance_policy = registry.get("governance_policy")
    if not isinstance(governance_policy, dict):
        reasons.append("governance_policy must be an object")
        governance_policy = {}
    else:
        require_fields(
            governance_policy,
            [
                "dry_run_first",
                "read_only_audit_default",
                "db_mutation_disabled_by_default",
                "notification_delivery_disabled_by_default",
                "secrets_or_env_values_disallowed",
                "source_id_uniqueness_required",
                "notification_separation_required",
                "candidate_sources_must_remain_unconnected",
                "schema_compatibility_required",
                "audit_summary_required",
                "rollback_or_no_op_policy_required",
            ],
            label="governance_policy",
            reasons=reasons,
        )

    connected_sources = validate_source_group(
        registry.get("connected_sources"),
        group_name="connected_sources",
        expected_role="data_source",
        expected_ids=CONNECTED_SOURCE_IDS,
        reasons=reasons,
    )
    notification_outputs = validate_source_group(
        registry.get("notification_outputs"),
        group_name="notification_outputs",
        expected_role="notification_output",
        expected_ids=NOTIFICATION_SOURCE_IDS,
        reasons=reasons,
    )
    candidate_sources = validate_source_group(
        registry.get("candidate_sources"),
        group_name="candidate_sources",
        expected_role="candidate_source",
        expected_ids=CANDIDATE_SOURCE_IDS,
        reasons=reasons,
    )

    all_sources = connected_sources + notification_outputs + candidate_sources
    all_source_ids = [str(item.get("source_id")) for item in all_sources if isinstance(item.get("source_id"), str)]
    source_id_counts = Counter(all_source_ids)
    duplicate_ids = sorted(source_id for source_id, count in source_id_counts.items() if count > 1)
    if duplicate_ids:
        reasons.append(f"duplicate source_id(s) found: {', '.join(duplicate_ids)}")

    if governance_policy:
        if governance_policy.get("dry_run_first") is not True:
            reasons.append("governance_policy.dry_run_first must be true")
        if governance_policy.get("notification_separation_required") is not True:
            reasons.append("governance_policy.notification_separation_required must be true")
        if governance_policy.get("candidate_sources_must_remain_unconnected") is not True:
            reasons.append("governance_policy.candidate_sources_must_remain_unconnected must be true")

    source_lookup = {str(item.get("source_id")): item for item in all_sources if isinstance(item.get("source_id"), str)}

    for source_id in CANDIDATE_SOURCE_IDS:
        if source_id in {str(item.get("source_id")) for item in connected_sources}:
            reasons.append(f"candidate source must not be connected: {source_id}")

    gemini = source_lookup.get("gemini_google_generative_ai")
    if not gemini:
        reasons.append("gemini_google_generative_ai entry missing")
    else:
        if gemini.get("source_category") != "llm_api":
            reasons.append("gemini_google_generative_ai must use source_category llm_api")
        if gemini.get("source_role") != "data_source":
            reasons.append("gemini_google_generative_ai must be a data_source")
        if gemini.get("connection_state") != "connected":
            reasons.append("gemini_google_generative_ai must be connected")

    for source_id in ["finmind", "mops_public_information_observatory"]:
        entry = source_lookup.get(source_id)
        if not entry:
            reasons.append(f"{source_id} entry missing")
        elif entry.get("connection_state") != "candidate":
            reasons.append(f"{source_id} must remain candidate")

    notification_separation_ok = all(
        item.get("source_role") == "notification_output" and item.get("source_category") in NOTIFICATION_CATEGORIES
        for item in notification_outputs
    )
    if not notification_separation_ok:
        reasons.append("notification outputs must remain separated from data sources")

    if any(item.get("credentials_required") is True and item.get("external_service") is False for item in all_sources):
        reasons.append("credentials_required sources should not be local-only")

    cost_summary = Counter(
        item.get("cost_tier")
        for item in all_sources
        if isinstance(item.get("cost_tier"), str)
    )

    summary = {
        "schema_version": 1,
        "operation": "source_inventory_registry_read_only_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safety_mode": "research_only_read_only",
        "registry_path": str(registry_path),
        "registry_name": registry.get("registry_name"),
        "inventory_summary": {
            "connected_source_ids": [item.get("source_id") for item in connected_sources],
            "notification_output_ids": [item.get("source_id") for item in notification_outputs],
            "candidate_source_ids": [item.get("source_id") for item in candidate_sources],
            "connected_source_count": len(connected_sources),
            "notification_output_count": len(notification_outputs),
            "candidate_source_count": len(candidate_sources),
            "total_source_count": len(all_sources),
        },
        "cost_governance_summary": {
            "cost_tier_counts": dict(sorted(cost_summary.items())),
            "high_cost_sources": [
                item.get("source_id")
                for item in all_sources
                if item.get("cost_tier") in {"variable", "unknown"}
            ],
            "cost_control_notes": [
                "Treat notification and AI model services as cost-sensitive surfaces.",
                "Keep candidate sources unconnected until cost and value are reviewed separately.",
            ],
        },
        "validation_summary": {
            "unique_source_ids": len(source_id_counts),
            "duplicate_source_ids": duplicate_ids,
            "connected_source_validation": "passed" if not any(
                reason.startswith("connected_sources") for reason in reasons
            ) else "failed",
            "notification_separation_validation": "passed" if notification_separation_ok else "failed",
            "gemini_category_validation": "passed" if not any(
                "gemini_google_generative_ai" in reason for reason in reasons
            ) else "failed",
            "candidate_source_validation": "passed" if not any(
                source_id in reason for source_id in CANDIDATE_SOURCE_IDS for reason in reasons
            ) else "failed",
            "credentials_consistency_validation": "passed" if not any(
                "credentials_required" in reason or "credential_fields" in reason for reason in reasons
            ) else "failed",
        },
        "audit_summary": {
            "source_roles": {
                "data_source": len(connected_sources),
                "notification_output": len(notification_outputs),
                "candidate_source": len(candidate_sources),
            },
            "read_only": True,
            "no_external_service_calls": True,
            "no_db_mutations": True,
            "no_notifications_sent": True,
        },
        "warnings": warnings,
        "reasons": reasons,
        "side_effects": {
            "files_modified": False,
            "database_modified": False,
            "production_data_modified": False,
            "external_api_called": False,
            "notification_sent": False,
            "trading_execution_run": False,
            "production_pipeline_run": False,
            "scheduler_modified": False,
            "secrets_read_or_modified": False,
        },
    }
    output = {
        "ok": True,
        "passed": not reasons,
        **summary,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if output["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
