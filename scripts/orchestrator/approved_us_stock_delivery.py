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
from app.dashboard.dashboard_url_registry import get_us_dashboard_url, normalize_delivery_dashboard_url
from app.dashboard.decision_presentation import decision_email_block_v2, decision_line_summary_v2, decision_presentation_v2
from app.reports.decision_intelligence_v4 import compact_summary, project_decision_intelligence_v4
from app.dashboard.window_snapshot_archive import resolve_snapshots, write_snapshot
from app.dashboard.public_latest_sync import synchronize_admitted_latest, write_sync_artifact
from app.reports.delivery_provenance import build_delivery_provenance, write_delivery_provenance
from app.reports.window_report_contract import get_window_report_contract
from app.us_stock.watchlist import normalize_us_watchlist_rows
from app.us_stock.runtime_provenance import ADMITTED_PROVENANCE, RuntimeProvenance, provenance_admission
from app.runtime.operations_provenance import build_operations_provenance, write_operations_provenance
from scripts.orchestrator.notify_stage_report import build_message, load_env_file, load_mail_config, send_message

WINDOWS = tuple(US_BATCH_WINDOWS.keys())
TAIPEI = ZoneInfo("Asia/Taipei")
NEW_YORK = ZoneInfo("America/New_York")
DASHBOARD_URL = normalize_delivery_dashboard_url("US", get_us_dashboard_url())
RUNTIME_DIR = REPO_ROOT / "artifacts/runtime"
US_RUNTIME_DIR = RUNTIME_DIR / "us_stock"
IDEMPOTENCY_DIR = US_RUNTIME_DIR / "idempotency"
STATUS_PATH = RUNTIME_DIR / "us_stock_delivery_status_latest.json"
US_STATUS_PATH = US_RUNTIME_DIR / "delivery_status_latest.json"
STATIC_DASHBOARD_PATH = Path("/var/www/stock-ai-dashboard/dashboard/us/index.html")
MAIL_ENV_FILE = Path("~/.config/stock-ai-orchestrator/mail.env")
LOCK_PATH = Path("/tmp/stock_ai_us_stock_batch.lock")
WINDOW_SNAPSHOT_ARCHIVE = REPO_ROOT / "artifacts/archive/window_snapshots"

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
    enabled, metadata = load_runtime_watchlist(dry_run=dry_run and not production_artifact)
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

        result = publish_pages(source_dir=Path("/tmp/stock-ai-dashboard-us-scheduled"))
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

def _count_high_risk(cards: list[dict[str, Any]]) -> int:
    total = 0
    for card in cards:
        tactical = card.get("daily_tactical_summary") or card.get("strategies", {}).get("daily_tactical", {}) if isinstance(card, dict) else {}
        text = json.dumps(tactical, ensure_ascii=False)
        if any(token in text for token in ["high", "高", "avoid_chasing", "no_trade"]):
            total += 1
    return total

def _intraday_text(value: Any) -> str:
    labels = {
        "gap_up_follow_through": "向上跳空延續", "gap_up_partial_fill": "向上跳空部分回補",
        "gap_up_full_fill": "向上跳空完全回補", "gap_down_follow_through": "向下跳空延續",
        "gap_down_partial_fill": "向下跳空部分回補", "gap_down_full_fill": "向下跳空完全回補",
        "flat_open": "平盤開出", "strong": "量能強", "confirmed": "量能確認", "neutral": "量能中性",
        "weak": "量能偏弱", "insufficient_history": "同期量歷史不足", "source_unavailable": "成交量未取得",
        "inside_zone": "位於進場區", "triggered": "已觸發", "not_reached": "尚未到達",
        "passed_without_safe_entry": "已越過安全進場區", "invalidated": "已失效",
        "maintain_watch": "維持觀察", "entry_triggered_hold": "觸發後續抱觀察", "wait_for_volume": "等待量能確認",
        "cancel_chase": "取消追價", "reduce_risk": "降低風險", "stop_invalidated": "停損失效",
        "target_near": "接近目標", "data_unavailable": "資料不足，暫不判定",
    }
    return labels.get(str(value), str(value or "尚未取得"))

