import json
import os
from datetime import datetime
from pathlib import Path
from time import monotonic
from zoneinfo import ZoneInfo

from app.loaders.google_sheet_loader import load_stock_ids
from app.market.stock_name_loader import resolve_stock_name
from app.market.adr_service import get_adr_result
from app.market.adr_score_engine import calculate_adr_score
from app.pipelines.context import create_pipeline_context
from app.database.sqlite_client import init_database
from app.database.analysis_result_repository import save_analysis_result

from indicators.indicator_engine_v2 import build_indicator_result

from analysis.analysis_engine import analyze_stock
from analysis.news_analysis_engine import analyze_news
from analysis.news_scoring_engine import calculate_news_score
from analysis.total_scoring_engine import calculate_total_score
from analysis.chip.chip_analysis_engine import analyze_chip
from analysis.backtest_auto_updater import run_backtest_auto_update

from reports.report_formatter_v2 import (
    format_stock_report_v2,
    format_multi_stock_report_v2,
)
from reports.line_report_sender import send_line_report
from reports.line_short_formatter import format_line_short
from app.dashboard.dashboard_url_registry import get_delivery_dashboard_url
from app.reports.tw_pre_open_structured import aggregate as aggregate_pre_open_cards
from app.reports.tw_pre_open_structured import build_card as build_pre_open_card
from app.reports.tw_pre_open_structured import render_line as render_pre_open_line
from app.reports.tw_pre_open_structured import unavailable_card as build_unavailable_pre_open_card
from app.strategy.tw_daily_tactical import build_runtime as build_tw_daily_tactical_runtime

from scripts.update_historical_csv import main as update_historical_csv


LINE_BATCH_SIZE = 3

STAGE_TIMING_PATH = Path("artifacts/runtime/pre_open_stage_timing_latest.json")
PRE_OPEN_RUNTIME_PATH = Path("artifacts/runtime/tw_window_decision/pre_open_0700_latest.json")


def _now_taipei():
    return datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")


class StageTiming:
    def __init__(self, window, pipeline_run_id):
        self.window = window
        self.pipeline_run_id = pipeline_run_id
        self.started_at = _now_taipei()
        self.events = []
        self._active = {}
        self._write("started")

    def start(self, stage, **metadata):
        self._active[stage] = monotonic()
        self.events.append({"stage": stage, "status": "started", "at": _now_taipei(), **metadata})
        self._write(stage)
        print(f"stage_start: {stage}", flush=True)

    def finish(self, stage, status="completed", **metadata):
        started = self._active.pop(stage, None)
        elapsed = None if started is None else round(monotonic() - started, 3)
        self.events.append({"stage": stage, "status": status, "at": _now_taipei(), "elapsed_seconds": elapsed, **metadata})
        self._write(stage)
        print(f"stage_{status}: {stage} elapsed_seconds={elapsed}", flush=True)

    def _write(self, current_stage):
        payload = {
            "schema_version": "pre_open_stage_timing_v1",
            "window": self.window,
            "pipeline_run_id": self.pipeline_run_id,
            "started_at": self.started_at,
            "last_updated_at": _now_taipei(),
            "current_stage": current_stage,
            "events": self.events,
        }
        STAGE_TIMING_PATH.parent.mkdir(parents=True, exist_ok=True)
        STAGE_TIMING_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_pre_open_runtime(context, cards, tracking_symbols):
    summary = aggregate_pre_open_cards(cards, tracking_symbols)
    generated_at = _now_taipei()
    source_dates = sorted(
        {
            str((card.get("data_freshness") or {}).get("market_data_as_of"))[:10]
            for card in cards
            if (card.get("data_freshness") or {}).get("market_data_as_of")
        }
    )
    payload = {
        "schema_version": "tw_pre_open_decision_runtime_v1",
        "artifact_type": "tw_window_decision_runtime",
        "artifact_mode": "scheduled_production",
        "runtime_provenance": "scheduled_production",
        "run_kind": "scheduled",
        "fixture": False,
        "validation_only": False,
        "dry_run": False,
        "status": "completed",
        "market": "TW",
        "window": "pre_open_0700",
        "pipeline_run_id": context["pipeline_run_id"],
        "effective_trading_date": context["run_date"],
        "generated_at": generated_at,
        "source_data_dates": source_dates,
        "source_data_time": None,
        "source_data_time_status": "date_only" if source_dates else "unavailable",
        "tracking_stock_count": summary["tracking_stock_count"],
        "tracking_symbols": summary["tracking_symbols"],
        "structured_card_count": summary["structured_card_count"],
        "rendered_card_count": summary["rendered_card_count"],
        "structured_pre_open_cards": cards,
        "cards": cards,
        "pre_open_summary": summary,
        "email_attempted": False,
        "line_attempted": False,
        "trading_or_order_executed": False,
    }
    PRE_OPEN_RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = PRE_OPEN_RUNTIME_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, PRE_OPEN_RUNTIME_PATH)
    return payload



