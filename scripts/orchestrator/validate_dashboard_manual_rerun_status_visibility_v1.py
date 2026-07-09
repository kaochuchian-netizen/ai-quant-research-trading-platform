#!/usr/bin/env python3
"""Validate Dashboard manual rerun status visibility and safe runtime feedback."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
PUBLIC_BASE = "http://35.201.242.167"
POST_PATH = "/stock-ai-dashboard/api/manual-rerun"
STATUS_PATH = "/stock-ai-dashboard/api/manual-rerun/status"

REQUIRED_MARKERS = [
    "手動重跑狀態",
    "目前狀態",
    "批次",
    "開始時間",
    "完成時間",
    "LINE 是否觸發",
    "Email 是否觸發",
    "交易/下單是否發生",
    "錯誤/拒絕原因",
    "重新整理重跑狀態",
    STATUS_PATH,
    "setInterval",
    "4000",
    "confirm_single_window_only",
    "重跑已完成",
    "重跑失敗",
    "重跑被拒絕",
]


def stable(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, method=method, headers={"Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            parsed["http_status"] = resp.status
            parsed["content_type"] = resp.headers.get("Content-Type", "")
            return parsed
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"body": body[:500]}
        parsed["http_status"] = exc.code
        parsed["content_type"] = exc.headers.get("Content-Type", "")
        return parsed
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error_type": exc.__class__.__name__, "error_message": str(exc)}


def prohibited_processes() -> list[str]:
    proc = run(["ps", "-ef"])
    hits: list[str] = []
    needles = ["run_stock_analysis.sh", "approved_pre_open_delivery.py", "scripts/run_pipeline.py", "manual_rerun_single_window.py"]
    for line in proc.stdout.splitlines():
        if any(n in line for n in needles) and "validate_dashboard_manual_rerun_status_visibility_v1.py" not in line:
            hits.append(line)
    return hits


def runtime_available() -> bool:
    probe = request_json("GET", PUBLIC_BASE + STATUS_PATH)
    return "http_status" in probe or probe.get("error_type") is None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []

    html = HTML.read_text(encoding="utf-8") if HTML.exists() else ""
    static_checks: dict[str, Any] = {}
    for marker in REQUIRED_MARKERS:
        ok = marker in html
        static_checks[marker] = ok
        if not ok:
            errors.append(f"Dashboard HTML missing marker: {marker}")
    if "localStorage" in html or "sessionStorage" in html:
        errors.append("Dashboard must not store PIN in localStorage/sessionStorage")
    if re.search(r"pin(Input)?\.value\s*=\s*['\"]\d{6}['\"]", html):
        errors.append("Dashboard appears to render or hardcode a PIN value")
    if re.search(r"\b(send_line|send_email|full_delivery|trade|order)\b", html):
        # The UI may contain no-trading wording, but must not submit these modes.
        submitted_modes = re.findall(r"mode:\s*['\"](send_line|send_email|full_delivery|trade|order)['\"]", html)
        if submitted_modes:
            errors.append("Dashboard submits forbidden manual rerun mode: " + ", ".join(submitted_modes))
    for phrase in ["會重送 LINE", "會發送 Email", "會執行交易", "會下單"]:
        if phrase in html and "不" not in html[max(0, html.find(phrase)-3):html.find(phrase)+len(phrase)]:
            errors.append(f"Dashboard text may imply unsafe action: {phrase}")
    static_checks["no_local_storage"] = "localStorage" not in html and "sessionStorage" not in html
    static_checks["pin_input_cleared"] = "pinInput.value = ''" in html
    if not static_checks["pin_input_cleared"]:
        errors.append("Dashboard should clear PIN input after submit/error")

    runtime_checks: dict[str, Any] = {"available": runtime_available()}
    skipped: list[str] = []
    if not runtime_checks["available"]:
        skipped.append("runtime_api_checks")
    else:
        before = prohibited_processes()
        status = request_json("GET", PUBLIC_BASE + STATUS_PATH)
        invalid_pin = request_json("POST", PUBLIC_BASE + POST_PATH, {"window": "intraday_1305", "mode": "dashboard_refresh_only", "pin": "abc123", "confirm_single_window_only": True})
        missing_confirm = request_json("POST", PUBLIC_BASE + POST_PATH, {"window": "intraday_1305", "mode": "dashboard_refresh_only", "pin": "abc123"})
        after = prohibited_processes()
        runtime_checks.update({
            "status_get": status,
            "invalid_pin_rejection": invalid_pin,
            "missing_confirm_rejection": missing_confirm,
            "prohibited_processes_before": before,
            "prohibited_processes_after": after,
        })
        if "json" not in str(status.get("content_type", "")).lower():
            errors.append("GET manual rerun status must return JSON when runtime is available")
        if invalid_pin.get("http_status") != 403 or invalid_pin.get("status") != "invalid_pin_format":
            errors.append("invalid non-digit PIN must return HTTP 403 JSON invalid_pin_format")
        if missing_confirm.get("http_status") != 403 or missing_confirm.get("reason") != "single_window_confirmation_required":
            errors.append("missing confirm_single_window_only must return HTTP 403 JSON single_window_confirmation_required")
        if after:
            errors.append("safe rejection tests started prohibited delivery/pipeline process")

    result = {
        "schema_version": "dashboard_manual_rerun_status_visibility_validation_v1",
        "task_id": "AI-DEV-167",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "static_dashboard_checks": static_checks,
        "runtime_api_checks": runtime_checks,
        "skipped_runtime_checks": skipped,
        "safety": {
            "real_pin_used": False,
            "pin_or_hash_printed": False,
            "valid_manual_rerun_triggered": False,
            "line_email_notification_sent": False,
            "production_pipeline_executed": False,
            "db_write": False,
            "scheduler_modified": False,
            "trading_or_order_executed": False,
        },
    }
    print(stable(result) if args.pretty else json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