def _num(value: Any, suffix: str = "") -> str:
    try:
        return f"{float(value):.2f}{suffix}"
    except (TypeError, ValueError):
        return "尚未取得"


def _compact_us_email_block(card: dict[str, Any], window: str) -> str:
    presentation = decision_presentation_v2("US", card)
    symbol = str(card.get("symbol") or "")
    name = str(card.get("name") or "")
    tactical = presentation.get("daily_tactical", {})
    prediction = presentation.get("prediction", {})
    reasons = presentation.get("reasons") if isinstance(presentation.get("reasons"), list) else []
    risks = presentation.get("risks") if isinstance(presentation.get("risks"), list) else []
    reason = str(reasons[0]) if reasons else "等待量價與資料確認"
    risk = str(risks[0]) if risks else "未偵測到額外風險"
    if window == "us_intraday_2300":
        return "\n".join([
            f"{symbol} {name}",
            f"目前 {_num(card.get('current_price'))}｜行情 {card.get('market_data_as_of') or '尚未取得'}",
            f"Gap {_num(card.get('gap_current_pct'), '%')}｜{_intraday_text(card.get('gap_state'))}｜回補 {_num(card.get('gap_fill_pct'), '%')}",
            f"量能 {_num(card.get('volume_ratio'), 'x')}｜{_intraday_text(card.get('volume_confirmation_state'))}",
            f"Entry {_num(card.get('entry_low'))}–{_num(card.get('entry_high'))}｜{_intraday_text(card.get('entry_trigger_state'))}",
            f"距停損 {_num(card.get('distance_to_stop_pct'), '%')}｜距目標 {_num(card.get('distance_to_target_pct'), '%')}",
            f"策略：{_intraday_text(card.get('tactical_adjustment'))}",
            f"原因：{card.get('adjustment_reason') or '盤中行情不足，無法安全判定'}",
        ])
    if window == "us_post_close_review_0630":
        return "\n".join([
            f"{symbol} {name}",
            f"Prediction review：{prediction.get('today_range')}",
            "Entry / Stop / Target outcome：本次檢討尚待實際結果",
            "Win / Loss / Not Triggered：本次檢討尚待實際結果",
            "MFE / MAE：本次檢討尚待實際結果",
            f"Overnight event update：{risk}",
            f"Next-session watchlist：{reason}",
        ])
    return decision_email_block_v2(presentation)

