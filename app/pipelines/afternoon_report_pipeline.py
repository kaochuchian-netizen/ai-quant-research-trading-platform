import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.database.analysis_result_repository import save_analysis_result
from app.database.sqlite_client import init_database
from app.loaders.google_sheet_loader import load_stock_ids
from app.market.adr_score_engine import calculate_adr_score
from app.market.adr_service import get_adr_result
from app.market.stock_name_loader import resolve_stock_name
from app.pipelines.context import create_pipeline_context

from analysis.analysis_engine import analyze_stock
from analysis.chip.chip_analysis_engine import analyze_chip
from analysis.news_analysis_engine import analyze_news
from analysis.news_scoring_engine import calculate_news_score
from analysis.total_scoring_engine import calculate_total_score
from indicators.indicator_engine_v2 import build_indicator_result
from reports.report_formatter_v2 import format_stock_report_v2


def run_afternoon_report_pipeline(pipeline_type, dry_run=False):
    """Generate stock-analysis report content for afternoon scheduler delivery.

    Afternoon windows print full stock report content for Email and Dashboard.
    They intentionally do not send full LINE batches; the approved scheduler
    wrapper sends only concise reminders with the dashboard URL.
    """
    context = create_pipeline_context(pipeline_type)
    print(f"pipeline_type: {context['pipeline_type']}")
    print(f"pipeline_run_id: {context['pipeline_run_id']}")
    print(f"run_date: {context['run_date']}")
    print(f"run_time: {context['run_time']}")

    if dry_run:
        print("dry-run 模式：略過 SQLite 初始化")
    else:
        init_database()

    print(f"{pipeline_type} historical CSV update skipped; using existing report-ready data")

    stock_ids = load_stock_ids()
    selected_stock_ids = [str(stock_id).zfill(4) for stock_id in stock_ids]
    print(f"{pipeline_type} stock universe count: {len(stock_ids)}")
    print(f"{pipeline_type} selected stock ids: {selected_stock_ids}")
    print(f"{pipeline_type} full LINE report disabled; concise scheduler reminder is handled by approved wrapper")

    daily_reports = []
    failed_reports = []
    stock_name_warnings = []

    for stock_id in stock_ids:
        stock_id = str(stock_id).zfill(4)
        stock_name_result = resolve_stock_name(stock_id)
        stock_name = str(stock_name_result["stock_name"])
        if stock_name_result.get("warning"):
            stock_name_warnings.append(
                {
                    "stock_id": stock_id,
                    "source": stock_name_result["source"],
                    "warning": stock_name_result["warning"],
                }
            )
            print(
                f"{pipeline_type} stock name fallback for {stock_id}: "
                f"{stock_name_result['warning']}"
            )
        print(f"開始分析股票：{stock_name}({stock_id})")

        csv_path = f"data/historical/{stock_id}_daily.csv"
        if not os.path.exists(csv_path):
            reason = f"找不到歷史資料 {csv_path}"
            print(f"略過股票 {stock_name}({stock_id})：{reason}")
            failed_reports.append({"stock_id": stock_id, "stock_name": stock_name, "reason": reason})
            continue

        try:
            indicator_result = build_indicator_result(stock_id, csv_path)
            technical_score = indicator_result.get("score", {}).get("bullish_score", 50)

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
                    signal_session=pipeline_type,
                    pipeline_type=context["pipeline_type"],
                    pipeline_run_id=context["pipeline_run_id"],
                    signal_time=datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
                    is_backtest_eligible=0,
                    schema_version=1,
                )
                print(f"SQLite 已寫入：{stock_name}({stock_id})")

            print(report)
            daily_reports.append(report)

        except Exception as exc:
            reason = exc.__class__.__name__
            print(f"分析失敗：{stock_name}({stock_id})，原因類型：{reason}")
            failed_reports.append({"stock_id": stock_id, "stock_name": stock_name, "reason": reason})

    result = {
        "pipeline_type": context["pipeline_type"],
        "pipeline_run_id": context["pipeline_run_id"],
        "run_date": context["run_date"],
        "run_time": context["run_time"],
        "dry_run": dry_run,
        "content_state": "stock_analysis_reports_available" if daily_reports else "stock_analysis_reports_unavailable",
        "report_count": len(daily_reports),
        "failed_count": len(failed_reports),
        "stock_name_fallback_count": len(stock_name_warnings),
        "stock_name_warnings": stock_name_warnings,
        "full_line_report_disabled": True,
        "trading_order_portfolio_action": False,
    }
    print("pipeline_report_summary:")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result
