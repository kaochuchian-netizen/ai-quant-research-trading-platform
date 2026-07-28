#!/usr/bin/env python3
"""Validate phase ordering, exit classification and close safety."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from governance_common import EXIT_CLASSIFICATIONS, EXIT_STATUSES, PHASE_STATUSES, load_json, result_payload


def validate(path: Path) -> dict:
    data, errors = load_json(path)
    phases = data.get("phases", []) if data else []
    current_id = data.get("current_phase_id") if data else None
    if data and data.get("schema_version") != "platform_phase_status_v1": errors.append("schema_version")
    if not isinstance(phases, list) or len(phases) != 5: errors.append("five_phases_required")
    ids = [item.get("id") for item in phases if isinstance(item, dict)]
    if ids != [f"phase_{index}" for index in range(1, 6)]: errors.append("phase_order_or_identity")
    current = [item for item in phases if isinstance(item, dict) and item.get("id") == current_id]
    if len(current) != 1: errors.append("current_phase_identity")
    if sum(item.get("status") == "IN_PROGRESS" for item in phases if isinstance(item, dict)) != 1: errors.append("one_in_progress_phase_required")
    for phase in phases:
        if not isinstance(phase, dict): errors.append("phase_object"); continue
        if phase.get("status") not in PHASE_STATUSES: errors.append(f"phase_status:{phase.get('id')}")
        if not phase.get("objective") or not phase.get("name") or not isinstance(phase.get("health_target"), (int, float)): errors.append(f"phase_metadata:{phase.get('id')}")
        for item in phase.get("exit_items", []):
            if item.get("classification") not in EXIT_CLASSIFICATIONS: errors.append(f"exit_classification:{item.get('id')}")
            if item.get("status") not in EXIT_STATUSES: errors.append(f"exit_status:{item.get('id')}")
            if not all(item.get(key) for key in ("id", "owner", "evidence")): errors.append(f"exit_metadata:{item.get('id')}")
            if item.get("classification") == "DEFERRED_ENHANCEMENT" and not item.get("target_phase"): errors.append(f"deferred_target:{item.get('id')}")
        if phase.get("status") == "CLOSED" and any(item.get("classification") == "MUST_FIX_BEFORE_CLOSE" and item.get("status") != "CLOSED" for item in phase.get("exit_items", [])):
            errors.append(f"closed_phase_with_open_must_fix:{phase.get('id')}")
    return result_payload("validate_phase_registry", errors, {"path": str(path), "phase_ids": ids, "current_phase_id": current_id})


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--input", default="config/governance/platform_phase_status.json"); parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(); result = validate(Path(args.input)); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)); return 0 if result["ok"] else 2


if __name__ == "__main__": raise SystemExit(main())
