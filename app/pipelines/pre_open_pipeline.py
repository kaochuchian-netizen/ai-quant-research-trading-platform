import os

from app.loaders.google_sheet_loader import load_stock_ids
from app.market.stock_name_loader import get_stock_name
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


def run_pre_open_pipeline(dry_run=False):
    context = create_pipeline_context("pre_open")
    print(f"pipeline_type: {context['pipeline_type']}")
    print(f"pipeline_run_id: {context['pipeline_run_id']}")
    print(f"run_date: {context['run_date']}")
    print(f"run_time: {context['run_time']}")

    if dry_run:
        print("dry-run 模式：略過 SQLite 初始化")
    else:
        init_database()

    if dry_run:
        print("dry-run 模式：略過 historical CSV 更新")
    else:
        print("開始更新 historical CSV")
        update_historical_csv()
        print("historical CSV 更新完成")

    stock_ids = load_stock_ids()
    daily_reports = []

    for stock_id in stock_ids:
        stock_id = str(stock_id).zfill(4)
        stock_name = get_stock_name(stock_id)

        print(f"開始分析股票：{stock_name}({stock_id})")

        csv_path = f"data/historical/{stock_id}_daily.csv"

        if not os.path.exists(csv_path):
            print(f"略過股票 {stock_name}({stock_id})：找不到歷史資料 {csv_path}")
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
                )

                print(f"SQLite 已寫入：{stock_name}({stock_id})")
            print(report)
            daily_reports.append(report)

        except Exception as e:
            print(f"分析失敗：{stock_name}({stock_id})，原因：{e}")

    send_reports_in_batches(daily_reports, dry_run=dry_run)

    print("每日總結推播完成")

    if dry_run:
        print("dry-run 模式：略過回測自動補值")
    else:
        run_backtest_auto_update()
