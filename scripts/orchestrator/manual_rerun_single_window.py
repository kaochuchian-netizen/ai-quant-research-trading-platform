#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.reports.window_report_contract import manual_batch_contracts

MANUAL_DIR = ROOT / "artifacts/runtime/manual_rerun"
STATUS_LATEST = MANUAL_DIR / "manual_rerun_status_latest.json"
AUDIT_LATEST = MANUAL_DIR / "manual_rerun_latest.json"
TAIPEI = ZoneInfo("Asia/Taipei")
PIN_RE = re.compile(r"^[0-9]{6}$")
PIN_HASH_PREFIX = "sha256:"
ALLOWED_WINDOWS = {
    window: {
        "label": contract.short_label,
        "market": contract.market,
        "pipeline_type": "us_manual_batch" if contract.market == "US" else {
            "pre_open_0700": "pre_open",
            "intraday_1305": "intraday",
            "pre_close_1335": "pre_close",
            "post_close_1500": "post_close",
        }.get(window, "manual"),
        "dashboard_url": contract.dashboard_url,
        "artifact_scope": contract.artifact_scope,
        "backend_command": list(contract.backend_command),
    }
    for window, contract in manual_batch_contracts().items()
}
ALLOWED_MODE = "dashboard_refresh_only"
REJECTED_MODES = {"full_delivery", "send_line", "send_email", "trade", "all_windows"}
GLOBAL_LOCK = Path("/tmp/stock_ai_manual_rerun_global.lock")
WINDOW_LOCKS = {k: Path(f"/tmp/stock_ai_manual_rerun_{k}.lock") for k in ALLOWED_WINDOWS}
GLOBAL_COOLDOWN_SECONDS = 3 * 60
WINDOW_COOLDOWN_SECONDS = 10 * 60
TIMEOUT_SECONDS = 10 * 60


def now() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()


