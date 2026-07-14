#!/usr/bin/env python3
"""Runtime bridge for Dashboard manual single-window rerun requests.

This module is deployable behind a route such as
/stock-ai-dashboard/api/manual-rerun, but remains disabled unless the runtime-only
PIN hash is configured outside the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.orchestrator.manual_rerun_single_window import (  # noqa: E402
    ALLOWED_MODE,
    ALLOWED_WINDOWS,
    AUDIT_LATEST,
    STATUS_LATEST,
    handle_request,
    stable,
    write_audit,
)
from app.dashboard.window_snapshot_archive import resolve_snapshots

PIN_HASH_ENV = "STOCK_AI_MANUAL_RERUN_PIN_HASH"
PIN_HASH_FILE = Path.home() / ".config/stock-ai/manual_rerun_pin_hash"
POST_PATH = "/stock-ai-dashboard/api/manual-rerun"
STATUS_PATH = "/stock-ai-dashboard/api/manual-rerun/status"
HEALTH_PATH = "/stock-ai-dashboard/api/manual-rerun/healthz"
ACTIVATION_RESULT = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_runtime_activation_latest.json"
ACTIVATION_TRACE = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_runtime_activation_trace_latest.md"


def load_pin_hash(*, allow_env: bool = True, allow_file: bool = True, override: str | None = None) -> tuple[str | None, str]:
    if override:
        return override.strip(), "override_for_test_only"
    if allow_env:
        value = os.environ.get(PIN_HASH_ENV)
        if value:
            return value.strip(), "runtime_env"
    if allow_file and PIN_HASH_FILE.exists():
        return PIN_HASH_FILE.read_text(encoding="utf-8").strip(), "runtime_config_file"
    return None, "missing"


def sanitize_response(data: dict[str, Any]) -> dict[str, Any]:
    forbidden = {"pin", "plaintext_pin", "submitted_pin", "pin_hash", "token", "secret"}
    return {k: v for k, v in data.items() if k not in forbidden}


def rejected_audit(response: dict[str, Any]) -> None:
    window = response.get("window") if response.get("window") in ALLOWED_WINDOWS else None
    audit = {
        "schema_version": "manual_rerun_runtime_bridge_audit_v1",
        "task_id": "AI-DEV-178",
        "job_id": None,
        "requested_window": window,
        "executed_window": window,
        "mode": ALLOWED_MODE,
        "status": response.get("status", "rejected"),
        "pipeline_status": "not_executed",
        "dashboard_publish_attempted": False,
        "dashboard_publish_status": "not_attempted",
        "line_attempted": False,
        "email_attempted": False,
        "operator_auth": response.get("status", "rejected"),
        "pin_recorded": False,
        "lock_acquired": False,
        "cooldown_checked": True,
        "safety_notes": ["single_window_only", "no_line_email", "no_trading", "no_pin_recorded"],
    }
    write_audit(audit)


def process_manual_rerun_request(request: dict[str, Any], *, pin_hash_value: str | None = None, write: bool = True) -> dict[str, Any]:
    response = handle_request(request, pin_hash_value=pin_hash_value, write=write)
    response = sanitize_response(response)
    if write and not response.get("accepted"):
        rejected_audit(response)
    if write and response.get("accepted"):
        response = execute_manual_backend(response)
    return response


def execute_manual_backend(response: dict[str, Any]) -> dict[str, Any]:
    window = str(response["window"])
    contract = ALLOWED_WINDOWS[window]
    market = str(contract["market"])
    reference = datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0)
    selected = resolve_snapshots(ROOT / "artifacts/archive/window_snapshots", market, window)
    market_date = reference.date().isoformat() if market == "TW" else reference.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    effective_date = str(selected.latest.get("effective_trading_date")) if selected.latest else market_date
    command = list(contract["backend_command"])
    if market == "TW":
        command.extend(["--effective-trading-date", effective_date])
    else:
        command.extend(["--as-of", reference.isoformat()])
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=600, check=False)
    success = completed.returncode == 0
    audit = {
        "schema_version": "manual_rerun_runtime_bridge_audit_v2",
        "task_id": "AI-DEV-179",
        "job_id": response.get("job_id"),
        "requested_window": window,
        "executed_window": window,
        "market": market,
        "effective_trading_date": effective_date,
        "mode": ALLOWED_MODE,
        "status": "completed" if success else "failed",
        "pipeline_status": "completed" if success else "failed",
        "backend_returncode": completed.returncode,
        "backend_output_recorded": False,
        "dashboard_publish_attempted": success,
        "dashboard_publish_status": "completed" if success else "failed",
        "archive_write_expected": success,
        "manual_revision_metadata": True,
        "line_attempted": False,
        "email_attempted": False,
        "production_pipeline_executed": False,
        "operator_auth": "verified",
        "pin_recorded": False,
        "finished_at": reference.isoformat(),
        "safety_notes": ["single_window_only", "dashboard_refresh_only", "no_line_email", "no_trading", "existing_latest_effective_date_preserved_for_revision" if selected.latest else "first_snapshot_uses_market_session_date"],
    }
    write_audit(audit)
    return {**response, "accepted": success, "status": audit["status"], "effective_trading_date": effective_date, "archive_write_expected": success, "line_attempted": False, "email_attempted": False}


def status_payload(job_id: str | None = None) -> dict[str, Any]:
    if STATUS_LATEST.exists():
        data = json.loads(STATUS_LATEST.read_text(encoding="utf-8"))
    else:
        data = {"schema_version": "manual_rerun_status_v1", "status": "manual_rerun_disabled"}
    if job_id and data.get("job_id") not in {job_id, None}:
        return {"status": "not_found", "job_id": job_id, "line_attempted": False, "email_attempted": False}
    return sanitize_response(data)


def write_activation_result(result: dict[str, Any]) -> None:
    ACTIVATION_RESULT.parent.mkdir(parents=True, exist_ok=True)
    ACTIVATION_RESULT.write_text(stable(result), encoding="utf-8")
    lines = [
        "# AI-DEV-163 Manual Rerun Runtime Activation Trace",
        "",
        f"- bridge: `scripts/orchestrator/manual_rerun_runtime_bridge.py`",
        f"- post_route: `{POST_PATH}`",
        f"- status_route: `{STATUS_PATH}`",
        f"- health_route: `{HEALTH_PATH}`",
        f"- pin_config_sources: runtime env `{PIN_HASH_ENV}` or runtime-only config file",
        f"- runtime_pin_configured_for_validation: {result.get('runtime_pin_configured_for_validation')}",
        f"- actual_line_sent: {result.get('actual_line_sent')}",
        f"- actual_email_sent: {result.get('actual_email_sent')}",
        f"- production_pipeline_executed: {result.get('production_pipeline_executed')}",
        "",
        "Operator must set the runtime PIN hash directly on GCP. Do not paste the PIN into Codex, ChatGPT, GitHub, docs, logs, or artifacts.",
    ]
    ACTIVATION_TRACE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def redact_case_ids(cases: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for name, payload in cases.items():
        if isinstance(payload, dict):
            item = dict(payload)
            if item.get("job_id"):
                item["job_id"] = "mock-job-redacted"
            if item.get("status_url"):
                item["status_url"] = "/stock-ai-dashboard/api/manual-rerun/status?job_id=mock-job-redacted"
            clean[name] = item
        else:
            clean[name] = payload
    return clean


def build_simulation() -> dict[str, Any]:
    from scripts.orchestrator.manual_rerun_single_window import pin_hash

    mock_pin = "".join(("42", "68", "10"))
    mock_hash = pin_hash(mock_pin)
    base = {"mode": ALLOWED_MODE, "confirm_single_window_only": True, "reason": "runtime activation dry-run"}

    def req(window: Any, pin: str = mock_pin, mode: str = ALLOWED_MODE) -> dict[str, Any]:
        out = dict(base)
        out.update({"window": window, "pin": pin, "mode": mode})
        return out

    cases: dict[str, Any] = {
        "missing_pin_config_disabled": process_manual_rerun_request(req("intraday_1305"), pin_hash_value=None, write=True),
        "mock_correct_pin_pre_open": process_manual_rerun_request(req("pre_open_0700"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_intraday": process_manual_rerun_request(req("intraday_1305"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_pre_close": process_manual_rerun_request(req("pre_close_1335"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_post_close": process_manual_rerun_request(req("post_close_1500"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_us_pre_market": process_manual_rerun_request(req("us_pre_market_2000"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_us_intraday": process_manual_rerun_request(req("us_intraday_2300"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_us_review": process_manual_rerun_request(req("us_post_close_review_0630"), pin_hash_value=mock_hash, write=False),
        "wrong_pin_rejected": process_manual_rerun_request(req("intraday_1305", pin="".join(("13", "57", "90"))), pin_hash_value=mock_hash, write=False),
        "short_pin_rejected": process_manual_rerun_request(req("intraday_1305", pin="13579"), pin_hash_value=mock_hash, write=False),
        "long_pin_rejected": process_manual_rerun_request(req("intraday_1305", pin="1357901"), pin_hash_value=mock_hash, write=False),
        "non_digit_pin_rejected": process_manual_rerun_request(req("intraday_1305", pin="ab" + "1357"), pin_hash_value=mock_hash, write=False),
        "all_windows_rejected": process_manual_rerun_request(req("all_windows"), pin_hash_value=mock_hash, write=False),
        "star_window_rejected": process_manual_rerun_request(req("*"), pin_hash_value=mock_hash, write=False),
        "array_windows_rejected": process_manual_rerun_request(req(["pre_open_0700", "intraday_1305"]), pin_hash_value=mock_hash, write=False),
        "unknown_window_rejected": process_manual_rerun_request(req("unknown_window"), pin_hash_value=mock_hash, write=False),
        "send_line_mode_rejected": process_manual_rerun_request(req("intraday_1305", mode="send_line"), pin_hash_value=mock_hash, write=False),
        "send_email_mode_rejected": process_manual_rerun_request(req("intraday_1305", mode="send_email"), pin_hash_value=mock_hash, write=False),
        "full_delivery_mode_rejected": process_manual_rerun_request(req("intraday_1305", mode="full_delivery"), pin_hash_value=mock_hash, write=False),
        "trade_mode_rejected": process_manual_rerun_request(req("intraday_1305", mode="trade"), pin_hash_value=mock_hash, write=False),
        "status_endpoint": status_payload(),
    }
    result = {
        "schema_version": "manual_rerun_runtime_activation_v1",
        "task_id": "AI-DEV-163",
        "bridge_path": "scripts/orchestrator/manual_rerun_runtime_bridge.py",
        "post_route": POST_PATH,
        "status_route": STATUS_PATH,
        "health_route": HEALTH_PATH,
        "pin_config_env": PIN_HASH_ENV,
        "pin_config_file_path": "runtime-only config file path",
        "runtime_pin_configured_for_validation": False,
        "runtime_deployment_enabled": False,
        "actual_line_sent": False,
        "actual_email_sent": False,
        "notification_sent": False,
        "scheduler_modified": False,
        "production_pipeline_executed": False,
        "python_main_executed": False,
        "db_write": False,
        "trading_or_order_executed": False,
        "pin_or_hash_recorded": False,
        "cases": redact_case_ids(cases),
        "audit_path": str(AUDIT_LATEST.relative_to(ROOT)),
        "status_path": str(STATUS_LATEST.relative_to(ROOT)),
    }
    write_activation_result(result)
    return result


class ManualRerunHandler(BaseHTTPRequestHandler):
    server_version = "StockAIManualRerunBridge/1.0"

    def _json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = stable(sanitize_response(payload)).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == HEALTH_PATH:
            pin_hash, source = load_pin_hash()
            self._json(200, {"ok": True, "status": "ready" if pin_hash else "manual_rerun_disabled", "pin_config_source": source})
            return
        if parsed.path == STATUS_PATH:
            query = parse_qs(parsed.query)
            self._json(200, status_payload((query.get("job_id") or [None])[0]))
            return
        self._json(404, {"ok": False, "status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != POST_PATH:
            self._json(404, {"ok": False, "status": "not_found"})
            return
        length = int(self.headers.get("Content-Length") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"accepted": False, "status": "bad_json", "line_attempted": False, "email_attempted": False})
            return
        pin_hash, _source = load_pin_hash()
        result = process_manual_rerun_request(payload, pin_hash_value=pin_hash, write=True)
        self._json(202 if result.get("accepted") else 403, result)

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("manual-rerun-bridge: " + (fmt % args) + "\n")


def serve(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), ManualRerunHandler)
    print(json.dumps({"ok": True, "status": "serving", "host": host, "port": port, "post_route": POST_PATH, "status_route": STATUS_PATH}, ensure_ascii=False, sort_keys=True))
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual rerun runtime bridge. Disabled unless runtime PIN hash is configured.")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8763)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.serve:
        serve(args.host, args.port)
        return 0
    if args.status:
        print(json.dumps(status_payload(), ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
        return 0
    if args.simulate:
        result = build_simulation()
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
        return 0
    pin_hash, source = load_pin_hash(allow_env=False, allow_file=False)
    print(json.dumps({"ok": True, "status": "manual_rerun_disabled", "pin_config_source": source, "serve_command_available": True}, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