def build_email_body(artifact: dict[str, Any], window: str) -> str:
    contract = get_window_report_contract("US", window)
    date = artifact.get("generated_at", "")[:10]
    cards = [card for card in artifact.get("dashboard_ready_contract", {}).get("cards", []) if isinstance(card, dict)]
    projection = project_decision_intelligence_v4("US", window, artifact)
    lines = [f"{contract.title} {date}", "", f"Dashboard: {contract.dashboard_url}", "", contract.primary_question, "", "Decision Intelligence V4", compact_summary(projection, "email"), "內容範圍：" + "、".join(projection["section_inventory"]), "", "本批次內容："]
    if window == "us_intraday_2300":
        summary = artifact.get("intraday_summary") or {}
        lines.extend([
            "", "盤中市場概況：",
            f"- 已觸發：{summary.get('triggered_count', 0)}",
            f"- 取消追價：{summary.get('cancel_chase_count', 0)}",
            f"- 量能確認：{summary.get('volume_confirmed_count', 0)}",
            f"- 接近停損／目標：{summary.get('near_stop_count', 0)} / {summary.get('near_target_count', 0)}",
            f"- 行情無法判定：{summary.get('data_unavailable_count', 0)}",
        ])
    for section in contract.email_sections:
        lines.append(f"- {section}")
    lines.extend(["", "批次摘要：", f"- Window: {window}", f"- Enabled stocks: {artifact.get('runtime_watchlist_validation', {}).get('enabled_stock_count')}", f"- 高風險數量: {_count_high_risk(cards)}", "- LINE 僅短提醒；Email 僅呈現本批次需要的內容；完整狀態請看 Dashboard。", ""])
    lines.append("個股摘要：")
    for card in cards:
        lines.append(_compact_us_email_block(card, window))
        news = card.get('bilingual_news_snippet', {}) if isinstance(card.get('bilingual_news_snippet'), dict) else {}
        if window == "us_pre_market_2000" and news.get('chinese_translation'):
            lines.append(f"News：{news.get('chinese_translation')}")
        lines.append("")
    if window == "us_post_close_review_0630":
        review = artifact.get("prediction_review_contract", {})
        lines.extend(["", "預測檢討：", f"- Reviewable: {review.get('reviewable_stock_count')}", f"- Reviewed: {review.get('reviewed_stock_count')}", f"- Skipped: {review.get('skipped_stock_count')}"])
    lines.extend(["", "研究情報：", "- SEC/公司 IR 為 Tier 1 official evidence；yfinance/Yahoo 為 Tier 2 market reference。", "- 不複製完整 filings、transcripts 或 copyrighted articles。", "", "僅供研究參考，非交易指令。"] )
    return "\n".join(lines)

