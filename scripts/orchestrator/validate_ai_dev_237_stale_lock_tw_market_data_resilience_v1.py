#!/usr/bin/env python3
"""Validate AI-DEV-237 stale-lock recovery and TW market-data evidence."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import multiprocessing
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.market.shioaji_client import classify_shioaji_error, transport_failure_evidence
from app.us_stock.batch_reliability import acquire_pid_lock, channel_state, read_lock_owner, release_pid_lock


def _case(name: str, passed: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"case": name, "passed": bool(passed), "details": details or {}}


def _hold_lock(lock_path: str, queue: multiprocessing.Queue) -> None:
    path = Path(lock_path)
    result = acquire_pid_lock(path)
    queue.put(result)
    time.sleep(0.6)
    release_pid_lock(path)


def _acquire_once(lock_path: str, queue: multiprocessing.Queue) -> None:
    result = acquire_pid_lock(Path(lock_path))
    if result.get("acquired"):
        time.sleep(0.5)
        release_pid_lock(Path(lock_path))
    queue.put(result)


def validate_lock_contract() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="ai-dev-237-lock-") as raw:
        lock_path = Path(raw) / "batch.lock"

        lock_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
        live = acquire_pid_lock(lock_path)
        cases.append(_case(
            "live_lock_not_removed",
            live.get("acquired") is False
            and live.get("reason") == "live_lock_present"
            and lock_path.exists()
            and read_lock_owner(lock_path).get("owner_pid") == os.getpid(),
            live,
        ))
        lock_path.unlink()

        stale_pid = 99999999
        lock_path.write_text(f"{stale_pid}\n", encoding="utf-8")
        stale = acquire_pid_lock(lock_path)
        owner_after_stale = read_lock_owner(lock_path)
        cases.append(_case(
            "stale_lock_recovered_only_when_owner_dead",
            stale.get("acquired") is True
            and stale.get("recovered_stale") is True
            and owner_after_stale.get("owner_pid") == os.getpid(),
            stale,
        ))
        cases.append(_case("release_on_normal_exit", release_pid_lock(lock_path).get("released") is True and not lock_path.exists()))

        lock_path.write_text(f"{stale_pid}\n", encoding="utf-8")
        sigkill_residue = acquire_pid_lock(lock_path)
        cases.append(_case(
            "sigkill_oom_residue_recovers_as_stale_lock",
            sigkill_residue.get("acquired") is True and sigkill_residue.get("recovered_stale") is True,
            sigkill_residue,
        ))
        release_pid_lock(lock_path)

        queue: multiprocessing.Queue = multiprocessing.Queue()
        holder = multiprocessing.Process(target=_hold_lock, args=(str(lock_path), queue))
        holder.start()
        first = queue.get(timeout=5)
        second = acquire_pid_lock(lock_path)
        holder.join(timeout=5)
        cases.append(_case(
            "concurrent_live_lock_blocks_second_acquisition",
            first.get("acquired") is True
            and second.get("acquired") is False
            and second.get("reason") == "live_lock_present",
            {"first": first, "second": second},
        ))

        queue = multiprocessing.Queue()
        workers = [multiprocessing.Process(target=_acquire_once, args=(str(lock_path), queue)) for _ in range(4)]
        for worker in workers:
            worker.start()
        results = [queue.get(timeout=5) for _ in workers]
        for worker in workers:
            worker.join(timeout=5)
        acquired_count = sum(1 for item in results if item.get("acquired"))
        cases.append(_case(
            "atomic_concurrent_acquisition_single_owner",
            acquired_count == 1,
            {"acquired_count": acquired_count, "results": results},
        ))

        duplicate = channel_state(attempted=False, succeeded=False, reason="duplicate_delivery_suppressed")
        cases.append(_case(
            "no_duplicate_delivery_state_not_attempted",
            duplicate["state"] == "suppressed" and duplicate["attempted"] is False and duplicate["sent"] is False,
            duplicate,
        ))
    return cases


def validate_tw_market_data_evidence() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    class FakeDnsError(OSError):
        pass

    class FakeTransportError(RuntimeError):
        pass

    dns = FakeDnsError("getaddrinfo failed for api.shioaji.example")
    provider = FakeTransportError("TransportError: Response Code: 503 from Solace transport")
    dns_evidence = transport_failure_evidence(dns, provider="shioaji", stage="login")
    provider_evidence = transport_failure_evidence(provider, provider="shioaji", stage="kbars_fetch")
    cases.append(_case(
        "tw_dns_failure_classified",
        dns_evidence.get("failure_kind") == "dns_failure"
        and classify_shioaji_error(dns) == "shioaji_dns_failure",
        dns_evidence,
    ))
    cases.append(_case(
        "tw_provider_api_failure_classified",
        provider_evidence.get("failure_kind") == "provider_api_failure"
        and classify_shioaji_error(provider) == "shioaji_provider_api_failure",
        provider_evidence,
    ))

    import scripts.update_historical_csv as updater

    original_get_api = updater.get_api
    try:
        def _raise_transport_error() -> Any:
            raise provider

        updater.get_api = _raise_transport_error
        with contextlib.redirect_stdout(io.StringIO()):
            result = updater.main(
                raise_on_failure=False,
                stock_ids=["2330"],
                universe_evidence={"source": "validator_fixture", "market": "TW", "stock_count": 1, "fallback_used": False},
                yfinance_downloader=lambda *_, **__: None,
            )
    finally:
        updater.get_api = original_get_api

    evidence = result.get("transport_failure_evidence") or []
    warnings = result.get("warnings") or []
    cases.append(_case(
        "tw_updater_persists_transport_failure_evidence",
        bool(evidence)
        and evidence[0].get("failure_kind") == "provider_api_failure"
        and warnings
        and "transport_failure_evidence" in warnings[0],
        {"evidence": evidence, "warnings": warnings[:1]},
    ))
    cases.append(_case(
        "tw_timeout_retry_contract_preserved",
        result.get("fallback_policy", {}).get("enabled") is True
        and result.get("fallback_policy", {}).get("bounded_kbars_window_days") == 180
        and result.get("fallback_policy", {}).get("crash_pipeline_on_shioaji_failure") is False,
        result.get("fallback_policy", {}),
    ))
    return cases


def validate_source_markers() -> list[dict[str, Any]]:
    runner = (ROOT / "scripts/orchestrator/approved_us_stock_delivery.py").read_text(encoding="utf-8")
    shioaji = (ROOT / "app/market/shioaji_client.py").read_text(encoding="utf-8")
    updater = (ROOT / "scripts/update_historical_csv.py").read_text(encoding="utf-8")
    registry = (ROOT / "config/governance/validator_registry_v1.json").read_text(encoding="utf-8")
    return [
        _case("runner_uses_atomic_pid_lock_helper", "acquire_pid_lock" in runner and "release_pid_lock" in runner and "LOCK_PATH.exists()" not in runner),
        _case("runner_installs_sigterm_cleanup", "signal.SIGTERM" in runner and "install_lock_signal_cleanup" in runner),
        _case("tw_transport_evidence_schema_exists", "tw_market_data_transport_failure_evidence_v1" in shioaji),
        _case("tw_transport_failure_kinds_distinguished", all(token in shioaji for token in ["dns_failure", "connect_failure", "http_failure", "provider_api_failure"])),
        _case("tw_updater_persists_evidence_without_policy_change", "transport_failure_evidence" in updater and "crash_pipeline_on_shioaji_failure" in updater),
        _case("governance_registry_includes_ai_dev_237", "ai_dev_237_stale_lock_tw_market_data_resilience_v1" in registry),
    ]


def validate() -> dict[str, Any]:
    cases = []
    cases.extend(validate_lock_contract())
    cases.extend(validate_tw_market_data_evidence())
    cases.extend(validate_source_markers())
    failed = [case for case in cases if not case.get("passed")]
    return {
        "schema_version": "ai_dev_237_stale_lock_tw_market_data_resilience_validator_v1",
        "task_id": "AI-DEV-237",
        "ok": not failed,
        "passed": len(cases) - len(failed),
        "total": len(cases),
        "cases": cases,
        "failed_cases": failed,
        "safety": {
            "production_pipeline_run": False,
            "line_sent": False,
            "email_sent": False,
            "db_or_sheet_written": False,
            "scheduler_modified": False,
            "runtime_artifact_modified": False,
            "trading_or_order_executed": False,
        },
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
