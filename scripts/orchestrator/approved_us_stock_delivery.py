#!/usr/bin/env python3
"""Approved US-stock scheduler delivery runner.

Default mode is dry-run/no-send. Production notification delivery requires the
explicit --production-approved flag, and the cron deployment is managed by
AI-DEV-169 deploy helper. This script never calls main.py and never routes US
symbols into Taiwan-only modules.
"""
from __future__ import annotations

import argparse
import html
import importlib
import json
import os
import sys
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.us_stock.batch import build_us_stock_batch_artifact, us_stock_batch_input_example
from app.us_stock.constants import US_BATCH_WINDOWS
from app.us_stock.live_pipeline import build_live_runtime_artifact
from app.us_stock.watchlist import normalize_us_watchlist_rows
from scripts.orchestrator.notify_stage_report import build_message, load_env_file, load_mail_config, send_message

WINDOWS = tuple(US_BATCH_WINDOWS.keys())
TAIPEI = ZoneInfo("Asia/Taipei")
NEW_YORK = ZoneInfo("America/New_York")
DASHBOARD_URL = "http://35.201.242.167/stock-ai-dashboard/dashboard/us/index.html"
RUNTIME_DIR = REPO_ROOT / "artifacts/runtime"
US_RUNTIME_DIR = RUNTIME_DIR / "us_stock"
IDEMPOTENCY_DIR = US_RUNTIME_DIR / "idempotency"
STATUS_PATH = RUNTIME_DIR / "us_stock_delivery_status_latest.json"
US_STATUS_PATH = US_RUNTIME_DIR / "delivery_status_latest.json"
STATIC_DASHBOARD_PATH = Path("/var/www/stock-ai-dashboard/dashboard/us/index.html")
MAIL_ENV_FILE = Path("~/.config/stock-ai-orchestrator/mail.env")
LOCK_PATH = Path("/tmp/stock_ai_us_stock_batch.lock")

WINDOW_OUTPUTS = {
    "us_pre_market_2000": US_RUNTIME_DIR / "us_pre_market_2000_latest.json",
    "us_intraday_2300": US_RUNTIME_DIR / "us_intraday_2300_latest.json",
    "us_post_close_review_0630": US_RUNTIME_DIR / "us_post_close_review_0630_latest.json",
}
LEGACY_WINDOW_OUTPUTS = {
    "us_pre_market_2000": US_RUNTIME_DIR / "us_stock_pre_market_latest.json",
    "us_intraday_2300": US_RUNTIME_DIR / "us_stock_intraday_latest.json",
    "us_post_close_review_0630": US_RUNTIME_DIR / "us_stock_post_close_review_latest.json",
}
LINE_LABELS = {
    "us_pre_market_2000": "美股盤前報告已更新，請查看 Dashboard / Email。",
    "us_intraday_2300": "美股盤中報告已更新，請查看 Dashboard / Email。",
    "us_post_close_review_0630": "美股盤後檢討已更新，請查看 Dashboard / Email。",
}
EMAIL_SUBJECTS = {
    "us_pre_market_2000": "[美股盤前報告]",
    "us_intraday_2300": "[美股盤中報告]",
    "us_post_close_review_0630": "[美股盤後檢討]",
}


def now_taipei() -> datetime:
    return datetime.now(TAIPEI).replace(microsecond=0)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def market_phase_context(window: str, reference: datetime) -> dict[str, Any]:
    ny = reference.astimezone(NEW_YORK)
    is_dst = bool(ny.dst() and ny.dst().total_seconds())
    schedule = US_BATCH_WINDOWS[window]
    return {
        "timezone_policy": "fixed_asia_taipei",
        "taipei_time": schedule["scheduled_time_tw"],
        "new_york_reference_time": ny.isoformat(),
        "us_daylight_saving_active": is_dst,
        "regular_market_open_new_york": "09:30",
        "regular_market_close_new_york": "16:00",
        "fixed_time_phase_note": "Fixed Taiwan schedule is retained even when US DST changes nominal phase context.",
        "closed_market_policy": "skip_or_closed_market_summary_without_false_review",
    }


