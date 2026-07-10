#!/usr/bin/env python3
"""Deploy or inspect AI-DEV-169 US stock production cron schedule."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = REPO_ROOT / "venv/bin/python"
RUNNER = REPO_ROOT / "scripts/orchestrator/approved_us_stock_delivery.py"
LOG_DIR = REPO_ROOT / "logs/us_stock"
MARKER_BEGIN = "# STOCK-AI-US-BATCH-BEGIN AI-DEV-169"
MARKER_END = "# STOCK-AI-US-BATCH-END AI-DEV-169"
TAIPEI = ZoneInfo("Asia/Taipei")
ENTRIES = [
    ("0 20 * * 1-5", "us_pre_market_2000", "us_pre_market_2000.log"),
    ("0 23 * * 1-5", "us_intraday_2300", "us_intraday_2300.log"),
    ("30 6 * * 2-6", "us_post_close_review_0630", "us_post_close_review_0630.log"),
]

def run_cmd(args: list[str], input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=input_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

def current_crontab() -> str:
    proc = run_cmd(["crontab", "-l"])
    if proc.returncode != 0:
        return ""
    return proc.stdout

def managed_block() -> str:
    lines = [MARKER_BEGIN]
    for cron_expr, window, log_name in ENTRIES:
        lines.append(f"{cron_expr} cd {REPO_ROOT} && {PYTHON} {RUNNER} --window {window} --production-approved >> {LOG_DIR / log_name} 2>&1")
    lines.append(MARKER_END)
    return "\n".join(lines) + "\n"

def remove_block(text: str) -> str:
    if MARKER_BEGIN not in text or MARKER_END not in text:
        return text.rstrip() + ("\n" if text.strip() else "")
    before = text.split(MARKER_BEGIN, 1)[0].rstrip()
    after = text.split(MARKER_END, 1)[1].strip()
    pieces = [p for p in [before, after] if p]
    return "\n".join(pieces) + ("\n" if pieces else "")

def next_trigger(hour: int, minute: int, weekdays: set[int]) -> str:
    now = datetime.now(TAIPEI).replace(second=0, microsecond=0)
    for offset in range(0, 14):
        day = now + timedelta(days=offset)
        candidate = day.replace(hour=hour, minute=minute)
        if candidate <= now:
            continue
        # Python Monday=0; cron Monday=1, Saturday=6.
        cron_weekday = candidate.weekday() + 1
        if cron_weekday in weekdays:
            return candidate.isoformat()
    return "unavailable"

def next_triggers() -> dict[str, str]:
    return {
        "us_pre_market_2000": next_trigger(20, 0, {1,2,3,4,5}),
        "us_intraday_2300": next_trigger(23, 0, {1,2,3,4,5}),
        "us_post_close_review_0630": next_trigger(6, 30, {2,3,4,5,6}),
    }

def validate_no_duplicate_us_entries(text: str) -> bool:
    return text.count(str(RUNNER)) <= len(ENTRIES)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    current = current_crontab()
    cleaned = remove_block(current)
    if args.rollback:
        desired = cleaned
        action = "rollback"
    else:
        desired = cleaned + managed_block()
        action = "apply" if args.apply else "dry_run"
    changed = desired != current
    applied = False
    errors: list[str] = []
    if args.apply or args.rollback:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        backup = REPO_ROOT / "artifacts/runtime/us_stock/us_stock_crontab_backup_latest.txt"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(current, encoding="utf-8")
        proc = run_cmd(["crontab", "-"], input_text=desired)
        applied = proc.returncode == 0
        if not applied:
            errors.append(proc.stderr.strip() or proc.stdout.strip() or "crontab apply failed")
    result = {
        "ok": not errors,
        "action": action,
        "applied": applied,
        "changed": changed,
        "cron_modified": applied,
        "systemd_modified": False,
        "timer_modified": False,
        "service_modified": False,
        "scheduler_entries": [{"cron": c, "window": w, "log": str(LOG_DIR / log)} for c,w,log in ENTRIES],
        "next_triggers_asia_taipei": next_triggers(),
        "no_duplicate_active_scheduler_entries": validate_no_duplicate_us_entries(desired),
        "uses_main_py": False,
        "line_email_sent_during_deploy": False,
        "secrets_printed": False,
        "rollback_command": f"cd {REPO_ROOT} && {PYTHON} scripts/orchestrator/deploy_us_stock_production_runtime_v1.py --rollback --pretty",
        "errors": errors,
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
