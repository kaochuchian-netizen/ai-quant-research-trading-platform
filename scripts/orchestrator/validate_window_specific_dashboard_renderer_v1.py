#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard.multi_market_dashboard import render_landing_page, render_tw_page, render_us_page
from app.reports.multi_window_formatter import format_window_report, line_notification_text
from app.reports.window_context import get_window_context
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, line_text

SCHEMA_VERSION = "window_specific_dashboard_renderer_validation_v1"
TASK_ID = "AI-DEV-178A"

DEBUG_TOKENS = [
    "Dashboard scope",
    "LINE scope",
    "dashboard_sections",
    "email_sections",
    "line_summary_scope",
    "suppressed_sections",
    "required_sections",
    "primary_question",
]

GENERIC_FORBIDDEN = [
    "最近官方文件（SEC）",
    "近期新聞與事件",
    "技術與系統細節",
    "策略代碼",
    "因子版本",
    "full-decision-card",
]

TW_PRE_CLOSE_REQUIRED = ["13:35 收盤快照", "收盤前摘要", "尾盤風險", "避免追價", "明日初步觀察"]
TW_POST_CLOSE_REQUIRED = ["15:00 盤後檢討", "今日預測 vs 實際", "是否進場", "第一目標結果", "第二目標結果", "停損結果", "MFE / MAE", "明日觀察"]
US_INTRADAY_REQUIRED = ["23:00 美股盤中", "開盤後變化", "Gap follow-through", "Volume confirmation", "Entry trigger", "Target / Stop proximity"]
US_REVIEW_REQUIRED = ["06:30 美股檢討", "Prediction review", "Entry / Stop / Target outcome", "Win / Loss / Not Triggered", "MFE / MAE", "Next-session watchlist"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_report(html: str, report_type: str) -> str:
    marker = f'data-report-type="{report_type}"'
    start = html.find(marker)
    if start < 0:
        return ""
    section_start = html.rfind("<section", 0, start)
    next_start = html.find('<section class="section window-report-section"', start + len(marker))
    end = next_start if next_start >= 0 else html.find("</main>", start)
    if end < 0:
        end = len(html)
    return html[section_start:end]


def section_ids(section: str) -> list[str]:
    return re.findall(r'data-section="([^"]+)"', section)


def card_types(section: str) -> list[str]:
    return re.findall(r'data-card-type="([^"]+)"', section)


def contains_all(text: str, tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in text]


def contains_any(text: str, tokens: list[str]) -> list[str]:
    return [token for token in tokens if token in text]


def fixture_us_artifact(window: str) -> dict[str, Any]:
    return {
        "market": "US",
        "window": window,
        "generated_at": "2026-07-14T00:00:00+08:00",
        "runtime_watchlist_validation": {"enabled_stock_count": 1},
        "dashboard_ready_contract": {
            "cards": [
                {
                    "symbol": "NVDA",
                    "name": "Nvidia",
                    "rating": "C級",
                    "action": "等待確認",
                    "confidence": 62,
                    "daily_tactical_summary": {
                        "direction": "溫和偏多",
                        "setup": "Breakout Pending",
                        "action": "等待突破",
                        "entry_zone": "201 ~ 205",
                        "stop": "198",
                        "target": "210 ~ 214",
                        "risk": "事件風險中",
                    },
                    "prediction": {"today_range": "198 ~ 210"},
                    "bilingual_news_snippet": {"chinese_translation": "近期未發現可驗證重大新聞"},
                }
            ]
        },
        "prediction_review_contract": {"review_status": "pending"},
    }


def validate_html() -> tuple[list[str], dict[str, Any]]:
    tw_html = render_tw_page()
    us_html = render_us_page([fixture_us_artifact(window) for window in ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630")])
    landing_html = render_landing_page()
    errors: list[str] = []
    debug_hits = {
        "landing": contains_any(landing_html, DEBUG_TOKENS),
        "tw": contains_any(tw_html, DEBUG_TOKENS),
        "us": contains_any(us_html, DEBUG_TOKENS),
    }
    for page, hits in debug_hits.items():
        for hit in hits:
            errors.append(f"{page}: debug contract token leaked: {hit}")

    reports = {
        "tw_pre_open": extract_report(tw_html, "pre-open-decision"),
        "tw_intraday": extract_report(tw_html, "intraday-change"),
        "tw_pre_close": extract_report(tw_html, "pre-close-snapshot"),
        "tw_post_close": extract_report(tw_html, "post-close-review"),
        "us_pre": extract_report(us_html, "us-pre-market"),
        "us_intraday": extract_report(us_html, "us-intraday-change"),
        "us_review": extract_report(us_html, "us-post-close-review"),
    }
    for name, html in reports.items():
        if not html:
            errors.append(f"{name}: missing rendered report section")

    checks = {
        "tw_pre_close_missing": contains_all(reports["tw_pre_close"], TW_PRE_CLOSE_REQUIRED),
        "tw_post_close_missing": contains_all(reports["tw_post_close"], TW_POST_CLOSE_REQUIRED),
        "us_intraday_missing": contains_all(reports["us_intraday"], US_INTRADAY_REQUIRED),
        "us_review_missing": contains_all(reports["us_review"], US_REVIEW_REQUIRED),
        "tw_pre_close_forbidden": contains_any(reports["tw_pre_close"], GENERIC_FORBIDDEN + ["中長期研究", "財務體質", "完整每日短線策略"]),
        "tw_post_close_forbidden": contains_any(reports["tw_post_close"], GENERIC_FORBIDDEN + ["進場區", "今日操作結論", "完整每日短線策略", "中長期研究", "財務體質"]),
        "us_intraday_forbidden": contains_any(reports["us_intraday"], GENERIC_FORBIDDEN + ["中長期研究", "財務體質"]),
        "us_review_forbidden": contains_any(reports["us_review"], GENERIC_FORBIDDEN + ["中長期研究", "財務體質", "今日 Tactical setup"]),
    }
    for key, values in checks.items():
        if values:
            errors.append(f"{key}: {values}")

    inventory = {
        name: {"sections": section_ids(html), "card_types": sorted(set(card_types(html)))}
        for name, html in reports.items()
    }
    pairs = [
        ("tw_pre_open", "tw_intraday"),
        ("tw_intraday", "tw_pre_close"),
        ("tw_pre_close", "tw_post_close"),
        ("us_pre", "us_intraday"),
        ("us_intraday", "us_review"),
    ]
    for left, right in pairs:
        if inventory[left] == inventory[right]:
            errors.append(f"window DOM inventory did not differ: {left} == {right}")

    if "full-decision-card" in reports["tw_pre_close"] + reports["tw_post_close"] + reports["us_intraday"] + reports["us_review"]:
        errors.append("generic full decision card leaked into compact/review windows")

    return errors, {"debug_hits": debug_hits, "inventory": inventory}


def validate_email_line() -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    tw_pre_close = format_window_report("pre_close_1335", "stock_analysis_reports_available", "收盤快照摘要", [{"stock_id": "2330", "stock_name": "台積電", "signal": "observe", "summary": "尾盤避免追價，明日觀察"}], "http://35.201.242.167/stock-ai-dashboard/dashboard/tw/index.html")
    tw_post_close = format_window_report("post_close_1500", "prediction_review_insufficient_data", "今日檢討尚待實際結果", [], "http://35.201.242.167/stock-ai-dashboard/dashboard/tw/index.html")
    us_intraday_email = build_email_body(fixture_us_artifact("us_intraday_2300"), "us_intraday_2300")
    us_review_email = build_email_body(fixture_us_artifact("us_post_close_review_0630"), "us_post_close_review_0630")
    us_line = line_text(fixture_us_artifact("us_intraday_2300"), "us_intraday_2300")
    tw_line = line_notification_text(get_window_context("pre_close_1335"), "http://35.201.242.167/stock-ai-dashboard/dashboard/tw/index.html")
    samples = {
        "tw_pre_close_email": tw_pre_close["channel_reports"]["email"]["text"],
        "tw_post_close_email": tw_post_close["channel_reports"]["email"]["text"],
        "us_intraday_email": us_intraday_email,
        "us_review_email": us_review_email,
        "tw_line": tw_line,
        "us_line": us_line,
    }
    forbidden = DEBUG_TOKENS + ["Window-specific sections:", "Dashboard scope", "LINE scope"]
    for name, text in samples.items():
        hits = contains_any(text, forbidden)
        if hits:
            errors.append(f"{name}: debug/scope leak {hits}")
    if "中長期研究" in us_intraday_email or "最近官方文件（SEC）" in us_intraday_email:
        errors.append("us_intraday_email contains full research/sec section")
    if "Daily Tactical：" in us_review_email or "Entry：" in us_review_email:
        errors.append("us_review_email contains full tactical plan block")
    return errors, {"email_line_samples": {key: len(value) for key, value in samples.items()}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    html_errors, html_details = validate_html()
    channel_errors, channel_details = validate_email_line()
    errors = html_errors + channel_errors
    payload = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "ok": not errors,
        "errors": errors,
        "html": html_details,
        "channels": channel_details,
        "safety": {
            "email_attempted": False,
            "line_attempted": False,
            "production_pipeline_executed": False,
            "trading_or_order_executed": False,
            "scheduler_changed": False,
            "python3_main_executed": False,
            "secrets_accessed": False,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
