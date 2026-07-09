#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HANDLER = ROOT / "scripts/orchestrator/manual_rerun_single_window.py"
HASHER = ROOT / "scripts/orchestrator/hash_manual_rerun_pin_v1.py"
SIM_JSON = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_simulation_latest.json"
AUDIT = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_latest.json"
STATUS = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_status_latest.json"
HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
DOCS = [ROOT / "docs/dashboard_manual_single_window_rerun_v1.md", ROOT / "docs/runbooks/dashboard_manual_single_window_rerun_runbook.md"]
ALLOWED_WINDOWS = {"pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"}
FORBIDDEN_PIN_TERMS = ["123456", "plaintext_pin", "submitted_pin", "pin_hash\"", "pin\""]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    for path in [HANDLER, HASHER, SIM_JSON, AUDIT, STATUS, HTML, *DOCS]:
        if not path.exists():
            errors.append(f"missing file: {path.relative_to(ROOT)}")
    handler = HANDLER.read_text(encoding="utf-8") if HANDLER.exists() else ""
    hasher = HASHER.read_text(encoding="utf-8") if HASHER.exists() else ""
    html = HTML.read_text(encoding="utf-8") if HTML.exists() else ""
    sim = load(SIM_JSON) if SIM_JSON.exists() else {}
    audit = load(AUDIT) if AUDIT.exists() else {}
    status = load(STATUS) if STATUS.exists() else {}

    if "^[0-9]{6}$" not in handler or "^[0-9]{6}$" not in hasher:
        errors.append("6-digit numeric PIN regex missing")
    if "STOCK_AI_MANUAL_RERUN_PIN_HASH" not in handler:
        errors.append("runtime PIN hash env var missing")
    if "ALLOWED_WINDOWS" not in handler or not all(w in handler for w in ALLOWED_WINDOWS):
        errors.append("window allowlist incomplete")
    if "dashboard_refresh_only" not in handler:
        errors.append("dashboard_refresh_only mode missing")
    for forbidden in ["full_delivery", "send_line", "send_email", "trade", "all_windows"]:
        if forbidden not in handler:
            errors.append(f"rejected mode/window marker missing: {forbidden}")
    for marker in ["GLOBAL_LOCK", "WINDOW_COOLDOWN_SECONDS", "TIMEOUT_SECONDS", "line_attempted", "email_attempted"]:
        if marker not in handler:
            errors.append(f"handler missing safety marker: {marker}")

    cases = sim.get("cases", {}) if isinstance(sim.get("cases"), dict) else {}
    for window in ALLOWED_WINDOWS:
        case = cases.get(f"valid_{window}", {})
        if case.get("accepted") is not True or case.get("window") != window:
            errors.append(f"valid simulation failed for {window}")
        if case.get("line_attempted") is not False or case.get("email_attempted") is not False:
            errors.append(f"valid simulation attempted notification for {window}")
    for key in ["invalid_all_windows", "invalid_unknown_window", "invalid_array_windows", "missing_pin", "non_digit_pin", "short_pin", "long_pin", "wrong_pin", "missing_pin_config", "cooldown_active", "lock_busy", "invalid_mode_send_line", "invalid_mode_full_delivery"]:
        if cases.get(key, {}).get("accepted") is True:
            errors.append(f"invalid simulation accepted: {key}")
    if cases.get("missing_pin_config", {}).get("status") != "manual_rerun_disabled":
        errors.append("missing PIN config must disable manual rerun")
    if cases.get("wrong_pin", {}).get("status") != "unauthorized":
        errors.append("wrong PIN must be unauthorized")
    if cases.get("cooldown_active", {}).get("status") != "cooldown_active":
        errors.append("cooldown simulation missing")
    if cases.get("lock_busy", {}).get("status") != "lock_busy":
        errors.append("lock busy simulation missing")

    for key in ["pin", "plaintext_pin", "submitted_pin", "pin_hash", "token", "secret"]:
        if key in audit:
            errors.append(f"audit artifact must not contain {key}")
    if audit.get("line_attempted") is not False or audit.get("email_attempted") is not False:
        errors.append("audit must record no LINE/Email")
    if audit.get("mode") != "dashboard_refresh_only":
        errors.append("audit mode must be dashboard_refresh_only")
    if audit.get("requested_window") != audit.get("executed_window"):
        errors.append("audit must be single-window only")
    if status.get("pin_recorded") is not False:
        errors.append("status artifact must not record PIN")

    for marker in ["手動重跑", "重跑 07:00 盤前", "重跑 13:05 盤中", "重跑 13:35 收盤快照", "重跑 15:00 盤後檢討", "6 位數字", "不會重送 LINE / Email", "不會執行交易", "不會一次重跑四個批次", "manual-rerun-status"]:
        if marker not in html:
            errors.append(f"Dashboard manual rerun UI marker missing: {marker}")
    if html.count("data-window=") != 4:
        errors.append("Dashboard must have exactly four manual rerun window buttons")
    if any(term in html for term in ["123456", "314159", "271828", "STOCK_AI_MANUAL_RERUN_PIN_HASH"]):
        errors.append("frontend must not expose accepted PIN or hash env var")
    if "all_windows" in html or "data-window=\"all" in html:
        errors.append("Dashboard must not expose all-windows rerun")

    scanned = "\n".join([handler, hasher, html, json.dumps(audit, ensure_ascii=False), json.dumps(status, ensure_ascii=False)])
    if "123456" in scanned:
        errors.append("repo/artifact contains forbidden example accepted PIN 123456")
    for pattern in [r"BEGIN (RSA|OPENSSH) PRIVATE KEY", r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", r"api[_-]?key\s*[:=]", r"password\s*[:=]"]:
        if re.search(pattern, scanned, re.I):
            errors.append(f"secret-like pattern found: {pattern}")

    return {
        "ok": not errors,
        "task_id": "AI-DEV-162",
        "errors": errors,
        "warnings": warnings,
        "allowed_windows": sorted(ALLOWED_WINDOWS),
        "simulation_case_count": len(cases),
        "line_attempted": False,
        "email_attempted": False,
        "scheduler_modified": False,
        "production_pipeline_executed": False,
        "python_main_executed": False,
        "db_write": False,
        "trading_or_order_executed": False,
        "pin_plaintext_committed": False,
        "runtime_deployment_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
