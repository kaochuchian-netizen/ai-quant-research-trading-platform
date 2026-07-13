#!/usr/bin/env python3
"""Validate production scheduler Dashboard URL contract end to end."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.dashboard_url_registry import (  # noqa: E402
    get_tw_dashboard_url,
    get_us_dashboard_url,
    get_dashboard_url,
    is_legacy_dashboard_url,
)

TW_WINDOWS = ["pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500", "prediction_review_1500"]
US_WINDOWS = ["us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"]
OLD_URL = "http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html"
OLD_ROUTE = "dashboard/decision-intelligence/four-window-preview"
EVIDENCE_DIR = ROOT / "artifacts/runtime/production_scheduler_dashboard_url_contract"
LATEST_JSON = EVIDENCE_DIR / "production_scheduler_dashboard_url_contract_latest.json"
LATEST_MD = EVIDENCE_DIR / "production_scheduler_dashboard_url_contract_latest.md"

FORMAL_RUNTIME_FILES = [
    ROOT / "run_stock_analysis.sh",
    ROOT / "app/reports/multi_window_formatter.py",
    ROOT / "reports/line_short_formatter.py",
    ROOT / "scripts/orchestrator/approved_pre_open_delivery.py",
    ROOT / "scripts/orchestrator/approved_us_stock_delivery.py",
    ROOT / "scripts/orchestrator/build_line_four_batch_runtime_preview_v1.py",
    ROOT / "scripts/orchestrator/build_email_scheduled_delivery_preview_v1.py",
    ROOT / "scripts/orchestrator/build_tw_daily_tactical_runtime_v1.py",
]


def run_cmd(cmd: list[str], *, env: dict[str, str] | None = None, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(cmd, cwd=ROOT, env=merged, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"parse_error": type(exc).__name__, "path": str(path)}


def extract_url(text: str, expected: str) -> str | None:
    if expected in text:
        return expected
    if OLD_ROUTE in text:
        return OLD_URL
    return None


def validate_tw_window(window: str, python_bin: str) -> dict[str, Any]:
    out = Path(f"/tmp/ai_dev_174c_tw_{window}.json")
    log = Path(f"/tmp/ai_dev_174c_tw_{window}.log")
    env = {
        "STOCK_AI_APPROVED_DELIVERY": "1",
        "STOCK_AI_APPROVED_DELIVERY_DRY_RUN": "1",
        "STOCK_AI_SCHEDULER_WINDOW": window,
        "STOCK_AI_APPROVED_DELIVERY_OUTPUT": str(out),
        "STOCK_AI_SCHEDULER_LOG_PATH": str(log),
        "STOCK_AI_DASHBOARD_URL": OLD_URL,
        "PYTHON_BIN": python_bin,
    }
    proc = run_cmd(["bash", "run_stock_analysis.sh"], env=env)
    data = load_json(out)
    line = str(data.get("line_payload_preview", ""))
    email = str(data.get("email_payload_preview", ""))
    tw_url = get_tw_dashboard_url()
    return {
        "market": "TW",
        "window": window,
        "entrypoint": "run_stock_analysis.sh -> approved_pre_open_delivery.py --dry-run",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-500:],
        "stderr_tail": proc.stderr[-500:],
        "artifact": str(out),
        "line_dashboard_url": extract_url(line, tw_url),
        "email_dashboard_url": extract_url(email, tw_url),
        "line_has_expected_url": tw_url in line,
        "email_has_expected_url": tw_url in email,
        "line_has_legacy_url": is_legacy_dashboard_url(line),
        "email_has_legacy_url": is_legacy_dashboard_url(email),
        "line_attempted": data.get("line_delivery_status") not in {"dry_run_not_sent", "not_sent", None},
        "email_attempted": data.get("email_delivery_status") not in {"dry_run_not_sent", "not_sent", None},
        "trading_or_order_executed": bool(data.get("trading_order_portfolio_action")),
        "dashboard_url": data.get("dashboard_url"),
        "ok": proc.returncode == 0 and tw_url in line and tw_url in email and not is_legacy_dashboard_url(line + email) and data.get("line_delivery_status") == "dry_run_not_sent" and data.get("email_delivery_status") == "dry_run_not_sent" and not data.get("trading_order_portfolio_action"),
    }


def validate_us_window(window: str, python_bin: str) -> dict[str, Any]:
    out = Path(f"/tmp/ai_dev_174c_us_{window}.json")
    proc = run_cmd([python_bin, "scripts/orchestrator/approved_us_stock_delivery.py", "--window", window, "--dry-run", "--pretty", "--output", str(out)], timeout=300)
    try:
        data = json.loads(proc.stdout)
    except Exception:
        data = load_json(out)
    line = str(data.get("line_payload_preview") or data.get("status", {}).get("line_payload_preview", ""))
    email = str(data.get("email_payload_preview") or data.get("status", {}).get("email_payload_preview", ""))
    us_url = get_us_dashboard_url()
    status = data.get("status", {}) if isinstance(data.get("status"), dict) else {}
    return {
        "market": "US",
        "window": window,
        "entrypoint": "approved_us_stock_delivery.py --dry-run",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-500:],
        "stderr_tail": proc.stderr[-500:],
        "artifact": str(out),
        "line_dashboard_url": extract_url(line, us_url),
        "email_dashboard_url": extract_url(email, us_url),
        "line_has_expected_url": us_url in line,
        "email_has_expected_url": us_url in email,
        "line_has_legacy_url": is_legacy_dashboard_url(line),
        "email_has_legacy_url": is_legacy_dashboard_url(email),
        "line_attempted": bool(status.get("line_attempted")),
        "email_attempted": bool(status.get("email_attempted")),
        "trading_or_order_executed": bool(status.get("trading_or_order_executed")),
        "dashboard_url": data.get("dashboard_url") or status.get("dashboard_url"),
        "ok": proc.returncode == 0 and us_url in line and us_url in email and not is_legacy_dashboard_url(line + email) and not status.get("line_attempted") and not status.get("email_attempted") and not status.get("trading_or_order_executed"),
    }


def static_scan() -> dict[str, Any]:
    hits: dict[str, list[str]] = {}
    for path in FORMAL_RUNTIME_FILES:
        text = path.read_text(encoding="utf-8", errors="ignore")
        bad = [line.strip() for line in text.splitlines() if OLD_ROUTE in line or "four-window-preview/index.html" in line]
        if bad:
            hits[str(path.relative_to(ROOT))] = bad
    return {"ok": not hits, "legacy_hits": hits}


def write_evidence(result: dict[str, Any]) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = ["# Production Scheduler Dashboard URL Contract", ""]
    for item in result.get("controlled_scheduler_path_matrix", []):
        rows.append(f"- {item['market']} {item['window']}: LINE={item.get('line_dashboard_url')} Email={item.get('email_dashboard_url')} ok={item.get('ok')}")
    LATEST_MD.write_text("\n".join(rows) + "\n", encoding="utf-8")


def validate(python_bin: str) -> dict[str, Any]:
    errors: list[str] = []
    registry = {
        "tw_url": get_tw_dashboard_url(),
        "us_url": get_us_dashboard_url(),
        "tw_mapping": get_dashboard_url("TW") == get_tw_dashboard_url(),
        "us_mapping": get_dashboard_url("US") == get_us_dashboard_url(),
    }
    if not registry["tw_url"].endswith("/dashboard/tw/index.html"):
        errors.append("TW registry URL is not canonical")
    if not registry["us_url"].endswith("/dashboard/us/index.html"):
        errors.append("US registry URL is not canonical")
    if not registry["tw_mapping"] or not registry["us_mapping"]:
        errors.append("market mapping failed")

    scan = static_scan()
    if not scan["ok"]:
        errors.append("formal runtime code still contains legacy Dashboard route")

    matrix = [validate_tw_window(window, python_bin) for window in TW_WINDOWS]
    matrix.extend(validate_us_window(window, python_bin) for window in US_WINDOWS)
    for item in matrix:
        if not item.get("ok"):
            errors.append(f"scheduler-path payload failed: {item['market']} {item['window']}")

    artifact_checks = {
        "evidence_json": str(LATEST_JSON),
        "evidence_md": str(LATEST_MD),
        "legacy_url_in_matrix": any(item.get("line_has_legacy_url") or item.get("email_has_legacy_url") for item in matrix),
        "notification_attempted": any(item.get("line_attempted") or item.get("email_attempted") for item in matrix),
        "trading_or_order_executed": any(item.get("trading_or_order_executed") for item in matrix),
    }
    if artifact_checks["legacy_url_in_matrix"]:
        errors.append("generated scheduler-path payload contains legacy URL")
    if artifact_checks["notification_attempted"]:
        errors.append("no-send scheduler-path validation attempted notification")
    if artifact_checks["trading_or_order_executed"]:
        errors.append("scheduler-path validation executed trading/order")

    result = {
        "ok": not errors,
        "task_id": "AI-DEV-174C",
        "root_cause": "run_stock_analysis.sh passed a legacy --dashboard-url default into approved_pre_open_delivery.py, overriding the registry default fixed in AI-DEV-174B.",
        "why_ai_dev_174b_missed_it": "AI-DEV-174B validated controlled formatter payloads and approved delivery defaults, but did not execute the cron-equivalent run_stock_analysis.sh wrapper that injected the legacy URL.",
        "registry_contract": registry,
        "static_runtime_scan": scan,
        "controlled_scheduler_path_matrix": matrix,
        "artifact_result_checks": artifact_checks,
        "safety_checks": {
            "email_attempted": artifact_checks["notification_attempted"],
            "line_attempted": artifact_checks["notification_attempted"],
            "scheduler_changed": False,
            "python_main_executed": False,
            "production_approved_delivery_executed": False,
            "trading_or_order_executed": artifact_checks["trading_or_order_executed"],
            "secrets_read": False,
        },
        "errors": errors,
    }
    write_evidence(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--python-bin", default=str(ROOT / "venv/bin/python"))
    args = parser.parse_args()
    result = validate(args.python_bin)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
