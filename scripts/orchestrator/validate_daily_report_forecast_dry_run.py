#!/usr/bin/env python3
"""Validate the daily report forecast dry-run generator and output example."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


GENERATOR_PATH = Path("scripts/orchestrator/generate_daily_report_forecast_dry_run.py")
EXAMPLE_PATH = Path("templates/daily_report_forecast_dry_run_output.example.json")
CONTRACT_PATH = Path("templates/daily_report_forecast_contract.example.json")

REQUIRED_KEYS = [
    "schema_version",
    "report_date",
    "market",
    "report_window",
    "generated_at",
    "dry_run",
    "stock_universe",
    "forecast_horizons",
    "per_stock_forecasts",
    "same_day_high_low",
    "next_day_high_low",
    "one_month_trend",
    "three_month_trend",
    "confidence",
    "interval_bounds",
    "evidence_sources",
    "risk_flags",
    "output_channels",
    "dashboard_detail_ready",
    "email_detail_ready",
    "line_reminder_only",
    "review_required",
    "no_trading_instruction",
    "no_order_execution",
    "research_only",
]

REQUIRED_HORIZONS = [
    "same_day_high_low",
    "next_day_high_low",
    "one_month_trend",
    "three_month_trend",
]

REQUIRED_TRUE_FLAGS = [
    "dry_run",
    "research_only",
    "no_trading_instruction",
    "no_order_execution",
    "review_required",
]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

FORBIDDEN_VALUE_PATTERNS = [
    re.compile(r"\b(buy|sell|short|long)\s+(now|today|at market|at open|at close)\b", re.IGNORECASE),
    re.compile(r"\b(place|submit|route|execute)\s+(an?\s+)?order\b", re.IGNORECASE),
    re.compile(r"\border\s+(now|immediately|ticket)\b", re.IGNORECASE),
]


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def run_generator(repo_root: Path) -> tuple[Any | None, str, str | None]:
    command = [sys.executable, str(repo_root / GENERATOR_PATH), "--pretty"]
    try:
        completed = subprocess.run(command, cwd=repo_root, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        return None, exc.stdout, exc.stderr or str(exc)
    try:
        return json.loads(completed.stdout), completed.stdout, None
    except json.JSONDecodeError as exc:
        return None, completed.stdout, str(exc)


def iter_string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(iter_string_values(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(iter_string_values(item))
        return result
    return []


def validate_payload(name: str, payload: Any) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"loaded": False}, [f"{name} root must be an object"]

    missing_keys = [key for key in REQUIRED_KEYS if key not in payload]
    errors.extend(f"{name} missing key: {key}" for key in missing_keys)

    if payload.get("report_window") != "pre_open_0700":
        errors.append(f"{name} report_window must be pre_open_0700")

    for flag in REQUIRED_TRUE_FLAGS:
        if payload.get(flag) is not True:
            errors.append(f"{name} {flag} must be true")

    horizons = payload.get("forecast_horizons")
    if not isinstance(horizons, list):
        errors.append(f"{name} forecast_horizons must be a list")
        horizons = []
    for horizon in REQUIRED_HORIZONS:
        if horizon not in horizons:
            errors.append(f"{name} missing forecast horizon: {horizon}")
        if not isinstance(payload.get(horizon), dict):
            errors.append(f"{name} missing horizon object: {horizon}")

    per_stock = payload.get("per_stock_forecasts")
    if not isinstance(per_stock, list) or not per_stock:
        errors.append(f"{name} per_stock_forecasts must be a non-empty list")

    output_channels = payload.get("output_channels")
    if not isinstance(output_channels, dict):
        errors.append(f"{name} output_channels must be an object")
        output_channels = {}
    for channel in ["dashboard", "email", "line_reminder"]:
        if channel not in output_channels:
            errors.append(f"{name} output_channels missing {channel}")

    line_channel = output_channels.get("line_reminder")
    if payload.get("line_reminder_only") is not True and not (
        isinstance(line_channel, dict) and line_channel.get("reminder_only") is True
    ):
        errors.append(f"{name} must mark LINE as reminder-only")

    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"{name} contains secret-like pattern: {pattern.pattern}")
            break

    for text in iter_string_values(payload):
        for pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(text):
                errors.append(f"{name} contains possible trading or order instruction: {text}")

    return {
        "loaded": True,
        "required_keys_present": not missing_keys,
        "required_horizons_present": all(horizon in horizons for horizon in REQUIRED_HORIZONS),
        "safety_flags_present": all(payload.get(flag) is True for flag in REQUIRED_TRUE_FLAGS),
        "line_reminder_only": payload.get("line_reminder_only") is True,
    }, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate daily report forecast dry-run generator.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    file_checks = {
        str(GENERATOR_PATH): (repo_root / GENERATOR_PATH).is_file(),
        str(EXAMPLE_PATH): (repo_root / EXAMPLE_PATH).is_file(),
        str(CONTRACT_PATH): (repo_root / CONTRACT_PATH).is_file(),
    }
    for rel_path, exists in file_checks.items():
        if not exists:
            errors.append(f"required file missing: {rel_path}")

    example_data: Any | None = None
    example_summary: dict[str, Any] = {"loaded": False}
    if file_checks[str(EXAMPLE_PATH)]:
        example_data, load_error = load_json(repo_root / EXAMPLE_PATH)
        if load_error:
            errors.append(f"example JSON parse failed: {load_error}")
        else:
            example_summary, example_errors = validate_payload("example", example_data)
            errors.extend(example_errors)

    generated_1, generated_stdout_1, generated_error_1 = run_generator(repo_root) if file_checks[str(GENERATOR_PATH)] else (None, "", "generator missing")
    generated_2, generated_stdout_2, generated_error_2 = run_generator(repo_root) if file_checks[str(GENERATOR_PATH)] else (None, "", "generator missing")
    if generated_error_1:
        errors.append(f"generator run failed: {generated_error_1}")
    if generated_error_2:
        errors.append(f"second generator run failed: {generated_error_2}")
    deterministic = generated_stdout_1 == generated_stdout_2 and generated_1 == generated_2
    if not deterministic:
        errors.append("generator output must be deterministic")

    generated_summary: dict[str, Any] = {"loaded": False}
    if generated_1 is not None:
        generated_summary, generated_errors = validate_payload("generated", generated_1)
        errors.extend(generated_errors)

    if example_data is not None and generated_1 is not None and example_data != generated_1:
        warnings.append("example output differs from current generator output")

    report = {
        "ok": not errors,
        "file_checks": file_checks,
        "generator_deterministic": deterministic,
        "example_summary": example_summary,
        "generated_summary": generated_summary,
        "forecast_horizons": REQUIRED_HORIZONS,
        "safety_flags": REQUIRED_TRUE_FLAGS,
        "warnings": warnings,
        "errors": errors,
        "side_effects": {
            "production_db_read": False,
            "external_api_called": False,
            "notification_sent": False,
            "credentials_required": False,
            "production_pipeline_run": False,
        },
    }

    print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
