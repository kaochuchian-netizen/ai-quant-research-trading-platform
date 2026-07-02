#!/usr/bin/env python3
"""Repo-only regression guard for AI-DEV-115A.

This validator uses in-process stubs only. It does not call Shioaji, LINE,
Email, trading, portfolio, scheduler, or production database writes.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
import types
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class _CredentialsFixture:
    @classmethod
    def from_service_account_file(cls, *args: Any, **kwargs: Any) -> "_CredentialsFixture":
        return cls()


sys.modules.setdefault("gspread", types.SimpleNamespace(authorize=lambda creds: None))
sys.modules.setdefault("google", types.ModuleType("google"))
sys.modules.setdefault("google.oauth2", types.ModuleType("google.oauth2"))
service_account_module = types.ModuleType("google.oauth2.service_account")
service_account_module.Credentials = _CredentialsFixture
sys.modules.setdefault("google.oauth2.service_account", service_account_module)
sys.modules.setdefault("yfinance", types.SimpleNamespace(Ticker=lambda symbol: None))
gemini_client_module = types.ModuleType("analysis.gemini_client")
gemini_client_module.generate_analysis = lambda prompt: "fixture analysis"
sys.modules.setdefault("analysis.gemini_client", gemini_client_module)
news_analysis_module = types.ModuleType("analysis.news_analysis_engine")
news_analysis_module.analyze_news = lambda stock_id, stock_name: {"news_signal": "neutral"}
sys.modules.setdefault("analysis.news_analysis_engine", news_analysis_module)
indicator_module = types.ModuleType("indicators.indicator_engine_v2")
indicator_module.build_indicator_result = lambda stock_id, csv_path: {
    "stock_id": stock_id,
    "csv_path": csv_path,
    "score": {"bullish_score": 50},
    "signals": {},
}
sys.modules.setdefault("indicators.indicator_engine_v2", indicator_module)
historical_update_module = types.ModuleType("scripts.update_historical_csv")
historical_update_module.main = lambda: {
    "schema_version": "pipeline_pre_delivery_status_v1",
    "stage": "historical_csv_update",
    "status": "stubbed_for_validator",
    "historical_update_completed": False,
    "report_ready_available": True,
}
sys.modules.setdefault("scripts.update_historical_csv", historical_update_module)

from app.market import stock_name_loader
from app.market.shioaji_client import ShioajiClientError
from app.pipelines import afternoon_report_pipeline, pre_open_pipeline
from app.pipelines.intraday_pipeline import run_intraday_pipeline
from app.pipelines.post_close_pipeline import run_post_close_pipeline
from app.pipelines.pre_close_pipeline import run_pre_close_pipeline
from scripts.orchestrator import approved_pre_open_delivery


INCIDENT_STOCK_IDS = ["2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409"]


class PatchSet:
    def __init__(self) -> None:
        self._originals: list[tuple[object, str, Any]] = []

    def set(self, target: object, name: str, value: Any) -> None:
        self._originals.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def restore(self) -> None:
        for target, name, value in reversed(self._originals):
            setattr(target, name, value)


def shioaji_unavailable() -> None:
    raise ShioajiClientError(
        "Shioaji login failed before market-data fetch (shioaji_version_or_upgrade_required)",
        classification="shioaji_version_or_upgrade_required",
    )


def indicator_fixture(stock_id: str, csv_path: str) -> dict[str, Any]:
    return {
        "stock_id": stock_id,
        "csv_path": csv_path,
        "score": {"bullish_score": 50},
        "signals": {},
    }


def report_fixture(
    stock_id: str,
    stock_name: str,
    indicator_result: dict[str, Any],
    ai_analysis: Any,
    adr_result: dict[str, Any],
    news_result: dict[str, Any],
    total_score_result: dict[str, Any],
    chip_result: dict[str, Any],
) -> str:
    return f"REPORT {stock_id} {stock_name} score={total_score_result.get('total_score', 50)}"


def install_pipeline_stubs(patches: PatchSet) -> None:
    for module in (pre_open_pipeline, afternoon_report_pipeline):
        patches.set(module, "load_stock_ids", lambda: list(INCIDENT_STOCK_IDS))
        patches.set(module.os.path, "exists", lambda path: True)
        patches.set(module, "build_indicator_result", indicator_fixture)
        patches.set(module, "get_adr_result", lambda stock_id: {})
        patches.set(module, "calculate_adr_score", lambda adr_result: 50)
        patches.set(module, "analyze_news", lambda stock_id, stock_name: {"news_signal": "neutral"})
        patches.set(module, "calculate_news_score", lambda news_result: {"score": 50})
        patches.set(module, "analyze_chip", lambda stock_id: {"chip_score": 50})
        patches.set(
            module,
            "calculate_total_score",
            lambda technical_score, news_score, adr_score, chip_score: {"total_score": 50},
        )
        patches.set(module, "analyze_stock", lambda indicator_result, adr_result, news_result: "fixture analysis")
        patches.set(module, "format_stock_report_v2", report_fixture)

    patches.set(pre_open_pipeline, "send_reports_in_batches", lambda reports, dry_run=False: None)
    patches.set(stock_name_loader, "get_api", shioaji_unavailable)
    stock_name_loader.load_local_stock_name_map.cache_clear()


def run_pipeline_case(name: str, runner: Any) -> dict[str, Any]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = runner(dry_run=True)
    rendered = output.getvalue()
    errors: list[str] = []
    if not isinstance(result, dict):
        errors.append("pipeline did not return a summary dict")
        result = {}
    if result.get("report_count") != len(INCIDENT_STOCK_IDS):
        errors.append(f"report_count expected {len(INCIDENT_STOCK_IDS)}, got {result.get('report_count')}")
    if result.get("trading_order_portfolio_action") is not False:
        errors.append("trading_order_portfolio_action must be false")
    if "Traceback" in rendered:
        errors.append("pipeline output must not include traceback")
    if "shioaji_version_or_upgrade_required" not in rendered:
        errors.append("pipeline output should keep stock-name fallback diagnostics")
    return {
        "pipeline": name,
        "ok": not errors,
        "errors": errors,
        "report_count": result.get("report_count"),
        "stock_name_fallback_count": result.get("stock_name_fallback_count"),
        "stdout_contains_traceback": "Traceback" in rendered,
    }


def validate_stock_name_resolver() -> dict[str, Any]:
    original = stock_name_loader.get_api
    try:
        stock_name_loader.get_api = shioaji_unavailable
        stock_name_loader.load_local_stock_name_map.cache_clear()
        resolved = stock_name_loader.resolve_stock_name("2330")
    finally:
        stock_name_loader.get_api = original
        stock_name_loader.load_local_stock_name_map.cache_clear()
    errors = []
    if resolved.get("stock_name") != "2330":
        errors.append(f"stock_name fallback expected 2330, got {resolved.get('stock_name')}")
    if resolved.get("warning") != "shioaji_version_or_upgrade_required":
        errors.append(f"warning classification mismatch: {resolved.get('warning')}")
    return {"ok": not errors, "errors": errors, "resolved": resolved}


def validate_pipelines() -> list[dict[str, Any]]:
    patches = PatchSet()
    try:
        install_pipeline_stubs(patches)
        return [
            run_pipeline_case("pre_open", pre_open_pipeline.run_pre_open_pipeline),
            run_pipeline_case("intraday", run_intraday_pipeline),
            run_pipeline_case("pre_close", run_pre_close_pipeline),
            run_pipeline_case("post_close", run_post_close_pipeline),
        ]
    finally:
        patches.restore()
        stock_name_loader.load_local_stock_name_map.cache_clear()


def validate_delivery_guard() -> dict[str, Any]:
    completed = subprocess.CompletedProcess(
        args=["python3", "scripts/run_pipeline.py", "pre_open", "--production-approved"],
        returncode=1,
        stdout=(
            "pre_open selected stock ids: ['2330']\n"
            "Traceback (most recent call last):\n"
            "ShioajiClientError: Shioaji login failed before market-data fetch "
            "(shioaji_version_or_upgrade_required)\n"
        ),
    )
    output = completed.stdout or ""
    dashboard = approved_pre_open_delivery.render_dashboard(
        "pre_open_0700",
        "approved-pre_open_0700-delivery-20260702-070001",
        "2026-07-02T07:00:01+08:00",
        "failed",
        output,
    )
    email = approved_pre_open_delivery.build_email_body(
        "pre_open_0700",
        "approved-pre_open_0700-delivery-20260702-070001",
        "2026-07-02T07:00:01+08:00",
        "failed",
        "http://example.invalid/dashboard",
        output,
    )
    diagnostics = approved_pre_open_delivery.build_pipeline_diagnostics(completed, output)
    line = approved_pre_open_delivery.send_concise_line(
        "pre_open_0700",
        "2026-07-02T07:00:01+08:00",
        "failed",
        "http://example.invalid/dashboard",
        output,
    )
    errors = []
    if "Traceback" in dashboard or "ShioajiClientError" in dashboard:
        errors.append("dashboard user-facing content contains raw traceback")
    if "Traceback" in email or "ShioajiClientError" in email:
        errors.append("email user-facing content contains raw traceback")
    if diagnostics.get("raw_output_contains_traceback") is not True:
        errors.append("diagnostics should retain raw traceback marker")
    if line.get("send_status") != "not_sent":
        errors.append(f"line status expected not_sent, got {line.get('send_status')}")
    if not line.get("reason"):
        errors.append("line not_sent result must include reason")
    return {
        "ok": not errors,
        "errors": errors,
        "dashboard_contains_traceback": "Traceback" in dashboard,
        "email_contains_traceback": "Traceback" in email,
        "diagnostics_contains_traceback": diagnostics.get("raw_output_contains_traceback"),
        "line_delivery_status": line.get("send_status"),
        "line_delivery_reason": line.get("reason"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-115A regression guard.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = {
        "schema_version": "ai_dev_115a_preopen_delivery_incident_regression_guard_v1",
        "stock_name_resolver": validate_stock_name_resolver(),
        "pipelines": validate_pipelines(),
        "delivery_guard": validate_delivery_guard(),
        "line_email_trading_side_effects": {
            "line_test_sent": False,
            "email_test_sent": False,
            "trading_order_portfolio_action": False,
            "scheduler_changed": False,
            "secret_touched": False,
        },
    }
    result["ok"] = (
        result["stock_name_resolver"]["ok"]
        and all(case["ok"] for case in result["pipelines"])
        and result["delivery_guard"]["ok"]
    )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
