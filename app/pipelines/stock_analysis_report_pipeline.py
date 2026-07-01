import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.database.analysis_result_repository import save_analysis_result
from app.database.sqlite_client import init_database
from app.loaders.google_sheet_loader import load_stock_ids
from app.market.adr_score_engine import calculate_adr_score
from app.market.adr_service import get_adr_result
from app.market.stock_name_loader import get_stock_name
from app.pipelines.context import create_pipeline_context

from analysis.analysis_engine import analyze_stock
from analysis.backtest_auto_updater import run_backtest_auto_update
from analysis.chip.chip_analysis_engine import analyze_chip
from analysis.news_analysis_engine import analyze_news
from analysis.news_scoring_engine import calculate_news_score
from analysis.total_scoring_engine import calculate_total_score
from indicators.indicator_engine_v2 import build_indicator_result
from reports.line_report_sender import send_line_report
from reports.report_formatter_v2 import format_multi_stock_report_v2, format_stock_report_v2
from scripts.update_historical_csv import main as update_historical_csv


LINE_BATCH_SIZE = 3


def send_reports_in_batches(reports, batch_size=LINE_BATCH_SIZE, dry_run=False):
    if not reports:
        print("沒有可推播的報告")
        return

    for index in range(0, len(reports), batch_size):
        batch = reports[index:index + batch_size]
        message = format_multi_stock_report_v2(batch)

        print(f"推播第 {index // batch_size + 1} 批，共 {len(batch)} 檔")

        if dry_run:
            print("dry-run 模式：略過 LINE 推播，批次內容如下")
            print(message)
            continue

        send_line_report(message)


def run_stock_analysis_report_pipeline(
    pipeline_type,
    dry_run=False,
    limit=None,
    update_historical=False,
    write_results=True,
    send_full_line_report=False,
    run_backtest_update_after=False,
):
    """Run a stock-analysis report pipeline and print report text for delivery.

    Afternoon scheduler windows reuse the same analysis/report content builder as
    the 07:00 pre-open flow, but keep full LINE report delivery disabled. The
    approved scheduler wrapper is responsible for concise afternoon LINE notices.
    """
    context = create_pipeline_context(pipeline_type)
    print(f"pipeline_type: {context['pipeline_type']}")
    print(f"pipeline_run_id: {context['pipeline_run_id']}")
    print(f"run_date: {context['run_date']}")
    print(f"run_time: {context['run_time']}")

    if dry_run:
        print("dry-run 模式：略過 SQLite 初始化")
    elif write_results:
        init_database()
    else:
        print(f"{pipeline_type} SQLite write disabled")

    if update_historical:
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
            print("開始更新 historical CSV")
            pipeline_pre_delivery_status = update_historical_csv()
            print("pipeline_pre_delivery_status:")
            print(json.dumps(pipeline_pre_delivery_status, ensure_ascii=False, sort_keys=True))
            if pipeline_pre_delivery_status.get("historical_update_completed"):
                print("historical CSV 更新完成")
            elif pipeline_pre_delivery_status.get("report_ready_available"):
                print("historical CSV 更新未完全成功，改用 fallback historical CSV 繼續產生報告")
            else:
                print("historical CSV 更新失敗且 fallback 不足，pipeline 將繼續嘗試既有逐檔檢查")
    else:
        print(f"{pipeline_type} historical CSV update skipped; using existing report-ready data")

    stock_ids = load_stock_ids()
    print(f"{pipeline_type} stock universe count: {len(stock_ids)}")
    print(f"{pipeline_type} dry_run: {dry_run}")
    print(f"{pipeline_type} limit: {limit}")

    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        stock_ids = stock_ids[:limit]

    selected_stock_ids = [str(stock_id).zfill(4) for stock_id in stock_ids]
    print(f"{pipeline_type} selected stock count: {len(stock_ids)}")
    print(f"{pipeline_type} selected stock ids: {selected_stock_ids}")

    daily_reports = []
    failed_reports = []

    for stock_id in stock_ids:
        stock_id = str(stock_id).zfill(4)
        stock_name = get_stock_name(stock_id)

        print(f"開始分析股票：{stock_name}({stock_id})")

        csv_path = f"data/historical/{stock_id}_daily.csv"
        if not os.path.exists(csv_path):
            reason = f"找不到歷史資料 {csv_path}"
            print(f"略過股票 {stock_name}({stock_id})：{reason}")
            failed_reports.append({"stock_id": stock_id, "stock_name": stock_name, "reason": reason})
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
            elif write_results:
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
                    signal_session=pipeline_type,
                    pipeline_type=context["pipeline_type"],
                    pipeline_run_id=context["pipeline_run_id"],
                    signal_time=datetime.now(
                        ZoneInfo("Asia/Taipei"),
                    ).isoformat(timespec="seconds"),
                    is_backtest_eligible=1 if pipeline_type == "pre_open" else 0,
                    schema_version=1,
                )
                print(f"SQLite 已寫入：{stock_name}({stock_id})")

            print(report)
            daily_reports.append(report)

        except Exception as exc:
            reason = exc.__class__.__name__
            print(f"分析失敗：{stock_name}({stock_id})，原因類型：{reason}")
            failed_reports.append({"stock_id": stock_id, "stock_name": stock_name, "reason": reason})

    if send_full_line_report:
        send_reports_in_batches(daily_reports, dry_run=dry_run)
        print("完整 LINE 報告推播完成")
    else:
        print(f"{pipeline_type} full LINE report disabled; concise scheduler reminder is handled by approved wrapper")

    if run_backtest_update_after:
        if dry_run:
            print("dry-run 模式：略過回測自動補值")
        else:
            run_backtest_auto_update()

    result = {
        "pipeline_type": context["pipeline_type"],
        "pipeline_run_id": context["pipeline_run_id"],
        "run_date": context["run_date"],
        "run_time": context["run_time"],
        "dry_run": dry_run,
        "content_state": "stock_analysis_reports_available" if daily_reports else "stock_analysis_reports_unavailable",
        "report_count": len(daily_reports),
        "failed_count": len(failed_reports),
        "send_full_line_report": send_full_line_report,
        "trading_order_portfolio_action": False,
    }
    print("pipeline_report_summary:")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result