def send_reports_in_batches(reports, batch_size=LINE_BATCH_SIZE, dry_run=False, structured_payload=None):
    if not reports:
        print("沒有可推播的報告")
        return

    for index in range(0, len(reports), batch_size):
        if structured_payload:
            message = render_pre_open_line(
                structured_payload,
                get_delivery_dashboard_url("TW", "pre_open_0700", ""),
            )
        else:
            message = format_line_short({"scheduler_window": "pre_open_0700"})

        print("LINE link-only reminder prepared; per-stock details are available on Dashboard only")

        if dry_run or os.environ.get("STOCK_AI_SUPPRESS_NOTIFICATIONS") == "1":
            print("dry-run 模式：略過 LINE 推播，短提醒內容如下")
            print(message)
            break

        send_line_report(message)
        break


def run_pre_open_pipeline(dry_run=False, limit=None):
    context = create_pipeline_context("pre_open")
    stage_timing = StageTiming("pre_open_0700", context["pipeline_run_id"])
    print(f"pipeline_type: {context['pipeline_type']}", flush=True)
    print(f"pipeline_run_id: {context['pipeline_run_id']}", flush=True)
    print(f"run_date: {context['run_date']}", flush=True)
    print(f"run_time: {context['run_time']}", flush=True)

    if dry_run:
        print("dry-run 模式：略過 SQLite 初始化")
    else:
        init_database()

    if dry_run:
        print("dry-run 模式：略過 historical CSV 更新")
        pipeline_pre_delivery_status = {
            "schema_version": "pipeline_pre_delivery_status_v1",
            "stage": "historical_csv_update",
            "status": "skipped_for_dry_run",
            "report_ready_available": True,
            "warnings": [],
        }
    else:
        print("開始更新 historical CSV", flush=True)
        stage_timing.start("historical_csv_update")
        pipeline_pre_delivery_status = update_historical_csv()
        stage_timing.finish(
            "historical_csv_update",
            updated_count=pipeline_pre_delivery_status.get("updated_count"),
            fallback_count=pipeline_pre_delivery_status.get("fallback_count"),
            failed_count=pipeline_pre_delivery_status.get("failed_count"),
        )
        print("pipeline_pre_delivery_status:", flush=True)
        print(json.dumps(pipeline_pre_delivery_status, ensure_ascii=False, sort_keys=True), flush=True)
        if pipeline_pre_delivery_status.get("historical_update_completed"):
            print("historical CSV 更新完成")
        elif pipeline_pre_delivery_status.get("report_ready_available"):
            print("historical CSV 更新未完全成功，改用 fallback historical CSV 繼續產生報告")
        else:
            print("historical CSV 更新失敗且 fallback 不足，pipeline 將繼續嘗試既有逐檔檢查")

    stage_timing.start("load_stock_universe")
    stock_ids = load_stock_ids()
    stage_timing.finish("load_stock_universe", stock_count=len(stock_ids))
    print(f"pre_open stock universe count: {len(stock_ids)}", flush=True)
    print(f"pre_open dry_run: {dry_run}")
    print(f"pre_open limit: {limit}")

    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        stock_ids = stock_ids[:limit]

    selected_stock_ids = [str(stock_id).zfill(4) for stock_id in stock_ids]
    stage_timing.start("strategy_setup")
    tactical_runtime = build_tw_daily_tactical_runtime()
    tactical_by_symbol = {
        str(card.get("stock_id") or "").zfill(4): ((card.get("strategies") or {}).get("daily_tactical") or {})
        for card in tactical_runtime.get("cards", [])
    }
    stage_timing.finish("strategy_setup", tactical_card_count=len(tactical_by_symbol))
    print(f"pre_open selected stock count: {len(stock_ids)}")
    print(f"pre_open selected stock ids: {selected_stock_ids}")

    daily_reports = []
    failed_reports = []
    stock_name_warnings = []
    structured_cards = []

    for stock_id in stock_ids:
        stock_id = str(stock_id).zfill(4)
        stock_name_result = resolve_stock_name(stock_id)
        stock_name = str(stock_name_result["stock_name"])
        if stock_name_result.get("warning"):
            warning = {
                "stock_id": stock_id,
                "source": stock_name_result["source"],
                "warning": stock_name_result["warning"],
            }
            stock_name_warnings.append(warning)
            print(
                f"pre_open stock name fallback for {stock_id}: "
                f"{stock_name_result['warning']}"
            )

        stage_name = f"stock_analysis_{stock_id}"
        stage_timing.start(stage_name, stock_id=stock_id, stock_name=stock_name)
        print(f"開始分析股票：{stock_name}({stock_id})", flush=True)

        csv_path = f"data/historical/{stock_id}_daily.csv"

        if not os.path.exists(csv_path):
            print(f"略過股票 {stock_name}({stock_id})：找不到歷史資料 {csv_path}")
            failed_reports.append(
                {
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "reason": f"找不到歷史資料 {csv_path}",
                }
            )
            structured_cards.append(
                build_unavailable_pre_open_card(
                    stock_id,
                    stock_name,
                    context["run_date"],
                    "missing_historical_csv",
                )
            )
            stage_timing.finish(stage_name, status="failed", reason="missing_historical_csv")
            continue

        try:
            indicator_result = build_indicator_result(stock_id, csv_path)

            technical_score = indicator_result.get("score", {}).get(
                "bullish_score",
                50,
            )

            adr_result = get_adr_result(stock_id)
            adr_score = calculate_adr_score(adr_result)

            news_result = analyze_news(stock_id, stock_name)
            news_score_result = calculate_news_score(news_result)
            news_score = news_score_result.get("score", 50)

            chip_result = analyze_chip(stock_id)
            chip_score = chip_result.get("chip_score", 50)


            total_score_result = calculate_total_score(
                technical_score=technical_score,
                news_score=news_score,
                adr_score=adr_score,
                chip_score=chip_score,
            )

            ai_analysis = analyze_stock(
                indicator_result=indicator_result,
                adr_result=adr_result,
                news_result=news_result,
            )

            report = format_stock_report_v2(
                stock_id=stock_id,
                stock_name=stock_name,
                indicator_result=indicator_result,
                ai_analysis=ai_analysis,
                adr_result=adr_result,
                news_result=news_result,
                total_score_result=total_score_result,
                chip_result=chip_result,
            )

            if dry_run:
                print(f"dry-run 模式：略過 SQLite 寫入：{stock_name}({stock_id})")
            else:
                save_analysis_result(
                    stock_id=stock_id,
                    stock_name=stock_name,
                    indicator_result=indicator_result,
                    technical_score=technical_score,
                    news_score=news_score,
                    adr_score=adr_score,
                    chip_score=chip_score,
                    total_score_result=total_score_result,
                    report_text=report,
                    signal_session="pre_open",
                    pipeline_type=context["pipeline_type"],
                    pipeline_run_id=context["pipeline_run_id"],
                    signal_time=datetime.now(
                        ZoneInfo("Asia/Taipei"),
                    ).isoformat(timespec="seconds"),
                    is_backtest_eligible=1,
                    schema_version=1,
                )

                print(f"SQLite 已寫入：{stock_name}({stock_id})")
            print(report, flush=True)
            daily_reports.append(report)
            structured_cards.append(
                build_pre_open_card(
                    symbol=stock_id,
                    name=stock_name,
                    trading_date=context["run_date"],
                    indicator=indicator_result,
                    adr=adr_result,
                    news=news_result,
                    chip=chip_result,
                    score=total_score_result,
                    analysis=ai_analysis,
                    tactical=tactical_by_symbol.get(stock_id),
                    missing_fields=[
                        source_name
                        for source_name, source_value in (
                            ("adr", adr_result),
                            ("news", news_result),
                            ("chip", chip_result),
                        )
                        if source_value in (None, [], {})
                    ],
                )
            )
            stage_timing.finish(stage_name, report_ready=True)

        except Exception as e:
            reason = e.__class__.__name__
            print(f"分析失敗：{stock_name}({stock_id})，原因類型：{reason}", flush=True)
            failed_reports.append({"stock_id": stock_id, "stock_name": stock_name, "reason": reason})
            structured_cards.append(
                build_unavailable_pre_open_card(
                    stock_id,
                    stock_name,
                    context["run_date"],
                    f"analysis_failed:{reason}",
                )
            )
            stage_timing.finish(stage_name, status="failed", reason=reason)

    pre_open_summary = aggregate_pre_open_cards(structured_cards, selected_stock_ids)
    window_runtime = None
    if dry_run:
        print("dry-run 模式：略過正式 07:00 window runtime 寫入")
    else:
        stage_timing.start("window_runtime_write")
        window_runtime = _write_pre_open_runtime(context, structured_cards, selected_stock_ids)
        stage_timing.finish(
            "window_runtime_write",
            structured_card_count=window_runtime["structured_card_count"],
            tracking_stock_count=window_runtime["tracking_stock_count"],
        )

    stage_timing.start("line_link_only_reminder")
    line_payload = window_runtime or {
        "effective_trading_date": context["run_date"],
        "generated_at": _now_taipei(),
        "tracking_symbols": selected_stock_ids,
        "structured_pre_open_cards": structured_cards,
        "pre_open_summary": pre_open_summary,
    }
    send_reports_in_batches(
        daily_reports,
        dry_run=dry_run,
        structured_payload=line_payload,
    )
    stage_timing.finish("line_link_only_reminder", report_count=len(daily_reports))

    result = {
        "pipeline_type": context["pipeline_type"],
        "pipeline_run_id": context["pipeline_run_id"],
        "run_date": context["run_date"],
        "run_time": context["run_time"],
        "dry_run": dry_run,
        "content_state": "stock_analysis_reports_available" if daily_reports else "stock_analysis_reports_unavailable",
        "report_count": len(daily_reports),
        "failed_count": len(failed_reports),
        "tracking_stock_count": pre_open_summary["tracking_stock_count"],
        "structured_card_count": pre_open_summary["structured_card_count"],
        "pre_open_summary": pre_open_summary,
        "window_runtime_path": str(PRE_OPEN_RUNTIME_PATH) if window_runtime else None,
        "stock_name_fallback_count": len(stock_name_warnings),
        "stock_name_warnings": stock_name_warnings,
        "full_line_report_disabled": bool(dry_run),
        "trading_order_portfolio_action": False,
    }
    print("pipeline_report_summary:")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    print("每日總結推播完成")

    if dry_run:
        print("dry-run 模式：略過回測自動補值")
    else:
        stage_timing.start("backtest_auto_update")
        run_backtest_auto_update()
        stage_timing.finish("backtest_auto_update")

    stage_timing.finish("pipeline", report_count=len(daily_reports), failed_count=len(failed_reports))

    return result
