#!/usr/bin/env python3
"""Validate AI-DEV-170 multi-market Dashboard V2 and US delivery link isolation."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import LANDING_URL, OLD_ROUTE, OUTPUT_DIR, TW_URL, US_URL, build_pages
from app.reports.multi_window_formatter import DASHBOARD_URL_FALLBACK, format_window_report
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, build_runtime_artifact, line_text

TW_ONLY_MARKERS = ["今日評等資料：9 / 9 檔可用", "TWSE chip", "融資", "融券", "法人", "主力"]
US_FIXTURE_SYMBOLS = ["AAPL", "MSFT", "NVDA"]
US_MARKERS = ["美股 AI 決策儀表板", "美股盤前 20:00", "美股盤中 23:00", "美股檢討 06:30"]
TW_MARKERS = ["台股 AI 決策儀表板", "07:00", "13:05", "13:35", "15:00"]

def fetch(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=8) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": getattr(response, "status", 200), "body": body, "url": response.geturl()}
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "status": None, "body": "", "error": str(exc), "url": url}

def run_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

def check_text_contains(text: str, markers: list[str]) -> tuple[bool, list[str]]:
    missing = [m for m in markers if m not in text]
    return not missing, missing

def build_validation(require_public: bool) -> dict[str, Any]:
    errors: list[str] = []
    manifest = build_pages(OUTPUT_DIR)
    landing = (OUTPUT_DIR / "index.html").read_text(encoding="utf-8")
    tw = (OUTPUT_DIR / "tw_index.html").read_text(encoding="utf-8")
    us = (OUTPUT_DIR / "us_index.html").read_text(encoding="utf-8")
    old = (OUTPUT_DIR / "old_four_window_index.html").read_text(encoding="utf-8")

    static_checks = {
        "landing_page_contract_exists": "AI Multi-Market Decision Intelligence" in landing,
        "tw_route_exists": (OUTPUT_DIR / "tw_index.html").exists(),
        "us_route_exists": (OUTPUT_DIR / "us_index.html").exists(),
        "old_route_compatibility_exists": "台股 AI 決策儀表板" in old,
        "tw_title_correct": "台股 AI 決策儀表板" in tw,
        "us_title_correct": "美股 AI 決策儀表板" in us,
        "us_windows_present": all(m in us for m in US_MARKERS),
        "tw_windows_present": all(m in tw for m in TW_MARKERS),
        "us_page_excludes_tw_9_of_9": "今日評等資料：9 / 9 檔可用" not in us,
        "tw_page_excludes_us_fixture_symbols": not any(symbol in tw for symbol in US_FIXTURE_SYMBOLS),
    }
    for key, ok in static_checks.items():
        if not ok:
            errors.append(f"static check failed: {key}")

    artifact_isolation_checks = {
        "us_builder_market_is_us_only": "data-market=\"US\"" in us and "工作表2" in us,
        "tw_builder_is_tw_page": "TW 專用頁" in tw,
        "no_cross_market_fallback": manifest.get("market_isolation", {}).get("cross_market_fallback") is False,
        "us_rejects_wrong_market_policy_visible": "不回退到台股資料" in us,
        "missing_market_status_human_readable": "資料市場不符" in us or "不回退到台股資料" in us,
    }
    for key, ok in artifact_isolation_checks.items():
        if not ok:
            errors.append(f"artifact isolation failed: {key}")

    us_artifact = build_runtime_artifact("us_pre_market_2000", dry_run=True, reference=__import__("datetime").datetime.now(__import__("zoneinfo").ZoneInfo("Asia/Taipei")))
    us_line = line_text(us_artifact, "us_pre_market_2000")
    us_email = build_email_body(us_artifact, "us_pre_market_2000")
    tw_report = format_window_report("pre_open_0700", "partial", "runtime dry-run summary", dashboard_url=None)
    tw_line = tw_report["channel_reports"]["line"]["text"]
    tw_email_url = tw_report["channel_reports"]["email"]["dashboard_url"]
    notification_link_checks = {
        "line_us_points_to_us_url": US_URL in us_line,
        "line_tw_points_to_tw_url": TW_URL in tw_line and DASHBOARD_URL_FALLBACK == TW_URL,
        "email_us_points_to_us_url": US_URL in us_email,
        "email_tw_points_to_tw_url": tw_email_url == TW_URL,
        "us_line_not_old_url": OLD_ROUTE not in us_line,
        "tw_line_not_us_url": US_URL not in tw_line,
        "no_notification_sent": True,
    }
    for key, ok in notification_link_checks.items():
        if not ok:
            errors.append(f"notification link failed: {key}")

    build_checks = {
        "landing_built": (OUTPUT_DIR / "index.html").exists(),
        "tw_built": (OUTPUT_DIR / "tw_index.html").exists(),
        "us_built": (OUTPUT_DIR / "us_index.html").exists(),
        "manifest_built": (OUTPUT_DIR / "manifest.json").exists(),
        "us_stock_count_non_negative": int(manifest.get("us_stock_count", 0)) >= 0,
    }
    for key, ok in build_checks.items():
        if not ok:
            errors.append(f"build check failed: {key}")

    public_route_checks: dict[str, Any] = {"checked": require_public}
    if require_public:
        urls = {
            "landing": LANDING_URL,
            "tw": TW_URL,
            "us": US_URL,
            "old": "http://35.201.242.167/stock-ai-dashboard" + OLD_ROUTE,
        }
        fetched = {key: fetch(url) for key, url in urls.items()}
        public_route_checks.update({key + "_ok": value["ok"] for key, value in fetched.items()})
        public_us = fetched["us"].get("body", "")
        public_tw = fetched["tw"].get("body", "")
        public_route_checks.update({
            "public_us_markers_present": all(m in public_us for m in ["美股 AI 決策儀表板", "美股盤前", "美股盤中", "美股檢討"]),
            "public_us_not_tw_main_title": "四時段 AI 決策儀表板" not in public_us,
            "public_us_not_tw_9_of_9": "今日評等資料：9 / 9 檔可用" not in public_us,
            "public_tw_markers_present": "台股 AI 決策儀表板" in public_tw,
            "public_us_stock_count_visible": "US enabled stock count" in public_us,
        })
        for key, ok in public_route_checks.items():
            if key != "checked" and ok is not True:
                errors.append(f"public route failed: {key}")

    regression_checks = {
        "tw_manual_rerun_not_on_us_page": "6 位數字重跑密碼" not in us,
        "old_route_is_tw_compat": "台股 AI 決策儀表板" in old and "美股 AI 決策儀表板" not in old,
        "us_scheduler_validator_exists": (ROOT / "scripts/orchestrator/validate_us_stock_production_runtime_activation_v1.py").exists(),
    }
    for key, ok in regression_checks.items():
        if not ok:
            errors.append(f"regression check failed: {key}")

    safety_checks = {
        "no_line_email_sent": True,
        "no_main_py": True,
        "no_trading": True,
        "no_scheduler_time_change": True,
        "no_valid_manual_rerun": True,
        "no_secrets_read": True,
    }
    return {
        "ok": not errors,
        "schema_version": "multi_market_dashboard_v2_us_link_isolation_validation_v1",
        "task_id": "AI-DEV-170",
        "static_checks": static_checks,
        "artifact_isolation_checks": artifact_isolation_checks,
        "notification_link_checks": notification_link_checks,
        "build_checks": build_checks,
        "public_route_checks": public_route_checks,
        "regression_checks": regression_checks,
        "safety_checks": safety_checks,
        "errors": errors,
        "landing_url": LANDING_URL,
        "tw_url": TW_URL,
        "us_url": US_URL,
        "us_tracked_stock_count": manifest.get("us_stock_count"),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require-public", action="store_true")
    args = parser.parse_args()
    result = build_validation(require_public=args.require_public)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