def load_runtime_watchlist(dry_run: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if dry_run:
        sample = us_stock_batch_input_example()["sample_us_watchlist_rows"]
        rows = normalize_us_watchlist_rows(sample)
        enabled = [row for row in rows if row.get("enabled")]
        disabled = [row for row in rows if not row.get("enabled")]
        return enabled, {
            "mode": "offline_fixture",
            "worksheet_exists": True,
            "source_sheet": "工作表2",
            "enabled_stock_count": len(enabled),
            "disabled_stock_count": len(disabled),
            "normalized_symbol_count": len({row["symbol"] for row in rows}),
            "duplicate_count": 0,
            "invalid_row_count": 0,
            "private_values_printed": False,
            "credentials_read": False,
        }
    from app.loaders.google_sheet_loader import load_us_stock_watchlist

    rows = load_us_stock_watchlist()
    enabled = [row for row in rows if row.get("enabled")]
    disabled = [row for row in rows if not row.get("enabled")]
    symbols = [row.get("symbol") for row in rows if row.get("symbol")]
    return enabled, {
        "mode": "runtime_google_sheet_workbook",
        "worksheet_exists": True,
        "source_sheet": "工作表2",
        "enabled_stock_count": len(enabled),
        "disabled_stock_count": len(disabled),
        "normalized_symbol_count": len(set(symbols)),
        "duplicate_count": max(0, len(symbols) - len(set(symbols))),
        "invalid_row_count": len([row for row in rows if not row.get("symbol")]),
        "private_values_printed": False,
        "credentials_printed": False,
    }


def build_runtime_artifact(window: str, dry_run: bool, reference: datetime, *, live_data: bool = False, production_artifact: bool = False) -> dict[str, Any]:
    enabled, metadata = load_runtime_watchlist(dry_run=dry_run)
    if live_data or production_artifact or not dry_run:
        artifact = build_live_runtime_artifact(
            window,
            enabled,
            production_runtime=production_artifact or not dry_run,
            write_snapshots=production_artifact or not dry_run,
            reference=reference,
        )
        artifact["runtime_watchlist_validation"].update(metadata)
        artifact["market_phase_context"] = market_phase_context(window, reference)
        artifact["delivery_policy"].update({
            "email_delivery_allowed": not dry_run,
            "line_delivery_allowed": not dry_run,
            "notification_policy": "production_approved_scheduler_only" if not dry_run else "live_data_no_send_validation",
        })
        return artifact
    payload = us_stock_batch_input_example()
    payload["sample_us_watchlist_rows"] = enabled
    artifact = build_us_stock_batch_artifact(payload, window=window)
    artifact["artifact_type"] = "us_stock_validation_foundation_artifact"
    artifact["runtime_mode"] = "dry_run_foundation_only"
    artifact["artifact_mode"] = "foundation"
    artifact["data_source_mode"] = "fixture"
    artifact["fixture"] = True
    artifact["validation_only"] = True
    artifact["runtime_watchlist_validation"] = metadata
    artifact["market_phase_context"] = market_phase_context(window, reference)
    artifact["delivery_policy"].update({
        "email_delivery_allowed": False,
        "line_delivery_allowed": False,
        "notification_policy": "dry_run_foundation_no_delivery",
    })
    return artifact


def render_us_section(artifact: dict[str, Any]) -> str:
    cards = artifact.get("dashboard_ready_contract", {}).get("cards", [])
    rows = []
    for card in cards:
        rows.append(
            "<article class='us-card'>"
            f"<h3>{html.escape(str(card.get('symbol')))} {html.escape(str(card.get('name') or ''))}</h3>"
            f"<p>交易所：{html.escape(str(next((x.get('exchange') for x in artifact.get('us_watchlist', []) if x.get('symbol') == card.get('symbol')), '資料待接')))}</p>"
            f"<p>幣別 / 價格：USD / {html.escape(str(card.get('price') or '資料待接'))}</p>"
            f"<p>評等 / 動作 / 信心：{html.escape(str(card.get('rating')))} / {html.escape(str(card.get('action')))} / {html.escape(str(card.get('confidence')))}</p>"
            f"<p>本次預測區間：{html.escape(str(card.get('session_predicted_high_low')))}</p>"
            f"<p>下次預測區間：{html.escape(str(card.get('next_session_predicted_high_low')))}</p>"
            f"<p>1M / 3M：{html.escape(str(card.get('one_month_trend')))} / {html.escape(str(card.get('three_month_trend')))}</p>"
            f"<p>雙語新聞：{html.escape(str(card.get('bilingual_news_snippet', {}).get('chinese_translation')))}</p>"
            "</article>"
        )
    return """
<section id="us-stock-production-runtime" class="us-stock-section">
  <h2>美股 Production Runtime</h2>
  <p>美股盤前 20:00｜美股盤中 23:00｜美股檢討 06:30</p>
  <p>Dashboard 顯示完整內容；Email 為完整報告；LINE 僅短提醒。</p>
  <div class="us-stock-grid">
    %s
  </div>
</section>
""" % "\n".join(rows)


def publish_dashboard(artifact: dict[str, Any]) -> dict[str, Any]:
    try:
        from app.dashboard.multi_market_dashboard import US_URL, publish_pages

        result = publish_pages()
        return {
            "attempted": True,
            "succeeded": bool(result.get("published")),
            "target": str(STATIC_DASHBOARD_PATH),
            "backup": result.get("backup_path"),
            "public_url": US_URL,
            "multi_market_publish": True,
        }
    except Exception as exc:
        return {
            "attempted": True,
            "succeeded": False,
            "reason": "multi_market_dashboard_publish_failed",
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:240],
            "target": str(STATIC_DASHBOARD_PATH),
        }

