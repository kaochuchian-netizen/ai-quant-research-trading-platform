#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.orchestrator.manual_rerun_single_window import (  # noqa: E402
    ALLOWED_MODE,
    ALLOWED_WINDOWS,
    build_audit,
    handle_request,
    pin_hash,
    stable,
    write_audit,
)

OUT = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_simulation_latest.json"
MOCK_PIN = "".join(("31", "41", "59"))
MOCK_HASH = pin_hash(MOCK_PIN)


def req(window: object, pin: str = MOCK_PIN, mode: str = ALLOWED_MODE, confirm: bool = True) -> dict[str, object]:
    return {"window": window, "mode": mode, "pin": pin, "confirm_single_window_only": confirm, "reason": "manual dashboard rerun", "idempotency_key": "simulation"}


def run() -> dict[str, object]:
    cases: dict[str, dict[str, object]] = {}
    for window in ALLOWED_WINDOWS:
        cases[f"valid_{window}"] = handle_request(req(window), pin_hash_value=MOCK_HASH)
    cases["invalid_all_windows"] = handle_request(req("all"), pin_hash_value=MOCK_HASH)
    cases["invalid_unknown_window"] = handle_request(req("opening_bell"), pin_hash_value=MOCK_HASH)
    cases["invalid_array_windows"] = handle_request(req(["pre_open_0700", "intraday_1305"]), pin_hash_value=MOCK_HASH)
    cases["missing_pin"] = handle_request(req("pre_open_0700", pin=""), pin_hash_value=MOCK_HASH)
    cases["non_digit_pin"] = handle_request(req("pre_open_0700", pin="abc123"), pin_hash_value=MOCK_HASH)
    cases["short_pin"] = handle_request(req("pre_open_0700", pin="12345"), pin_hash_value=MOCK_HASH)
    cases["long_pin"] = handle_request(req("pre_open_0700", pin="1234567"), pin_hash_value=MOCK_HASH)
    cases["wrong_pin"] = handle_request(req("pre_open_0700", pin="".join(("27", "18", "28"))), pin_hash_value=MOCK_HASH)
    cases["missing_pin_config"] = handle_request(req("pre_open_0700"), pin_hash_value=None)
    cases["cooldown_active"] = handle_request(req("pre_open_0700"), pin_hash_value=MOCK_HASH, mock_cooldown=True)
    cases["lock_busy"] = handle_request(req("pre_open_0700"), pin_hash_value=MOCK_HASH, mock_lock_busy=True)
    cases["invalid_mode_send_line"] = handle_request(req("pre_open_0700", mode="send_line"), pin_hash_value=MOCK_HASH)
    cases["invalid_mode_full_delivery"] = handle_request(req("pre_open_0700", mode="full_delivery"), pin_hash_value=MOCK_HASH)
    cases["timeout_model"] = {"accepted": False, "status": "timed_out", "line_attempted": False, "email_attempted": False, "trading_or_order_executed": False, "timeout_seconds": 600}

    audit = build_audit("manual-simulation", "intraday_1305", "completed", "verified", True, True)
    write_audit(audit)
    result = {
        "schema_version": "dashboard_manual_single_window_rerun_simulation_v1",
        "task_id": "AI-DEV-162",
        "ok": all(c.get("accepted") is True for k, c in cases.items() if k.startswith("valid_"))
        and all(c.get("accepted") is not True for k, c in cases.items() if not k.startswith("valid_")),
        "cases": cases,
        "mock_pin_plaintext_recorded": False,
        "actual_line_sent": False,
        "actual_email_sent": False,
        "db_write": False,
        "scheduler_modified": False,
        "production_pipeline_executed": False,
        "python_main_executed": False,
        "trading_or_order_executed": False,
        "audit_path": "artifacts/runtime/manual_rerun/manual_rerun_latest.json",
        "status_path": "artifacts/runtime/manual_rerun/manual_rerun_status_latest.json",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(stable(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
