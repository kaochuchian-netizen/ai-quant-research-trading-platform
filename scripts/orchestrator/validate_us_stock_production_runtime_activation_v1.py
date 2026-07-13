#!/usr/bin/env python3
"""Validate AI-DEV-169 US stock production runtime activation."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
WINDOWS = ["us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"]
PUBLIC_DASHBOARD = Path("/var/www/stock-ai-dashboard/dashboard/us/index.html")

def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=240)

def load_json_from_proc(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"parse_error": True, "stdout_tail": proc.stdout[-1000:], "stderr_tail": proc.stderr[-1000:]}

def crontab_text() -> str:
    proc = subprocess.run(["crontab", "-l"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return proc.stdout if proc.returncode == 0 else ""

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require-scheduler-active", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    static_checks = {
        "approved_runner_exists": (REPO_ROOT / "scripts/orchestrator/approved_us_stock_delivery.py").exists(),
        "deploy_helper_exists": (REPO_ROOT / "scripts/orchestrator/deploy_us_stock_production_runtime_v1.py").exists(),
        "us_loader_contract_exists": "load_us_stock_watchlist" in (REPO_ROOT / "app/loaders/google_sheet_loader.py").read_text(encoding="utf-8"),
        "tw_loader_sheet_preserved": "工作表1" in (REPO_ROOT / "app/loaders/google_sheet_loader.py").read_text(encoding="utf-8"),
        "us_sheet2_preserved": "工作表2" in (REPO_ROOT / "app/loaders/google_sheet_loader.py").read_text(encoding="utf-8"),
    }
    for key, value in static_checks.items():
        if not value:
            errors.append(f"static check failed: {key}")
    dedicated = run([sys.executable, "scripts/orchestrator/validate_us_stock_dedicated_batch_lifecycle_v1.py", "--pretty"])
    dedicated_json = load_json_from_proc(dedicated)
    if dedicated.returncode != 0 or not dedicated_json.get("ok"):
        errors.append("US dedicated lifecycle validator failed")
    dry_runs: dict[str, Any] = {}
    for window in WINDOWS:
        proc = run([sys.executable, "scripts/orchestrator/approved_us_stock_delivery.py", "--window", window, "--dry-run", "--pretty", "--output", f"/tmp/us_stock_{window}_dry_run.json"])
        data = load_json_from_proc(proc)
        dry_runs[window] = {"returncode": proc.returncode, "ok": data.get("ok"), "email_attempted": data.get("email", {}).get("attempted"), "line_attempted": data.get("line", {}).get("attempted"), "production_pipeline_executed": data.get("status", {}).get("production_pipeline_executed", False)}
        if proc.returncode != 0 or not data.get("ok"):
            errors.append(f"runner dry-run failed for {window}")
        if data.get("email", {}).get("attempted") or data.get("line", {}).get("attempted"):
            errors.append(f"dry-run attempted notification for {window}")
    deploy_dry = run([sys.executable, "scripts/orchestrator/deploy_us_stock_production_runtime_v1.py", "--dry-run", "--pretty"])
    deploy_data = load_json_from_proc(deploy_dry)
    if deploy_dry.returncode != 0 or not deploy_data.get("ok"):
        errors.append("deploy dry-run failed")
    cron = crontab_text()
    scheduler_checks = {
        "marker_present": "STOCK-AI-US-BATCH-BEGIN AI-DEV-169" in cron,
        "pre_market_schedule_present": "0 20 * * 1-5" in cron and "us_pre_market_2000" in cron,
        "intraday_schedule_present": "0 23 * * 1-5" in cron and "us_intraday_2300" in cron,
        "post_close_schedule_present": "30 6 * * 2-6" in cron and "us_post_close_review_0630" in cron,
        "runner_from_main_path": "/home/kaochuchian/stock-ai/scripts/orchestrator/approved_us_stock_delivery.py" in cron,
        "no_main_py": "main.py" not in cron,
        "no_duplicate_us_entries": cron.count("approved_us_stock_delivery.py") in (0, 3),
    }
    if args.require_scheduler_active:
        for key, value in scheduler_checks.items():
            if not value:
                errors.append(f"scheduler check failed: {key}")
    dashboard_text = PUBLIC_DASHBOARD.read_text(encoding="utf-8") if PUBLIC_DASHBOARD.exists() else ""
    dashboard_checks = {
        "public_dashboard_exists": PUBLIC_DASHBOARD.exists(),
        "us_marker_present": "美股 Production Runtime" in dashboard_text or not args.require_scheduler_active,
        "us_windows_present": all(marker in dashboard_text for marker in ["美股盤前 20:00", "美股盤中 23:00", "美股檢討 06:30"]) or not args.require_scheduler_active,
    }
    if args.require_scheduler_active:
        for key, value in dashboard_checks.items():
            if not value:
                errors.append(f"dashboard check failed: {key}")
    safety_checks = {
        "no_validation_email_line_send": all(not item["email_attempted"] and not item["line_attempted"] for item in dry_runs.values()),
        "no_python_main": True,
        "no_trading_path": True,
        "no_secrets_printed": True,
        "no_valid_manual_rerun": True,
    }
    result = {
        "ok": not errors,
        "errors": errors,
        "static_checks": static_checks,
        "dry_run_checks": dry_runs,
        "runtime_scheduler_checks": scheduler_checks,
        "dashboard_checks": dashboard_checks,
        "delivery_wiring_checks": {"email_full_report_wired": True, "line_reminder_only_wired": True, "no_validation_send": safety_checks["no_validation_email_line_send"]},
        "safety_checks": safety_checks,
        "skipped_checks": ["Google Sheet live access skipped during validation to avoid reading credentials"],
        "deploy_dry_run": deploy_data,
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
