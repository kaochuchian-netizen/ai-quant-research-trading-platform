#!/usr/bin/env python3
"""Validate AI-DEV-236 US batch execution reliability contract."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.us_stock.batch import build_us_stock_batch_artifact, us_stock_batch_input_example
from app.us_stock.batch_reliability import (
    CONTRACT_WINDOWS,
    US_BATCH_EXECUTION_RELIABILITY_CONTRACT,
    behavioral_contract_cases,
    build_failure_status,
    channel_state,
    memory_profile_fixture,
    validate_runtime_identity,
    validate_status,
)


def _case(name: str, passed: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"case": name, "passed": bool(passed), "details": details or {}}


def _worker_command(mode: str) -> list[str]:
    script = (
        "import json, os, signal, sys, time; "
        f"mode={mode!r}; "
        "\nif mode == 'ok': print(json.dumps({'ok': True, 'status': {'status': 'completed'}})); sys.exit(0)"
        "\nif mode == 'fail': print('worker failed', file=sys.stderr); sys.exit(2)"
        "\nif mode == 'sleep': time.sleep(2); sys.exit(0)"
        "\nif mode == 'sigkill': os.kill(os.getpid(), signal.SIGKILL)"
    )
    return [sys.executable, "-c", script]


def _simulate_worker_boundary() -> list[dict[str, Any]]:
    started = datetime.fromisoformat("2026-09-08T20:00:01+08:00")
    cases: list[dict[str, Any]] = []
    ok = subprocess.run(_worker_command("ok"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    cases.append(_case("worker_normal_json_completed", ok.returncode == 0 and json.loads(ok.stdout)["ok"] is True))
    fail = subprocess.run(_worker_command("fail"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    fail_status = build_failure_status(
        window="us_pre_market_2000",
        started_at=started,
        finished_at=datetime.fromisoformat("2026-09-08T20:01:00+08:00"),
        reason="worker_failed",
        error_type="WorkerProcessFailed",
        error_message=fail.stderr,
        returncode=fail.returncode,
    )
    cases.append(_case("worker_nonzero_fail_closed", fail.returncode != 0 and not validate_status(fail_status), fail_status))
    killed = subprocess.run(_worker_command("sigkill"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    killed_status = build_failure_status(
        window="us_pre_market_2000",
        started_at=started,
        finished_at=datetime.fromisoformat("2026-09-08T21:06:27+08:00"),
        reason="worker_terminated_signal",
        error_type="WorkerProcessFailed",
        returncode=killed.returncode,
    )
    cases.append(_case("worker_sigkill_oom_equivalent_fail_closed", killed.returncode < 0 and killed_status.get("signal") == "SIG9" and not validate_status(killed_status), killed_status))
    timed_out = False
    try:
        subprocess.run(_worker_command("sleep"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=0.1, check=False)
    except subprocess.TimeoutExpired:
        timed_out = True
    timeout_status = build_failure_status(
        window="us_pre_market_2000",
        started_at=started,
        finished_at=datetime.fromisoformat("2026-09-08T21:15:01+08:00"),
        reason="worker_timeout",
        error_type="TimeoutExpired",
        timeout_seconds=1,
    )
    cases.append(_case("worker_timeout_fail_closed", timed_out and not validate_status(timeout_status), timeout_status))
    return cases


def _runtime_cases() -> list[dict[str, Any]]:
    payload = us_stock_batch_input_example()
    expected_symbols = ["AAPL", "MSFT", "NVDA"]
    runtime_20 = build_us_stock_batch_artifact(payload, window="us_pre_market_2000")
    runtime_20["effective_trading_date"] = "2026-09-08"
    runtime_23 = build_us_stock_batch_artifact(payload, window="us_intraday_2300")
    runtime_23["effective_trading_date"] = "2026-09-08"
    stale = {**runtime_20, "effective_trading_date": "2026-09-07"}
    return [
        _case("20_runtime_symbol_order", not validate_runtime_identity(runtime_20, expected_window="us_pre_market_2000", expected_trading_date="2026-09-08", expected_symbols=expected_symbols)),
        _case("23_runtime_symbol_order", not validate_runtime_identity(runtime_23, expected_window="us_intraday_2300", expected_trading_date="2026-09-08", expected_symbols=expected_symbols)),
        _case("wrong_date_runtime_rejected", "runtime_effective_trading_date_mismatch" in validate_runtime_identity(stale, expected_window="us_pre_market_2000", expected_trading_date="2026-09-08", expected_symbols=expected_symbols)),
    ]


def _idempotency_cases() -> list[dict[str, Any]]:
    first_email = channel_state(attempted=True, succeeded=True)
    duplicate_email = channel_state(attempted=False, succeeded=False, reason="duplicate_delivery_suppressed")
    partial_email = channel_state(attempted=True, succeeded=False, reason="smtp_failed")
    line_23 = channel_state(attempted=False, succeeded=False, reason="line_not_allowed_for_window")
    return [
        _case("sent_implies_attempted", first_email["sent"] and first_email["attempted"]),
        _case("duplicate_retry_not_attempted", duplicate_email["state"] == "suppressed" and not duplicate_email["attempted"]),
        _case("partial_channel_failure_truthful", partial_email["attempted"] and not partial_email["sent"] and partial_email["state"] == "failed"),
        _case("us_2300_line_not_attempted_by_policy", line_23["state"] == "not_attempted" and not line_23["attempted"]),
    ]


def validate() -> dict[str, Any]:
    cases = []
    cases.extend(behavioral_contract_cases())
    cases.extend(_simulate_worker_boundary())
    cases.extend(_runtime_cases())
    cases.extend(_idempotency_cases())
    memory = memory_profile_fixture()
    def named_case_set(names: set[str]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        for case in cases:
            name = case["case"]
            if name in names and name not in seen:
                selected.append(case)
                seen.add(name)
        return selected

    contract_cases = named_case_set({
        "20_normal_contract_defined",
        "23_normal_contract_defined",
        "20_worker_oom_equivalent_fail_closed",
        "20_timeout_fail_closed",
        "20_failure_does_not_mutate_23_contract",
        "23_line_not_allowed_email_allowed",
        "partial_channel_failure_truthful",
        "retry_after_delivery_suppressed",
        "sent_implies_attempted",
        "tw_isolation",
    })
    worker_cases = [case for case in cases if case["case"].startswith("worker_")]
    runtime_cases = [case for case in cases if "runtime" in case["case"] or "wrong_date" in case["case"]]
    idempotency_cases = named_case_set({
        "duplicate_retry_not_attempted",
        "partial_channel_failure_truthful",
        "sent_implies_attempted",
        "us_2300_line_not_attempted_by_policy",
    })
    failed = [case for case in cases if not case.get("passed")]
    return {
        "ok": not failed,
        "passed": not failed,
        "task_id": "AI-DEV-236",
        "contract_name": "US_BATCH_EXECUTION_RELIABILITY_CONTRACT",
        "windows": list(CONTRACT_WINDOWS),
        "contract": {key: value.to_dict() for key, value in US_BATCH_EXECUTION_RELIABILITY_CONTRACT.items()},
        "counts": {
            "overall_passed": sum(1 for case in cases if case.get("passed")),
            "overall_total": len(cases),
            "contract_passed": sum(1 for case in contract_cases if case.get("passed")),
            "contract_total": len(contract_cases),
            "worker_boundary_passed": sum(1 for case in worker_cases if case.get("passed")),
            "worker_boundary_total": len(worker_cases),
            "runtime_identity_passed": sum(1 for case in runtime_cases if case.get("passed")),
            "runtime_identity_total": len(runtime_cases),
            "notification_idempotency_passed": sum(1 for case in idempotency_cases if case.get("passed")),
            "notification_idempotency_total": len(idempotency_cases),
        },
        "cases": cases,
        "memory_profile": memory,
        "production_only_blockers": [
            "23:00 scheduler absence requires read-only VM-local cron/journal evidence; do not encode infra workaround in app code.",
            "Production OOM ownership requires VM-local us_stock log and resource telemetry; offline fixture path is not memory-representative.",
        ],
        "safety": {
            "production_pipeline_run": False,
            "line_sent": False,
            "email_sent": False,
            "db_or_sheet_written": False,
            "scheduler_modified": False,
            "runtime_artifact_modified": False,
            "trading_or_order_executed": False,
        },
        "failed_cases": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
