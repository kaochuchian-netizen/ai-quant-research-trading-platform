#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "scripts/orchestrator/manual_rerun_runtime_bridge.py"
HANDLER = ROOT / "scripts/orchestrator/manual_rerun_single_window.py"
HASHER = ROOT / "scripts/orchestrator/hash_manual_rerun_pin_v1.py"
ACTIVATION = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_runtime_activation_latest.json"
TRACE = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_runtime_activation_trace_latest.md"
AUDIT = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_latest.json"
STATUS = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_status_latest.json"
HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
DOC = ROOT / "docs/manual_rerun_runtime_activation_v1.md"
RUNBOOK = ROOT / "docs/runbooks/manual_rerun_runtime_activation_runbook.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def add(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []

    for path, label in [(BRIDGE, "runtime bridge"), (HANDLER, "handler"), (HASHER, "hash helper"), (ACTIVATION, "activation artifact"), (TRACE, "trace"), (AUDIT, "audit"), (STATUS, "status"), (HTML, "Dashboard HTML"), (DOC, "doc"), (RUNBOOK, "runbook")]:
        add(errors, path.exists(), f"missing {label}: {path}")
    if errors:
        print(json.dumps({"ok": False, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
        return 2

    bridge = BRIDGE.read_text(encoding="utf-8")
    handler = HANDLER.read_text(encoding="utf-8")
    hasher = HASHER.read_text(encoding="utf-8")
    html = HTML.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8") + "\n" + RUNBOOK.read_text(encoding="utf-8")
    activation = load_json(ACTIVATION)
    audit = load_json(AUDIT)
    status = load_json(STATUS)
    cases = activation.get("cases", {})

    add(errors, "BaseHTTPRequestHandler" in bridge and "ThreadingHTTPServer" in bridge, "backend runtime bridge HTTP server missing")
    add(errors, "/stock-ai-dashboard/api/manual-rerun" in bridge, "POST route missing")
    add(errors, "/stock-ai-dashboard/api/manual-rerun/status" in bridge, "status route missing")
    add(errors, "STOCK_AI_MANUAL_RERUN_PIN_HASH" in bridge, "runtime PIN hash env support missing")
    add(errors, ".config/stock-ai/manual_rerun_pin_hash" in bridge, "runtime-only PIN hash file support missing")
    add(errors, "manual_rerun_disabled" in bridge and "pin_not_configured" in handler, "missing PIN hash disabled behavior missing")
    add(errors, "PIN_RE" in handler and "^[0-9]{6}$" in handler, "6-digit PIN format guard missing")
    add(errors, "handle_request" in bridge and "process_manual_rerun_request" in bridge, "bridge does not call safe handler")
    add(errors, "send_line" in handler and "send_email" in handler and "full_delivery" in handler, "rejected delivery modes missing")
    add(errors, "trade" in handler, "trade mode rejection missing")
    add(errors, "lock_busy" in handler and "cooldown_active" in handler and "TIMEOUT_SECONDS" in handler, "lock/cooldown/timeout guard missing")

    add(errors, cases.get("missing_pin_config_disabled", {}).get("status") == "manual_rerun_disabled", "missing PIN hash must disable manual rerun")
    for key in ["mock_correct_pin_pre_open", "mock_correct_pin_intraday", "mock_correct_pin_pre_close", "mock_correct_pin_post_close"]:
        add(errors, cases.get(key, {}).get("accepted") is True, f"mock correct PIN case not accepted: {key}")
        add(errors, cases.get(key, {}).get("line_attempted") is False, f"LINE attempted in {key}")
        add(errors, cases.get(key, {}).get("email_attempted") is False, f"Email attempted in {key}")
    for key in ["wrong_pin_rejected", "short_pin_rejected", "long_pin_rejected", "non_digit_pin_rejected", "all_windows_rejected", "star_window_rejected", "array_windows_rejected", "unknown_window_rejected", "send_line_mode_rejected", "send_email_mode_rejected", "full_delivery_mode_rejected", "trade_mode_rejected"]:
        add(errors, cases.get(key, {}).get("accepted") is False, f"unsafe/invalid case accepted: {key}")
    add(errors, cases.get("status_endpoint") is not None, "status endpoint/status artifact simulation missing")

    for payload_name, payload in [("activation", activation), ("audit", audit), ("status", status)]:
        serialized = json.dumps(payload, ensure_ascii=False)
        for token in ["plaintext_pin", "submitted_pin", "pin_hash", "token", "secret"]:
            add(errors, token not in serialized, f"{payload_name} contains forbidden token marker: {token}")
        add(errors, not re.search(r"sha256:[0-9a-f]{64}", serialized), f"{payload_name} contains hash-like secret")
        add(errors, not re.search(r"(?<![0-9])[0-9]{6}(?![0-9])", serialized), f"{payload_name} contains 6-digit PIN-like value")

    add(errors, "manual-rerun-button" in html and html.count("data-window=") == 4, "Dashboard must expose exactly four manual rerun buttons")
    for marker in ["手動重跑", "重跑 07:00 盤前", "重跑 13:05 盤中", "重跑 13:35 收盤快照", "重跑 15:00 盤後檢討", "6 位數字", "不會重送 LINE / Email", "不會執行交易", "不會一次重跑四個批次"]:
        add(errors, marker in html, f"Dashboard marker missing: {marker}")
    add(errors, "123456" not in html and "STOCK_AI_MANUAL_RERUN_PIN_HASH" not in html, "frontend exposes PIN/PIN hash config marker")

    add(errors, "runtime-only" in doc and "do not paste" in doc.lower(), "docs must explain runtime-only PIN and no paste rule")
    add(errors, "rollback" in doc.lower(), "rollback plan missing")
    add(errors, "manual_rerun_disabled" in doc, "disabled-state verification missing in docs")

    add(errors, activation.get("actual_line_sent") is False, "activation artifact says LINE sent")
    add(errors, activation.get("actual_email_sent") is False, "activation artifact says Email sent")
    add(errors, activation.get("scheduler_modified") is False, "activation artifact says scheduler modified")
    add(errors, activation.get("production_pipeline_executed") is False, "activation artifact says production pipeline executed")
    add(errors, activation.get("python_main_executed") is False, "activation artifact says python main executed")
    add(errors, activation.get("db_write") is False, "activation artifact says DB write")
    add(errors, activation.get("trading_or_order_executed") is False, "activation artifact says trading/order")
    add(errors, activation.get("pin_or_hash_recorded") is False, "activation artifact says PIN/hash recorded")

    scanned = "\n".join([bridge, handler, hasher, html, doc])
    add(errors, "123456" not in scanned, "repo contains forbidden example PIN 123456")
    if re.search(r"BEGIN (RSA|OPENSSH) PRIVATE KEY|Bearer\s+[A-Za-z0-9._~+/=-]{16,}|api[_-]?key\s*[:=]|password\s*[:=]", scanned, re.IGNORECASE):
        errors.append("secret-like pattern found in repo scan")

    summary = {
        "ok": not errors,
        "task_id": "AI-DEV-163",
        "errors": errors,
        "warnings": warnings,
        "bridge": str(BRIDGE),
        "activation_artifact": str(ACTIVATION),
        "runtime_deployment_enabled": False,
        "missing_pin_config_disabled": cases.get("missing_pin_config_disabled", {}).get("status") == "manual_rerun_disabled",
        "mock_correct_pin_cases": sum(1 for key in cases if key.startswith("mock_correct_pin") and cases[key].get("accepted") is True),
        "line_attempted": False,
        "email_attempted": False,
        "scheduler_modified": False,
        "production_pipeline_executed": False,
        "python_main_executed": False,
        "trading_or_order_executed": False,
        "pin_or_hash_recorded": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