def stable(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def pin_hash(pin: str) -> str:
    return PIN_HASH_PREFIX + hashlib.sha256(pin.encode("utf-8")).hexdigest()


def verify_pin(pin: str, expected_hash: str | None) -> tuple[bool, str]:
    if not PIN_RE.fullmatch(pin or ""):
        return False, "invalid_pin_format"
    if not expected_hash:
        return False, "pin_not_configured"
    if not expected_hash.startswith(PIN_HASH_PREFIX):
        return False, "pin_hash_invalid"
    return (hmac.compare_digest(pin_hash(pin), expected_hash), "verified" if hmac.compare_digest(pin_hash(pin), expected_hash) else "unauthorized")


def validate_window(value: Any) -> tuple[bool, str | None]:
    if isinstance(value, list):
        return False, "array_windows_rejected"
    if value in {None, "", "all", "all_windows", "*"}:
        return False, "all_windows_rejected"
    if value not in ALLOWED_WINDOWS:
        return False, "invalid_window"
    return True, None


def validate_mode(mode: str) -> tuple[bool, str | None]:
    if mode != ALLOWED_MODE:
        return False, "mode_rejected"
    if mode in REJECTED_MODES:
        return False, "mode_rejected"
    return True, None


def lock_busy(window: str, mock_lock_busy: bool = False) -> bool:
    return mock_lock_busy or GLOBAL_LOCK.exists() or WINDOW_LOCKS[window].exists()


def cooldown_active(window: str, mock_cooldown: bool = False) -> tuple[bool, int]:
    if mock_cooldown:
        return True, WINDOW_COOLDOWN_SECONDS
    latest = STATUS_LATEST if STATUS_LATEST.exists() else None
    if not latest:
        return False, 0
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return False, 0
    if data.get("requested_window") != window:
        return False, 0
    finished_at = data.get("finished_at") or data.get("requested_at")
    if not finished_at:
        return False, 0
    try:
        dt = datetime.fromisoformat(str(finished_at)).astimezone(TAIPEI)
    except ValueError:
        return False, 0
    elapsed = (datetime.now(TAIPEI) - dt).total_seconds()
    if elapsed < WINDOW_COOLDOWN_SECONDS:
        return True, int(WINDOW_COOLDOWN_SECONDS - elapsed)
    return False, 0


def response(status: str, window: str | None = None, job_id: str | None = None, reason: str | None = None, retry_after_seconds: int | None = None) -> dict[str, Any]:
    accepted = status == "accepted"
    data: dict[str, Any] = {
        "accepted": accepted,
        "status": status,
        "window": window,
        "mode": ALLOWED_MODE,
        "line_attempted": False,
        "email_attempted": False,
        "trading_or_order_executed": False,
        "scheduler_changed": False,
    }
    if job_id:
        data["job_id"] = job_id
        data["status_url"] = f"/stock-ai-dashboard/api/manual-rerun/status?job_id={job_id}"
    if reason:
        data["reason"] = reason
    if retry_after_seconds is not None:
        data["retry_after_seconds"] = retry_after_seconds
    return data


def write_audit(data: dict[str, Any]) -> None:
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_LATEST.write_text(stable(data), encoding="utf-8")
    if data.get("job_id"):
        (MANUAL_DIR / f"manual_rerun_{data['job_id']}.json").write_text(stable(data), encoding="utf-8")
    STATUS_LATEST.write_text(stable({
        "schema_version": "manual_rerun_status_v1",
        "job_id": data.get("job_id"),
        "requested_window": data.get("requested_window"),
        "status": data.get("status"),
        "requested_at": data.get("requested_at"),
        "finished_at": data.get("finished_at"),
        "line_attempted": False,
        "email_attempted": False,
        "pin_recorded": False,
    }), encoding="utf-8")


def build_audit(job_id: str, window: str, status: str, auth: str, lock_acquired: bool, cooldown_checked: bool) -> dict[str, Any]:
    stamp = now()
    return {
        "schema_version": "manual_single_window_rerun_audit_v1",
        "task_id": "AI-DEV-162",
        "job_id": job_id,
        "requested_at": stamp,
        "started_at": stamp if status in {"accepted", "completed"} else None,
        "finished_at": stamp,
        "requested_window": window,
        "executed_window": window if status in {"accepted", "completed"} else None,
        "mode": ALLOWED_MODE,
        "status": status,
        "pipeline_status": "not_executed_in_repo_validation",
        "market": ALLOWED_WINDOWS[window]["market"],
        "dashboard_url": ALLOWED_WINDOWS[window]["dashboard_url"],
        "artifact_scope": ALLOWED_WINDOWS[window]["artifact_scope"],
        "backend_command": ALLOWED_WINDOWS[window]["backend_command"],
        "dashboard_publish_attempted": status in {"accepted", "completed"},
        "dashboard_publish_status": "simulated" if status in {"accepted", "completed"} else "not_attempted",
        "line_attempted": False,
        "email_attempted": False,
        "scheduler_changed": False,
        "production_pipeline_executed": False,
        "notification_policy": "manual_rerun_dashboard_refresh_only",
        "operator_auth": auth,
        "pin_recorded": False,
        "lock_acquired": lock_acquired,
        "cooldown_checked": cooldown_checked,
        "timeout_seconds": TIMEOUT_SECONDS,
        "safety_notes": ["single_window_only", "global_one_batch_lock", "six_digit_pin_verified" if auth == "verified" else "pin_not_verified", "no_line_email", "no_trading", "no_scheduler_change"]
    }


def handle_request(request: dict[str, Any], *, pin_hash_value: str | None = None, mock_lock_busy: bool = False, mock_cooldown: bool = False, write: bool = False) -> dict[str, Any]:
    window = request.get("window")
    ok_window, window_reason = validate_window(window)
    if not ok_window:
        return response(window_reason or "invalid_window", reason=window_reason or "invalid_window")
    assert isinstance(window, str)
    mode = request.get("mode", ALLOWED_MODE)
    ok_mode, mode_reason = validate_mode(mode)
    if not ok_mode:
        return response("rejected", window=window, reason=mode_reason or "mode_rejected")
    if request.get("confirm_single_window_only") is not True:
        return response("rejected", window=window, reason="single_window_confirmation_required")
    verified, auth_reason = verify_pin(str(request.get("pin", "")), pin_hash_value)
    if auth_reason == "invalid_pin_format":
        return response("invalid_pin_format", window=window, reason="invalid_pin_format")
    if auth_reason == "pin_not_configured":
        return response("manual_rerun_disabled", window=window, reason="pin_not_configured")
    if not verified:
        return response("unauthorized", window=window, reason="unauthorized")
    if lock_busy(window, mock_lock_busy=mock_lock_busy):
        return response("lock_busy", window=window, reason="another_manual_rerun_in_progress")
    cool, retry = cooldown_active(window, mock_cooldown=mock_cooldown)
    if cool:
        return response("cooldown_active", window=window, retry_after_seconds=retry)
    job_id = "manual-" + hashlib.sha256(f"{window}:{time.time()}".encode()).hexdigest()[:16]
    audit = build_audit(job_id, window, "completed", "verified", True, True)
    if write:
        write_audit(audit)
    return response("accepted", window=window, job_id=job_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual single-window Dashboard rerun handler. Disabled unless PIN hash is configured.")
    parser.add_argument("--window", required=True)
    parser.add_argument("--mode", default=ALLOWED_MODE)
    parser.add_argument("--pin", default="")
    parser.add_argument("--reason", default="manual dashboard rerun")
    parser.add_argument("--idempotency-key", default="")
    parser.add_argument("--mock-pin-hash")
    parser.add_argument("--mock-lock-busy", action="store_true")
    parser.add_argument("--mock-cooldown", action="store_true")
    parser.add_argument("--write-audit", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    configured_hash = args.mock_pin_hash or os.environ.get("STOCK_AI_MANUAL_RERUN_PIN_HASH")
    req = {"window": args.window, "mode": args.mode, "pin": args.pin, "confirm_single_window_only": True, "reason": args.reason, "idempotency_key": args.idempotency_key}
    out = handle_request(req, pin_hash_value=configured_hash, mock_lock_busy=args.mock_lock_busy, mock_cooldown=args.mock_cooldown, write=args.write_audit)
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if out.get("accepted") else 2


if __name__ == "__main__":
    raise SystemExit(main())