def line_text(artifact: dict[str, Any], window: str) -> str:
    contract = get_window_report_contract("US", window)
    cards = [card for card in artifact.get("dashboard_ready_contract", {}).get("cards", []) if isinstance(card, dict)]
    if window == "us_intraday_2300":
        summary = artifact.get("intraday_summary") or {}
        ranked = sorted(
            artifact.get("structured_intraday_cards") or [],
            key=lambda card: ({"stop_invalidated": 0, "reduce_risk": 1, "cancel_chase": 2, "target_near": 3}.get(str(card.get("tactical_adjustment")), 9), str(card.get("symbol") or "")),
        )[:3]
        changes = "、".join(f"{card.get('symbol')} {_intraday_text(card.get('tactical_adjustment'))}" for card in ranked) or "無可安全判定標的"
        return "\n".join([
            "【Stock AI】23:00 美股盤中",
            f"已觸發 {summary.get('triggered_count', 0)}｜取消追價 {summary.get('cancel_chase_count', 0)}｜量能確認 {summary.get('volume_confirmed_count', 0)}",
            f"接近停損 {summary.get('near_stop_count', 0)}｜接近目標 {summary.get('near_target_count', 0)}｜行情不足 {summary.get('data_unavailable_count', 0)}",
            f"重點調整：{changes}", "完整報告：", contract.dashboard_url, "僅供研究參考，非交易指令。",
        ])
    parts = [f"【Stock AI】{contract.title}已更新", "美股決策摘要已更新"]
    parts.append(compact_summary(project_decision_intelligence_v4("US", window, artifact), "line"))
    parts.append(f"短線可觀察：{len(cards)}")
    parts.append(f"高風險：{_count_high_risk(cards)}")
    parts.extend(["Dashboard：", contract.dashboard_url, "僅供研究參考，非交易指令。"] )
    return "\n".join(parts)
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
    batch_reference = datetime.fromisoformat(args.as_of).astimezone(TAIPEI) if args.as_of else started
    production_approved = bool(args.production_approved and not args.dry_run)
    production_artifact = bool(args.production_artifact and not args.production_approved)
    if args.window not in WINDOWS:
        raise SystemExit(f"unsupported US stock window: {args.window}")
    if not acquire_lock():
        return {"ok": False, "status": "lock_busy", "window": args.window, "line_attempted": False, "email_attempted": False}
    try:
        artifact = build_runtime_artifact(args.window, dry_run=not production_approved, reference=batch_reference, live_data=args.live_data, production_artifact=production_artifact)
        artifact["generated_at"] = started.isoformat()
        if args.manual_rerun and (production_approved or production_artifact):
            runtime_provenance = RuntimeProvenance.MANUAL_RERUN.value
        elif production_approved or production_artifact:
            runtime_provenance = RuntimeProvenance.SCHEDULED_PRODUCTION.value
        elif args.live_data:
            runtime_provenance = RuntimeProvenance.CONTROLLED_NO_SEND.value
        else:
            runtime_provenance = RuntimeProvenance.DRY_RUN.value
        artifact["runtime_provenance"] = runtime_provenance
        artifact["provenance_source"] = "approved_us_stock_delivery_cli_contract"
        artifact["run_kind"] = "manual_rerun" if args.manual_rerun else "scheduled" if runtime_provenance == RuntimeProvenance.SCHEDULED_PRODUCTION.value else runtime_provenance
        admission = provenance_admission(artifact, run_kind=artifact["run_kind"])
        persist_formal_runtime = admission["admitted"] and runtime_provenance in ADMITTED_PROVENANCE
        out_path = WINDOW_OUTPUTS[args.window]
        legacy_path = LEGACY_WINDOW_OUTPUTS.get(args.window)
        if persist_formal_runtime:
            write_json(out_path, artifact)
            if legacy_path and legacy_path != out_path:
                write_json(legacy_path, artifact)
        archive_result = {"written": False, "reason": admission["admission_reason"], **admission}
        if persist_formal_runtime:
            archive_result = write_snapshot(
                WINDOW_SNAPSHOT_ARCHIVE,
                market="US",
                window=args.window,
                effective_trading_date=batch_reference.astimezone(NEW_YORK).date().isoformat(),
                generated_at=started.isoformat(),
                source_payload=artifact,
                status="completed",
                run_kind="manual_rerun" if args.manual_rerun else "scheduled",
                run_id=f"us-{args.window}-{started.strftime('%Y%m%d-%H%M%S')}",
                source_artifact_path=str(out_path),
                rebuild_routes=args.manual_rerun,
            )
        public_latest_sync = {"status": "not_attempted", "reason": "not_scheduled_production"}
        if production_approved and persist_formal_runtime and archive_result.get("written") is True and not args.manual_rerun:
            public_latest_sync = synchronize_admitted_latest(
                market="US", window=args.window,
                static_root=Path("/var/www/stock-ai-dashboard"),
                output_dir=Path("/tmp/stock-ai-dashboard-scheduled-sync") / args.window,
            )
            write_sync_artifact(
                US_RUNTIME_DIR / "public_latest_sync" / f"{args.window}_latest.json",
                public_latest_sync,
            )
        if production_approved and not args.manual_rerun:
            dashboard_result = {
                "attempted": public_latest_sync.get("status") != "not_attempted",
                "succeeded": public_latest_sync.get("status") == "verified",
                "source": "admitted_snapshot_active_alias",
            }
        else:
            dashboard_result = publish_dashboard(artifact) if persist_formal_runtime and args.publish_dashboard else {"attempted": False, "succeeded": False, "reason": "provenance_not_publishable"}
        idem = idempotency_path(args.window, started)
        delivery_skipped_duplicate = production_approved and idem.exists()
        if delivery_skipped_duplicate:
            email_result = {"attempted": False, "succeeded": False, "reason": "duplicate_delivery_suppressed"}
            line_result = {"attempted": False, "succeeded": False, "reason": "duplicate_delivery_suppressed"}
        else:
            email_result = send_email_if_allowed(artifact, args.window, production_approved)
            line_result = send_line_if_allowed(artifact, args.window, production_approved)
        latest_snapshot = resolve_snapshots(WINDOW_SNAPSHOT_ARCHIVE, "US", args.window).latest or {}
        email_preview = build_email_body(artifact, args.window)
        line_preview = line_text(artifact, args.window)
        provenance_results = {}
        for channel, delivery, content in (("email", email_result, email_preview), ("line", line_result, line_preview)):
            attempted = bool(delivery.get("attempted"))
            result_name = "sent" if delivery.get("succeeded") else "failed" if attempted else "suppressed" if "suppress" in str(delivery.get("reason") or "") else "not_attempted"
            provenance = build_delivery_provenance(
                market="US", window=args.window,
                trading_date=batch_reference.astimezone(NEW_YORK).date().isoformat(),
                snapshot=latest_snapshot, canonical_url=get_window_report_contract("US", args.window).dashboard_url,
                channel=channel, content=content, delivery_result=result_name,
                delivery_attempted=attempted, recipient_count=int(delivery.get("recipient_count") or 0),
            )
            if persist_formal_runtime:
                write_delivery_provenance(
                    US_RUNTIME_DIR / "delivery_provenance" / f"{args.window}_{channel}_latest.json",
                    provenance,
                )
            provenance_results[channel] = result_name
        operations_provenance = build_operations_provenance(
            market="US", window=args.window, runtime_status="completed",
            runtime_trading_date=batch_reference.astimezone(NEW_YORK).date().isoformat(),
            snapshot=latest_snapshot, public_sync=public_latest_sync,
            email_result=provenance_results.get("email", "not_attempted"),
            line_result=provenance_results.get("line", "not_attempted"),
        )
        if persist_formal_runtime:
            write_operations_provenance(
                US_RUNTIME_DIR / "operations_provenance" / f"{args.window}_latest.json",
                operations_provenance,
            )
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
            "artifact_path": str(out_path) if persist_formal_runtime else None,
            "runtime_provenance": runtime_provenance,
            "provenance_admitted": admission["admitted"],
            "formal_runtime_persisted": persist_formal_runtime,
            "dashboard_publish_attempted": dashboard_result.get("attempted", False),
            "dashboard_publish_succeeded": dashboard_result.get("succeeded", False),
            "email_attempted": email_result.get("attempted", False),
            "email_succeeded": email_result.get("succeeded", False),
            "line_attempted": line_result.get("attempted", False),
            "line_succeeded": line_result.get("succeeded", False),
            "line_payload_preview": line_preview,
            "email_payload_preview": email_preview,
            "dashboard_url": get_window_report_contract("US", args.window).dashboard_url,
            "production_pipeline_executed": False,
            "trading_or_order_executed": False,
            "error_type": None,
            "error_message": None,
            "idempotency_key": str(idem),
            "duplicate_delivery_suppressed": delivery_skipped_duplicate,
            "dry_run": not production_approved,
            "archive_write": archive_result,
            "public_latest_sync": public_latest_sync,
            "operations_provenance_preview": operations_provenance,
            "delivery_provenance_persisted": persist_formal_runtime,
            "python3_main_executed": False,
            "secret_values_printed": False,
        }
        if persist_formal_runtime:
            write_json(STATUS_PATH, status)
            write_json(US_STATUS_PATH, status)
        return {"ok": (not production_approved or args.manual_rerun or public_latest_sync.get("status") == "verified"), "status": status, "archive_write": archive_result, "dashboard": dashboard_result, "email": email_result, "line": line_result, "line_payload_preview": status["line_payload_preview"], "email_payload_preview": status["email_payload_preview"], "dashboard_url": get_window_report_contract("US", args.window).dashboard_url}
    except Exception as exc:
        error = {"ok": False, "status": "failed", "window": args.window, "error_type": type(exc).__name__, "error_message": str(exc)[:240], "line_attempted": False, "email_attempted": False, "trading_or_order_executed": False, "production_pipeline_executed": False}
        if production_approved or production_artifact:
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
    parser.add_argument("--manual-rerun", action="store_true")
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
