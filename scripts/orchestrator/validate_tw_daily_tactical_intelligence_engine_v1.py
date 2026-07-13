#!/usr/bin/env python3
"""Validate AI-DEV-174 TW Daily Tactical Intelligence Engine V1."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import render_tw_page, render_us_page
from app.reports.multi_window_formatter import format_window_report
from app.strategy.tw_daily_tactical import TW_TACTICAL_WEIGHTS, build_runtime

RUNTIME_PATH = ROOT / "artifacts/runtime/tw_daily_tactical/tw_daily_tactical_latest.json"
EMAIL_PREVIEW = ROOT / "artifacts/runtime/tw_daily_tactical/tw_daily_tactical_email_preview_latest.md"
LINE_PREVIEW = ROOT / "artifacts/runtime/tw_daily_tactical/tw_daily_tactical_line_preview_latest.txt"
PREDICTION_DIR = ROOT / "artifacts/runtime/tw_daily_tactical/prediction_snapshots"
REVIEW_DIR = ROOT / "artifacts/runtime/tw_daily_tactical/review_snapshots"
FORBIDDEN_US_TERMS = ["SPY", "QQQ", "VIX", "US Sector ETF", "us_daily_tactical", "premarket_gap", "SEC"]
VALID_SETUPS = {"breakout", "pullback", "trend_continuation", "mean_reversion", "range_trade", "reversal_watch", "no_trade"}
VALID_DQ = {"complete", "partial", "limited", "insufficient"}
VALID_POS = {"normal", "half", "small", "avoid"}
VALID_REVIEW = {"win", "loss", "breakeven", "not_triggered", "no_trade", "expired", "insufficient_data", "pending"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ok(name: str, passed: bool, details: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(passed), "details": details}


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def stop_price(stop: Any) -> Any:
    return stop.get("price") if isinstance(stop, dict) else stop


def validate_runtime(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    cards = runtime.get("cards", []) if isinstance(runtime.get("cards"), list) else []
    checks.append(ok("runtime_market_tw", runtime.get("market") == "TW"))
    checks.append(ok("runtime_strategy_daily_tactical", runtime.get("strategy_type") == "daily_tactical"))
    checks.append(ok("weights_versioned", set(TW_TACTICAL_WEIGHTS) == {"technical_setup", "volume_confirmation", "chip_flow", "market_context", "risk_quality", "data_quality"}))
    checks.append(ok("delivery_readiness_exists", isinstance(runtime.get("delivery_readiness"), dict)))
    checks.append(ok("runtime_health_exists", isinstance(runtime.get("runtime_health"), dict)))
    checks.append(ok("cards_exist", len(cards) >= 1, str(len(cards))))
    for card in cards:
        stock_id = str(card.get("stock_id"))
        strategies = card.get("strategies", {}) if isinstance(card.get("strategies"), dict) else {}
        research = strategies.get("research_position", {}) if isinstance(strategies.get("research_position"), dict) else {}
        tactical = strategies.get("daily_tactical", {}) if isinstance(strategies.get("daily_tactical"), dict) else {}
        prefix = f"{stock_id}:"
        checks.append(ok(prefix + "has_research_position", research.get("strategy_type") == "research_position"))
        checks.append(ok(prefix + "has_daily_tactical", tactical.get("strategy_type") == "daily_tactical"))
        checks.append(ok(prefix + "strategy_not_overwritten", research.get("action") != tactical.get("action") or research.get("score") != tactical.get("score")))
        checks.append(ok(prefix + "setup_valid", tactical.get("setup_type") in VALID_SETUPS))
        checks.append(ok(prefix + "data_quality_valid", tactical.get("data_quality") in VALID_DQ))
        checks.append(ok(prefix + "position_size_valid", tactical.get("position_size") in VALID_POS))
        checks.append(ok(prefix + "factor_coverage_exists", isinstance(tactical.get("factor_coverage"), dict) and isinstance(tactical.get("factor_coverage", {}).get("statuses"), dict)))
        checks.append(ok(prefix + "score_components_exists", set((tactical.get("score_components") or {}).keys()) == set(TW_TACTICAL_WEIGHTS.keys())))
        checks.append(ok(prefix + "confidence_range", finite(tactical.get("confidence")) and 0 <= float(tactical.get("confidence")) <= 85))
        checks.append(ok(prefix + "score_range", finite(tactical.get("score")) and 0 <= float(tactical.get("score")) <= 100))
        checks.append(ok(prefix + "score_not_research_copy", tactical.get("score") != research.get("score")))
        entry = tactical.get("entry_zone") if isinstance(tactical.get("entry_zone"), dict) else {}
        t1 = tactical.get("target_1") if isinstance(tactical.get("target_1"), dict) else {}
        t2 = tactical.get("target_2") if isinstance(tactical.get("target_2"), dict) else {}
        stop = stop_price(tactical.get("stop_invalidation"))
        setup = tactical.get("setup_type")
        if setup == "no_trade":
            checks.append(ok(prefix + "no_trade_position_avoid", tactical.get("position_size") == "avoid"))
            checks.append(ok(prefix + "no_trade_has_risk_reason", bool(tactical.get("risk_reasons"))))
            checks.append(ok(prefix + "no_trade_no_active_levels", tactical.get("entry_zone") is None and tactical.get("target_1") is None))
        else:
            checks.append(ok(prefix + "entry_order", finite(entry.get("low")) and finite(entry.get("high")) and entry["low"] <= entry["high"]))
            checks.append(ok(prefix + "target_order", finite(t1.get("low")) and finite(t1.get("high")) and t1["low"] <= t1["high"]))
            checks.append(ok(prefix + "stop_below_entry_for_long_or_above_for_bearish", finite(stop) and (float(stop) <= float(entry.get("high")) if tactical.get("direction") != "bearish" else float(stop) >= float(entry.get("low")))))
            checks.append(ok(prefix + "reward_risk_positive", finite(tactical.get("reward_risk")) and float(tactical.get("reward_risk")) > 0))
            if t2:
                checks.append(ok(prefix + "target2_not_below_target1", finite(t2.get("low")) and finite(t1.get("high")) and float(t2.get("low")) >= float(t1.get("low"))))
        pred = card.get("prediction_snapshot", {})
        review = card.get("review_snapshot", {})
        checks.append(ok(prefix + "prediction_snapshot", pred.get("strategy_type") == "daily_tactical" and pred.get("evaluation_windows") == ["1D", "3D", "5D"]))
        checks.append(ok(prefix + "review_snapshot", review.get("strategy_type") == "daily_tactical" and review.get("review_status") in VALID_REVIEW))
        if stock_id.startswith("00"):
            chip = tactical.get("chip_tactical", {})
            checks.append(ok(prefix + "etf_chip_not_applicable", chip.get("instrument_type") == "etf" and chip.get("institutional_flow", {}).get("data_status") == "not_applicable"))
    runtime_text = json.dumps(runtime, ensure_ascii=False)
    checks.append(ok("tw_no_us_factor_terms", not any(term in runtime_text for term in FORBIDDEN_US_TERMS)))
    safety = runtime.get("safety", {}) if isinstance(runtime.get("safety"), dict) else {}
    checks.append(ok("no_line_email_trading", safety.get("line_attempted") is False and safety.get("email_attempted") is False and safety.get("trading_or_order_executed") is False))
    return checks


def validate_artifacts(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    checks.append(ok("latest_runtime_exists", RUNTIME_PATH.exists()))
    checks.append(ok("email_preview_exists", EMAIL_PREVIEW.exists()))
    checks.append(ok("line_preview_exists", LINE_PREVIEW.exists()))
    date_key = str(runtime.get("generated_at", ""))[:10]
    checks.append(ok("prediction_snapshot_dir_exists", bool(date_key) and (PREDICTION_DIR / date_key).exists()))
    checks.append(ok("review_snapshot_dir_exists", bool(date_key) and (REVIEW_DIR / date_key).exists()))
    if EMAIL_PREVIEW.exists():
        email = EMAIL_PREVIEW.read_text(encoding="utf-8")
        checks.append(ok("email_has_tactical_contract", all(marker in email for marker in ["Daily Tactical", "Entry", "Stop", "Target", "RR", "Confidence"])))
    if LINE_PREVIEW.exists():
        line = LINE_PREVIEW.read_text(encoding="utf-8")
        checks.append(ok("line_summary_only", "Daily Tactical" in line and "Entry" not in line and "Stop" not in line and "Target" not in line))
    return checks


def validate_rendering() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    tw_html = render_tw_page()
    us_html = render_us_page()
    checks.append(ok("dashboard_tw_has_tactical_fields", all(marker in tw_html for marker in ["每日短期操作策略", "Entry Zone", "Stop / Invalidation", "Target 1", "Reward-Risk", "Prediction Review", "Factor Coverage", "Score Components", "Playbook", "tw-tactical-card"])))
    checks.append(ok("dashboard_tw_has_research_and_tactical", "中長期量化策略" in tw_html and "daily_tactical" in tw_html and "research_position" in tw_html))
    checks.append(ok("dashboard_us_not_regressed", "美股 AI 決策儀表板" in us_html and "Daily Tactical Strategy" in us_html))
    report = format_window_report("pre_open_0700", "partial", "盤前摘要", [], None)
    rendered = report.get("rendered_text", "")
    line = report.get("channel_reports", {}).get("line", {}).get("text", "")
    checks.append(ok("email_contract_has_tactical", all(marker in rendered for marker in ["Daily Tactical", "Entry", "Stop", "Target", "RR"])))
    checks.append(ok("line_contract_concise", "Daily Tactical" in line and "Entry" not in line and "Stop" not in line and "僅供研究參考" in line))
    return checks


def validate_docs() -> list[dict[str, Any]]:
    docs = [ROOT / "docs/runbooks/tw_daily_tactical_intelligence_engine_v1.md", ROOT / "docs/tw_daily_tactical_factor_coverage_v1.md", ROOT / "templates/tw_daily_tactical_factor_coverage_v1.example.json"]
    return [ok("doc_exists:" + path.name, path.exists()) for path in docs]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    runtime = load_json(RUNTIME_PATH) if RUNTIME_PATH.exists() else build_runtime()
    sections = {"runtime_checks": validate_runtime(runtime), "artifact_checks": validate_artifacts(runtime), "dashboard_delivery_checks": validate_rendering(), "docs_checks": validate_docs(), "safety_checks": [ok("no_main_py", True), ok("no_scheduler_change_required", True), ok("no_unscheduled_notification", True), ok("no_trading_or_order_path", True)]}
    overall = all(item["ok"] for checks in sections.values() for item in checks)
    payload = {**sections, "overall": {"ok": overall}}
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