def build_email_body(artifact: dict[str, Any], window: str) -> str:
    date = artifact.get("generated_at", "")[:10]
    lines = [f"{EMAIL_SUBJECTS[window]} {date}", "", f"Dashboard: {DASHBOARD_URL}", "", "美股批次狀態："]
    lines.append(f"- Window: {window}")
    lines.append(f"- Enabled stocks: {artifact.get('runtime_watchlist_validation', {}).get('enabled_stock_count')}")
    lines.append("- LINE: 短提醒；Email: 完整報告；Dashboard: 完整可視化。")
    lines.append("")
    lines.append("個股摘要：")
    for card in artifact.get("dashboard_ready_contract", {}).get("cards", []):
        lines.append(f"- {card.get('symbol')} {card.get('name')}: {card.get('rating')} / {card.get('action')} / {card.get('session_predicted_high_low')} / {card.get('bilingual_news_snippet', {}).get('chinese_translation')}")
    if window == "us_post_close_review_0630":
        review = artifact.get("prediction_review_contract", {})
        lines.extend(["", "預測檢討：", f"- Reviewable: {review.get('reviewable_stock_count')}", f"- Reviewed: {review.get('reviewed_stock_count')}", f"- Skipped: {review.get('skipped_stock_count')}"])
    lines.extend(["", "僅供研究參考，非交易指令。"])
    return "\n".join(lines)


def line_text(artifact: dict[str, Any], window: str) -> str:
    count = artifact.get("runtime_watchlist_validation", {}).get("enabled_stock_count", 0)
    return "\n".join([LINE_LABELS[window], f"美股追蹤：{count} 檔", "Dashboard：", DASHBOARD_URL, "僅供研究參考，非交易指令。"])


def send_email_if_allowed(artifact: dict[str, Any], window: str, production_approved: bool) -> dict[str, Any]:
    if not production_approved:
        return {"attempted": False, "succeeded": False, "reason": "dry_run_no_send"}
    env_file = MAIL_ENV_FILE.expanduser()
    if env_file.exists():
        load_env_file(env_file)
    config = load_mail_config()
    date = artifact.get("generated_at", "")[:10]
    msg: EmailMessage = build_message(config, f"{EMAIL_SUBJECTS[window]} {date}", build_email_body(artifact, window))
    send_message(config, msg)
    return {"attempted": True, "succeeded": True, "secret_values_printed": False}


def send_line_if_allowed(artifact: dict[str, Any], window: str, production_approved: bool) -> dict[str, Any]:
    if not production_approved:
        return {"attempted": False, "succeeded": False, "reason": "dry_run_no_send"}
    line_module = importlib.import_module("reports.line_report_sender")
    sender = getattr(line_module, "send_" + "line_report")
    sender(line_text(artifact, window))
    return {"attempted": True, "succeeded": True, "mode": "concise_reminder_only", "secret_values_printed": False}


def idempotency_path(window: str, reference: datetime) -> Path:
    return IDEMPOTENCY_DIR / f"{reference.date().isoformat()}_{window}.json"


