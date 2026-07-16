import json
import os
from datetime import datetime
from pathlib import Path
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

REPO_ROOT = Path(__file__).resolve().parents[2]
WINDOW_BY_PIPELINE = {"intraday": "intraday_1305", "pre_close": "pre_close_1335", "post_close": "post_close_1500"}


def _decision_state(action):
    text = str(action or "")
    return {
        "hold_candidate": any(token in text for token in ("續抱", "加碼")),
        "avoid_hold": "降低追價" in text,
        "no_trade": any(token in text for token in ("中性觀察", "保守觀望", "暫不操作")),
        "late_session_risk": any(token in text for token in ("降低追價", "保守觀望")),
        "tomorrow_watch": any(token in text for token in ("續抱", "加碼", "中性觀察")),
        "near_target": None,
        "near_stop": None,
        "setup_triggered": None,
        "setup_invalidated": None,
    }


def _write_window_runtime(pipeline_type, context, cards, runtime_dir=None):
    window = WINDOW_BY_PIPELINE[pipeline_type]
    source_dates = sorted({str(card.get("source_data_date")) for card in cards if card.get("source_data_date")})
    payload = {
        "schema_version": "tw_window_decision_runtime_v1",
        "artifact_type": "tw_window_decision_runtime",
        "artifact_mode": "production_runtime",
        "runtime_provenance": "scheduled_production",
        "fixture": False,
        "validator": False,
        "validation_only": False,
        "market": "TW",
        "window": window,
        "pipeline_type": pipeline_type,
        "pipeline_run_id": context["pipeline_run_id"],
        "generated_at": datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat(),
        "source_data_time": None,
        "source_data_dates": source_dates,
        "source_data_time_status": "unavailable_no_intraday_timestamp",
        "cards": cards,
        "stock_count": len(cards),
        "trading_or_order_executed": False,
    }
    target = Path(runtime_dir) / f"{window}_latest.json" if runtime_dir else REPO_ROOT / "artifacts/runtime/tw_window_decision" / f"{window}_latest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


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
    decision_cards = []
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
            action = total_score_result.get("action")
            decision_cards.append({
                "stock_id": stock_id,
                "stock_name": stock_name,
                "source_data_date": indicator_result.get("date"),
                "source_data_time": None,
                "current_price": indicator_result.get("close"),
                "rating": total_score_result.get("rating"),
                "total_score": total_score_result.get("total_score"),
                "action": action,
                "decision_state": _decision_state(action),
                "strategies": {"daily_tactical": {
                    "action": action,
                    "rating": total_score_result.get("rating"),
                    "score": total_score_result.get("total_score"),
                    "confidence": total_score_result.get("total_score"),
                    "entry_zone": None,
                    "target_1": None,
                    "target_2": None,
                    "stop_invalidation": None,
                    "source_data_date": indicator_result.get("date"),
                    "source_data_time": None,
                }},
            })

        except Exception as exc:
            reason = exc.__class__.__name__
            print(f"分析失敗：{stock_name}({stock_id})，原因類型：{reason}")
            failed_reports.append({"stock_id": stock_id, "stock_name": stock_name, "reason": reason})

    runtime_path = None if dry_run else _write_window_runtime(pipeline_type, context, decision_cards)
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
        "window_runtime_path": str(runtime_path) if runtime_path else None,
        "window_runtime_card_count": len(decision_cards),
    }
    print("pipeline_report_summary:")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result
