#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-174A pre-open timeout recovery guard.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    reasons: list[str] = []
    shioaji = read("app/market/shioaji_client.py")
    pre_open = read("app/pipelines/pre_open_pipeline.py")
    run_stock = read("run_stock_analysis.sh")

    checks = {
        "shioaji_get_api_process_cached": "@lru_cache(maxsize=1)" in shioaji and "def get_api" in shioaji,
        "shioaji_contracts_timeout_configured": "contracts_timeout=_contracts_timeout_ms()" in shioaji,
        "stage_timing_artifact_declared": "pre_open_stage_timing_latest.json" in pre_open,
        "stage_timing_historical_update": "stage_timing.start(\"historical_csv_update\")" in pre_open,
        "stage_timing_stock_analysis": "stage_name = f\"stock_analysis_{stock_id}\"" in pre_open,
        "stage_timing_missing_csv_finished": "reason=\"missing_historical_csv\"" in pre_open,
        "stdout_flush_for_initial_markers": "pipeline_run_id" in pre_open and "flush=True" in pre_open,
        "scheduler_entry_still_wrapper": "approved_pre_open_delivery.py" in run_stock,
        "no_main_py_entrypoint": "python3 main.py" not in run_stock and "main.py" not in pre_open,
        "no_delivery_policy_change": "send_reports_in_batches" in pre_open and "format_line_short" in pre_open,
    }
    for key, ok in checks.items():
        if not ok:
            reasons.append(key)

    result = {
        "ok": not reasons,
        "schema_version": "pre_open_pipeline_timeout_recovery_validation_v1",
        "checks": checks,
        "reasons": reasons,
        "safety": {
            "notification_sent": False,
            "scheduler_modified": False,
            "production_pipeline_executed": False,
            "python_main_executed": False,
            "trading_or_order_executed": False,
            "secrets_read": False,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