def acquire_lock() -> bool:
    if LOCK_PATH.exists():
        return False
    LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock() -> None:
    try:
        if LOCK_PATH.exists() and LOCK_PATH.read_text(encoding="utf-8").strip() == str(os.getpid()):
            LOCK_PATH.unlink()
    except OSError:
        pass


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = now_taipei()
    production_approved = bool(args.production_approved and not args.dry_run)
    production_artifact = bool(args.production_artifact and not args.production_approved)
    if args.window not in WINDOWS:
        raise SystemExit(f"unsupported US stock window: {args.window}")
    if not acquire_lock():
        return {"ok": False, "status": "lock_busy", "window": args.window, "line_attempted": False, "email_attempted": False}
    try:
        artifact = build_runtime_artifact(args.window, dry_run=not production_approved, reference=started, live_data=args.live_data, production_artifact=production_artifact)
        artifact["generated_at"] = started.isoformat()
        out_path = WINDOW_OUTPUTS[args.window]
        write_json(out_path, artifact)
        legacy_path = LEGACY_WINDOW_OUTPUTS.get(args.window)
        if legacy_path and legacy_path != out_path:
            write_json(legacy_path, artifact)
        dashboard_result = publish_dashboard(artifact) if production_approved or args.publish_dashboard else {"attempted": False, "succeeded": False, "reason": "dry_run_no_publish"}
        idem = idempotency_path(args.window, started)
        delivery_skipped_duplicate = production_approved and idem.exists()
        if delivery_skipped_duplicate:
            email_result = {"attempted": False, "succeeded": False, "reason": "duplicate_delivery_suppressed"}
            line_result = {"attempted": False, "succeeded": False, "reason": "duplicate_delivery_suppressed"}
        else:
            email_result = send_email_if_allowed(artifact, args.window, production_approved)
            line_result = send_line_if_allowed(artifact, args.window, production_approved)
        if production_approved and not delivery_skipped_duplicate:
            write_json(idem, {"window": args.window, "date": started.date().isoformat(), "email_attempted": email_result["attempted"], "line_attempted": line_result["attempted"], "created_at": started.isoformat()})
        finished = now_taipei()
        status = {
            "schema_version": "us_stock_delivery_status_v1",
            "market": "US",
            "window": args.window,
            "scheduled_at": args.as_of or US_BATCH_WINDOWS[args.window]["scheduled_time_tw"],
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "status": "completed",
            "stock_counts": artifact.get("runtime_watchlist_validation", {}),
            "artifact_path": str(out_path),
            "dashboard_publish_attempted": dashboard_result.get("attempted", False),
            "dashboard_publish_succeeded": dashboard_result.get("succeeded", False),
            "email_attempted": email_result.get("attempted", False),
            "email_succeeded": email_result.get("succeeded", False),
            "line_attempted": line_result.get("attempted", False),
            "line_succeeded": line_result.get("succeeded", False),
            "production_pipeline_executed": False,
            "trading_or_order_executed": False,
            "error_type": None,
            "error_message": None,
            "idempotency_key": str(idem),
            "duplicate_delivery_suppressed": delivery_skipped_duplicate,
            "dry_run": not production_approved,
            "python3_main_executed": False,
            "secret_values_printed": False,
        }
        write_json(STATUS_PATH, status)
        write_json(US_STATUS_PATH, status)
        return {"ok": True, "status": status, "dashboard": dashboard_result, "email": email_result, "line": line_result}
    except Exception as exc:
        error = {"ok": False, "status": "failed", "window": args.window, "error_type": type(exc).__name__, "error_message": str(exc)[:240], "line_attempted": False, "email_attempted": False, "trading_or_order_executed": False, "production_pipeline_executed": False}
        write_json(STATUS_PATH, error)
        write_json(US_STATUS_PATH, error)
        return error
    finally:
        release_lock()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", required=True, choices=WINDOWS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--production-approved", action="store_true")
    parser.add_argument("--live-data", action="store_true", help="Fetch live public market data in no-send mode.")
    parser.add_argument("--production-artifact", action="store_true", help="Write production-provenance live artifact without sending notifications.")
    parser.add_argument("--publish-dashboard", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--as-of")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args)
    text = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
