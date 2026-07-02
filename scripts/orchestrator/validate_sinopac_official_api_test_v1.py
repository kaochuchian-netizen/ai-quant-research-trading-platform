#!/usr/bin/env python3
"""Validate AI-DEV-119 Sinopac official API online test controls."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


TASK_ID = "AI-DEV-119"
SCHEMA_VERSION = "sinopac_official_api_test_result_v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "scripts/orchestrator/sinopac_official_api_test.py"
TEMPLATE = REPO_ROOT / "templates/sinopac_official_api_test_result.example.json"

VALID_DECISIONS = {
    "sinopac_official_api_test_dry_run_ready",
    "sinopac_official_api_simulation_tests_completed",
    "sinopac_official_api_test_blocked_by_safety_gate",
}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
FORBIDDEN_SOURCE_PATTERNS = [
    re.compile(r"Shioaji\s*\(\s*simulation\s*=\s*False"),
    re.compile(r"production\s*=\s*True"),
    re.compile(r"\bsubprocess\b"),
    re.compile(r"\bsmtplib\b"),
    re.compile(r"\blinebot\b", re.IGNORECASE),
    re.compile(r"\bschedule\b"),
    re.compile(r"\bcron\b.*\b(write|install|modify|enable)\b", re.IGNORECASE),
    re.compile(r"\bsystemctl\b"),
]


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(REPO_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("sinopac_official_api_test", TARGET)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load sinopac_official_api_test module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_json(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(strings(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(strings(item))
        return result
    return []


def validate_schema(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["result root must be an object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version is invalid")
    if payload.get("task_id") != TASK_ID:
        errors.append("task_id is invalid")
    if payload.get("decision") not in VALID_DECISIONS:
        errors.append("decision is invalid")
    if not isinstance(payload.get("ok"), bool):
        errors.append("ok must be boolean")
    if not str(payload.get("generated_at", "")).strip():
        errors.append("generated_at is required")

    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    required_true = [
        "simulation_only",
        "production_blocked",
        "production_order_forbidden",
        "formal_order_forbidden",
        "stock_test_default_enabled",
        "requires_richard_same_run_approval",
        "requires_explicit_login_flag",
        "requires_explicit_order_flag",
        "no_strategy_signal_integration",
        "no_scheduler_cron_systemd_integration",
        "no_line_email_notification",
        "no_production_db_write",
        "no_secret_or_account_printing",
    ]
    required_false = ["futures_test_default_enabled"]
    for key in required_true:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    for key in required_false:
        if safety.get(key) is not False:
            errors.append(f"safety.{key} must be false")

    effects = payload.get("side_effects") if isinstance(payload.get("side_effects"), dict) else {}
    always_false = [
        "production_client_created",
        "production_order_called",
        "formal_order_called",
        "strategy_signal_connected",
        "scheduler_modified",
        "cron_modified",
        "systemd_modified",
        "line_sent",
        "email_sent",
        "production_db_modified",
        "secret_printed",
        "account_number_printed",
    ]
    for key in always_false:
        if effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")

    test_results = payload.get("test_results") if isinstance(payload.get("test_results"), dict) else {}
    for key in ["login", "stock_place_order", "futures_place_order"]:
        if key not in test_results:
            errors.append(f"test_results.{key} is required")
    if payload.get("mode") == "dry-run":
        if effects.get("secrets_read") is not False:
            errors.append("dry-run must not read secrets")
        if effects.get("simulation_login_called") is not False:
            errors.append("dry-run must not login")
        if effects.get("simulation_order_called") is not False:
            errors.append("dry-run must not place simulation orders")

    text = "\n".join(strings(payload))
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        errors.append("payload contains a secret-like value")
    return errors


def capture(name: str, check: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"name": name, "ok": True, "result": check()}
    except Exception as exc:
        return {"name": name, "ok": False, "error_class": type(exc).__name__, "error": str(exc)}


def check_dry_run() -> dict[str, Any]:
    proc = run_command([sys.executable, str(TARGET.relative_to(REPO_ROOT)), "--mode", "dry-run"])
    payload = parse_json(proc.stdout)
    errors = validate_schema(payload)
    if proc.returncode != 0:
        errors.append(f"dry-run exited {proc.returncode}")
    return {"passed": not errors, "returncode": proc.returncode, "errors": errors, "decision": payload.get("decision")}


def check_execute_without_approval_blocked() -> dict[str, Any]:
    proc = run_command([sys.executable, str(TARGET.relative_to(REPO_ROOT)), "--mode", "execute"])
    payload = parse_json(proc.stdout)
    errors = validate_schema(payload)
    if proc.returncode != 2:
        errors.append(f"execute without approval should exit 2, got {proc.returncode}")
    if payload.get("ok") is not False:
        errors.append("blocked execute payload must have ok=false")
    if payload.get("decision") != "sinopac_official_api_test_blocked_by_safety_gate":
        errors.append("blocked execute decision is invalid")
    return {"passed": not errors, "returncode": proc.returncode, "errors": errors, "decision": payload.get("decision")}


def check_production_blocked() -> dict[str, Any]:
    proc = run_command(
        [
            sys.executable,
            str(TARGET.relative_to(REPO_ROOT)),
            "--mode",
            "execute",
            "--production",
            "--i-understand-this-runs-simulation-login",
            "--i-understand-this-runs-simulation-order",
            "--richard-approval",
            "RICHARD_APPROVES_AI_DEV_119_SIMULATION_LOGIN_AND_ORDER",
        ]
    )
    payload = parse_json(proc.stdout)
    errors = validate_schema(payload)
    if proc.returncode != 2:
        errors.append(f"production request should exit 2, got {proc.returncode}")
    if "production" not in str(payload.get("error", "")).lower():
        errors.append("production block error should mention production")
    return {"passed": not errors, "returncode": proc.returncode, "errors": errors, "decision": payload.get("decision")}


def check_secret_masking() -> dict[str, Any]:
    module = load_module()
    raw = {
        "api_key": "REAL_API_KEY_SHOULD_NOT_APPEAR",
        "secret_key": "REAL_SECRET_SHOULD_NOT_APPEAR",
        "account_number": "12345678901",
        "nested": [{"token": "REAL_TOKEN_SHOULD_NOT_APPEAR"}],
        "safe": "visible",
    }
    masked = module.mask_sensitive(raw)
    encoded = json.dumps(masked, sort_keys=True)
    leaks = [value for value in ["REAL_API_KEY", "REAL_SECRET", "12345678901", "REAL_TOKEN"] if value in encoded]
    return {"passed": not leaks and encoded.count(module.MASKED) >= 4, "masked": masked, "leaks": leaks}


def check_template_schema() -> dict[str, Any]:
    payload = parse_json(TEMPLATE.read_text(encoding="utf-8"))
    errors = validate_schema(payload)
    return {"passed": not errors, "errors": errors, "decision": payload.get("decision")}


def check_no_forbidden_actions() -> dict[str, Any]:
    text = TARGET.read_text(encoding="utf-8")
    hits = [pattern.pattern for pattern in FORBIDDEN_SOURCE_PATTERNS if pattern.search(text)]
    return {
        "passed": not hits,
        "forbidden_source_patterns": hits,
        "no_line_email_scheduler_trading_production_action": not hits,
    }


def build_result() -> dict[str, Any]:
    checks = [
        capture("dry_run_allowed", check_dry_run),
        capture("execute_without_explicit_approval_blocked", check_execute_without_approval_blocked),
        capture("production_blocked", check_production_blocked),
        capture("secret_masking_works", check_secret_masking),
        capture("official_test_result_schema_valid", check_template_schema),
        capture("no_line_email_scheduler_trading_production_action", check_no_forbidden_actions),
    ]
    passed = all(check["ok"] and check.get("result", {}).get("passed") for check in checks)
    return {
        "schema_version": "sinopac_official_api_test_validation_v1",
        "task_id": TASK_ID,
        "ok": passed,
        "checks": checks,
        "side_effects": {
            "login_called": False,
            "simulation_order_called": False,
            "production_order_called": False,
            "line_sent": False,
            "email_sent": False,
            "scheduler_modified": False,
            "production_db_modified": False,
            "secrets_read": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Sinopac official API online test controls.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = build_result()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
