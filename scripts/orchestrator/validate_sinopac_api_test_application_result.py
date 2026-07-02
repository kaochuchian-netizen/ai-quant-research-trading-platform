#!/usr/bin/env python3
"""Validate controlled Sinopac API test application records."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TASK_ID = "AI-DEV-116"
SCHEMA_VERSION = "sinopac_api_test_application_v1"
STATUS_SCHEMA_VERSION = "sinopac_api_test_status_v1"
VALID_DECISIONS = {
    "sinopac_api_test_application_package_ready",
    "sinopac_api_runtime_health_ready",
    "sinopac_api_runtime_health_blocked",
    "sinopac_simulation_login_test_completed",
    "sinopac_simulation_stock_place_order_test_completed",
    "sinopac_simulation_futures_place_order_test_completed",
    "sinopac_api_test_blocked_by_safety_gate",
    "sinopac_api_test_status_ready",
    "sinopac_api_test_status_incomplete",
}
SAFETY_TRUE = [
    "simulation_only",
    "production_place_order_forbidden",
    "no_formal_trading",
    "no_auto_trading",
    "no_scheduler_integration",
    "no_strategy_signal_integration",
    "no_portfolio_modification",
    "no_secret_printing",
    "requires_richard_same_run_confirmation_for_order",
]
SAFETY_FALSE = ["futures_order_test_default_enabled"]
SIDE_EFFECTS_FALSE_ALWAYS = [
    "printed_secrets",
    "mutated_secrets",
    "production_place_order_called",
    "modified_portfolio",
    "modified_scheduler",
    "modified_strategy_signal",
    "sent_line_push",
    "wrote_persistent_store",
]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except Exception as exc:
        return None, [f"failed to read JSON: {exc}"]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(iter_strings(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(iter_strings(item))
        return result
    return []


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}

    schema = payload.get("schema_version")
    if schema not in {SCHEMA_VERSION, STATUS_SCHEMA_VERSION}:
        errors.append("schema_version is invalid")
    if payload.get("task_id") != TASK_ID:
        errors.append(f"task_id must be {TASK_ID}")
    if payload.get("decision") not in VALID_DECISIONS:
        errors.append("decision is invalid")
    if not isinstance(payload.get("ok"), bool):
        errors.append("ok must be boolean")
    if not str(payload.get("generated_at", "")).strip():
        errors.append("generated_at is required")

    safety = as_dict(payload.get("safety"))
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety.{key} must be false")

    side_effects = as_dict(payload.get("side_effects"))
    for key in SIDE_EFFECTS_FALSE_ALWAYS:
        if side_effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")

    decision = payload.get("decision")
    test_results = as_dict(payload.get("test_results"))
    if decision == "sinopac_simulation_login_test_completed":
        login = as_dict(test_results.get("login"))
        if login.get("simulation") is not True or login.get("ok") is not True:
            errors.append("login test result must be ok and simulation=true")
        if side_effects.get("login_called") is not True:
            errors.append("login test must record login_called=true")
        if side_effects.get("place_order_called") is not False:
            errors.append("login test must not record place_order_called=true")
    if decision == "sinopac_simulation_stock_place_order_test_completed":
        stock = as_dict(test_results.get("stock_place_order"))
        if stock.get("simulation") is not True or stock.get("ok") is not True:
            errors.append("stock place_order test result must be ok and simulation=true")
        if side_effects.get("login_called") is not True or side_effects.get("place_order_called") is not True:
            errors.append("stock place_order test must record login and order calls")
    if decision == "sinopac_simulation_futures_place_order_test_completed":
        futures = as_dict(test_results.get("futures_place_order"))
        if futures.get("simulation") is not True or futures.get("ok") is not True:
            errors.append("futures place_order test result must be ok and simulation=true")
        if side_effects.get("login_called") is not True or side_effects.get("place_order_called") is not True:
            errors.append("futures place_order test must record login and order calls")

    text = "\n".join(iter_strings(payload))
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append("payload appears to contain a secret-like value")
            break

    return {"ok": not errors, "errors": errors}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Sinopac API test application result.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload, errors = load_json(Path(args.input))
    result = {"ok": False, "errors": errors} if errors else validate_payload(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
