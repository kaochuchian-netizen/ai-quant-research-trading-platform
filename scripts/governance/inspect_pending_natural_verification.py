#!/usr/bin/env python3
"""Read-only inspector for bounded natural-verification records."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from governance_common import PENDING_STATES, load_json, result_payload


def inspect(path: Path, as_of: date) -> dict:
    data, errors = load_json(path)
    records = data.get("records", []) if data else []
    sla = data.get("sla", {}) if data else {}
    if data and data.get("schema_version") != "pending_natural_verification_v1": errors.append("schema_version")
    if sla.get("minimum_trading_days") != 2 or sla.get("maximum_trading_days") != 5: errors.append("sla_must_be_2_to_5_trading_days")
    seen: set[str] = set(); counts = {state: 0 for state in sorted(PENDING_STATES)}; warnings = []
    for record in records:
        task_id = record.get("task_id") if isinstance(record, dict) else None
        if not task_id or task_id in seen: errors.append(f"task_identity:{task_id}"); continue
        seen.add(task_id)
        state = record.get("state")
        if state not in PENDING_STATES: errors.append(f"state:{task_id}")
        else: counts[state] += 1
        if not isinstance(record.get("required_windows"), list) or not record["required_windows"]: errors.append(f"required_windows:{task_id}")
        for key in ("registered_at", "owner", "acceptance", "monitoring"):
            if not record.get(key): errors.append(f"metadata:{task_id}:{key}")
        try:
            registered = date.fromisoformat(str(record.get("registered_at")))
            calendar_days = (as_of - registered).days
            if state == "PENDING" and calendar_days > 7:
                warnings.append({"task_id": task_id, "reason": "requires_trading_calendar_sla_review", "calendar_days": calendar_days})
        except ValueError:
            errors.append(f"registered_at:{task_id}")
    result = result_payload("inspect_pending_natural_verification", errors, {"path": str(path), "as_of": as_of.isoformat(), "record_count": len(records), "state_counts": counts, "warnings": warnings})
    result["pending_is_not_failure"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--input", default="config/governance/pending_natural_verification.json"); parser.add_argument("--as-of", default=date.today().isoformat()); parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(); result = inspect(Path(args.input), date.fromisoformat(args.as_of)); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)); return 0 if result["ok"] else 2


if __name__ == "__main__": raise SystemExit(main())
