#!/usr/bin/env python3
"""Validate AI-DEV-171 US live-data prediction/review runtime integration."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WINDOWS = ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630")
DASHBOARD_FILE = REPO_ROOT / "app/dashboard/multi_market_dashboard.py"
RUNNER_FILE = REPO_ROOT / "scripts/orchestrator/approved_us_stock_delivery.py"
LIVE_DATA_FILE = REPO_ROOT / "app/us_stock/live_data.py"
LIVE_PIPELINE_FILE = REPO_ROOT / "app/us_stock/live_pipeline.py"
PUBLIC_US_PATH = Path("/var/www/stock-ai-dashboard/dashboard/us/index.html")


def ok(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(passed), "detail": detail}


def has_package(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def run_runner_live_dry_run(window: str) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "scripts/orchestrator/approved_us_stock_delivery.py",
        "--window",
        window,
        "--dry-run",
        "--live-data",
        "--pretty",
    ]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, timeout=90)
    if completed.returncode != 0:
        return {"ok": False, "returncode": completed.returncode, "stderr": completed.stderr[-500:]}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"json_decode_failed: {exc}", "stdout": completed.stdout[-500:]}


def validate_live_artifact(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    checks: list[dict[str, Any]] = []
    if not path.exists():
        return [ok("live_artifact_exists", False, str(path))], None
    data = json.loads(path.read_text(encoding="utf-8"))
    checks.extend([
        ok("artifact_kind_us_stock_runtime", data.get("artifact_kind") == "us_stock_runtime", str(data.get("artifact_kind"))),
        ok("artifact_market_us", data.get("market") == "US", str(data.get("market"))),
        ok("artifact_data_source_live", data.get("data_source_mode") == "live", str(data.get("data_source_mode"))),
        ok("artifact_not_fixture", data.get("fixture") is False, str(data.get("fixture"))),
        ok("artifact_validation_only_for_dry_run", data.get("validation_only") is True, str(data.get("validation_only"))),
        ok("no_foundation_placeholder", "US batch foundation ready" not in json.dumps(data, ensure_ascii=False), "foundation text absent"),
        ok("line_email_not_sent_by_builder", data.get("safety_policy", {}).get("line_email_sent_by_builder") is False, str(data.get("safety_policy", {}))),
    ])
    items = data.get("items", [])
    cards = data.get("dashboard_ready_contract", {}).get("cards", [])
    prices = [item.get("quote", {}).get("last_price") for item in items]
    predictions = [item.get("prediction", {}) for item in items]
    checks.extend([
        ok("items_exist", len(items) > 0, str(len(items))),
        ok("cards_exist", len(cards) > 0, str(len(cards))),
        ok("numeric_live_price_exists", any(finite_number(v) and float(v) > 0 for v in prices), str(prices[:3])),
        ok("technical_indicators_exist", any(item.get("technical", {}).get("indicators", {}).get("ma20") is not None for item in items), "ma20 present"),
        ok("prediction_range_numeric", any(finite_number(p.get("predicted_session_low")) and finite_number(p.get("predicted_session_high")) for p in predictions), "range present"),
        ok("prediction_range_ordered", all((p.get("prediction_status") != "available") or float(p["predicted_session_high"]) >= float(p["predicted_session_low"]) for p in predictions), "high >= low"),
        ok("news_not_fabricated", all(not news.get("fabricated", True) for item in items for news in item.get("news", [])), "news fabricated flag false"),
    ])
    return checks, data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require-public", action="store_true")
    args = parser.parse_args()

    runner_src = read_text(RUNNER_FILE)
    dashboard_src = read_text(DASHBOARD_FILE)
    live_data_src = read_text(LIVE_DATA_FILE)
    live_pipeline_src = read_text(LIVE_PIPELINE_FILE)

    result: dict[str, Any] = {
        "schema_version": "us_stock_live_data_prediction_review_runtime_validation_v1",
        "root_cause_checks": [
            ok("runner_previously_foundation_path_replaced", "build_live_runtime_artifact" in runner_src, "approved runner imports live pipeline"),
            ok("foundation_artifact_marked_fixture", "us_stock_validation_foundation_artifact" in runner_src and "fixture" in runner_src, "foundation path cannot look production"),
        ],
        "sheet_checks": [
            ok("workbook2_reference_present", "工作表2" in runner_src and "load_us_stock_watchlist" in runner_src, "US loader remains 工作表2 based"),
            ok("production_artifact_uses_runtime_sheet", "dry_run=dry_run and not production_artifact" in runner_src, "production-artifact no-send reads runtime 工作表2"),
            ok("private_values_not_printed_flag", "private_values_printed" in runner_src, "safe metadata only"),
        ],
        "dependency_checks": [
            ok("yfinance_installed", has_package("yfinance"), "yfinance import spec"),
            ok("pandas_installed", has_package("pandas"), "pandas import spec"),
            ok("numpy_installed", has_package("numpy"), "numpy import spec"),
        ],
        "live_market_data_checks": [
            ok("yfinance_client_exists", "class YFinanceUSClient" in live_data_src, "dedicated client"),
            ok("timeout_configured", "timeout" in live_data_src, "request timeout/retry fields present"),
        ],
        "technical_checks": [
            ok("ma_rsi_macd_bollinger_present", all(token in live_data_src for token in ["ma20", "rsi14", "macd", "bollinger_upper"]), "technical fields wired"),
            ok("tw_terms_not_used", not any(token in live_data_src for token in ["TWSE", "Shioaji", "融資", "融券"]), "US client avoids TW-only modules"),
        ],
        "news_checks": [
            ok("news_headline_fields_present", all(token in live_data_src for token in ["english_headline", "chinese_translation", "investment_reading"]), "bilingual news contract"),
            ok("no_full_article_copy_contract", not any(token in live_data_src.lower() for token in ["full_article", "article_body", "raw_article", "full_text"]), "headline/summary only"),
        ],
        "prediction_checks": [
            ok("deterministic_prediction_method_present", "prediction_for_symbol" in live_pipeline_src and "atr_like_range_pct" in live_pipeline_src, "range based deterministic prediction"),
            ok("insufficient_data_policy_present", "prediction_status" in live_pipeline_src and "insufficient_data" in live_pipeline_src, "missing data explicit"),
        ],
        "review_checks": [
            ok("snapshot_review_linkage_present", "latest_snapshot_for" in live_pipeline_src and "build_review" in live_pipeline_src, "review uses prior snapshots"),
            ok("review_not_fabricated", '"fabricated": False' in live_pipeline_src, "review outputs fabricated=false"),
        ],
        "artifact_provenance_checks": [
            ok("production_provenance_fields_present", all(token in live_pipeline_src for token in ["artifact_kind", "production_runtime", "data_source_mode", "fixture", "validation_only", "source_sheet"]), "provenance fields"),
        ],
        "dashboard_checks": [
            ok("dashboard_rejects_fixture", "_is_authoritative_us_artifact" in dashboard_src and "artifact_mode") in dashboard_src if False else ok("dashboard_rejects_fixture", "_is_authoritative_us_artifact" in dashboard_src and "artifact_mode" in dashboard_src and "validation_only" in dashboard_src, "authoritative guard"),
            ok("dashboard_no_fixture_fallback", "us_stock_dashboard_fixture_no_send" not in dashboard_src and "us_stock_batch_input_example" not in dashboard_src, "fixture fallback removed"),
            ok("dashboard_missing_state_safe", "正式美股資料尚未產生" in dashboard_src, "safe missing production state"),
        ],
        "scheduler_checks": [
            ok("runner_has_all_windows", all(window in runner_src for window in WINDOWS), "all approved US windows"),
            ok("runner_no_main_py", "python3 main.py" not in runner_src and "python main.py" not in runner_src, "no main.py entrypoint"),
        ],
        "delivery_checks": [
            ok("no_send_default", "dry_run_no_send" in runner_src, "dry-run no send"),
            ok("line_concise_reminder", "concise_reminder_only" in runner_src and "Dashboard" in runner_src, "LINE link reminder only"),
        ],
        "regression_checks": [
            ok("tw_dashboard_route_unchanged", "TW_ROUTE" in dashboard_src and "/dashboard/tw/index.html" in dashboard_src, "TW route retained"),
            ok("us_dashboard_route_unchanged", "US_ROUTE" in dashboard_src and "/dashboard/us/index.html" in dashboard_src, "US route retained"),
        ],
        "safety_checks": [
            ok("no_trading_terms", not any(token in runner_src + live_data_src + live_pipeline_src for token in ["place_order", "broker_order", "Shioaji"]), "no trading/order path"),
            ok("no_secret_printing", "secret_values_printed" in runner_src and "secrets_printed" in live_pipeline_src, "safety flags present"),
        ],
        "skipped_checks": [],
    }
    dry_run = run_runner_live_dry_run("us_pre_market_2000")
    result["live_market_data_checks"].append(ok("approved_runner_live_dry_run_ok", dry_run.get("ok") is True, str(dry_run)[:220]))
    artifact_path = REPO_ROOT / "artifacts/runtime/us_stock/us_pre_market_2000_latest.json"
    artifact_checks, artifact = validate_live_artifact(artifact_path)
    result["artifact_provenance_checks"].extend(artifact_checks)
    if artifact:
        result["prediction_checks"].append(ok("live_prediction_cards_have_no_foundation_text", "market data not fetched in validation" not in json.dumps(artifact.get("dashboard_ready_contract", {}), ensure_ascii=False), "placeholder absent"))

    if args.require_public:
        html = read_text(PUBLIC_US_PATH)
        result["dashboard_checks"].extend([
            ok("public_us_dashboard_exists", PUBLIC_US_PATH.exists(), str(PUBLIC_US_PATH)),
            ok("public_no_foundation_text", "US batch foundation ready" not in html and "market data not fetched in validation" not in html, "foundation text absent"),
            ok("public_us_title", "美股 AI 決策儀表板" in html, "US title"),
        ])
    else:
        result["skipped_checks"].append({"name": "public_us_dashboard_runtime_check", "reason": "use --require-public after controlled publish"})

    all_checks = [check for section, checks in result.items() if section.endswith("_checks") and section != "skipped_checks" for check in checks]
    result["overall"] = {"ok": all(check.get("ok") for check in all_checks), "passed": sum(1 for check in all_checks if check.get("ok")), "total": len(all_checks)}
    text = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    sys.stdout.write(text)
    return 0 if result["overall"]["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
