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
from app.market.shioaji_client import get_snapshots
from app.market.snapshot_normalizer import normalize_snapshots
from app.pipelines.context import create_pipeline_context
from app.dashboard.window_snapshot_archive import load_admitted_snapshots
from app.reports.tw_four_window_decision import aggregate_cards, build_observed_card, stable_hash

from analysis.analysis_engine import analyze_stock
from analysis.chip.chip_analysis_engine import analyze_chip
from analysis.news_analysis_engine import analyze_news
from analysis.news_scoring_engine import calculate_news_score
from analysis.total_scoring_engine import calculate_total_score
from indicators.indicator_engine_v2 import build_indicator_result
from reports.report_formatter_v2 import format_stock_report_v2
from app.runtime.stage_timing import StageTimingRecorder, TW_INTRADAY_1305_BUDGET, record_stage_result

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
    effective_trading_date = str(context.get("run_date") or datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat())
    source_dates = sorted({str(card.get("source_data_date")) for card in cards if card.get("source_data_date")})
    summary = aggregate_cards(window, cards)
    structured_key = {
        "intraday_1305": "structured_intraday_cards",
        "pre_close_1335": "structured_pre_close_cards",
        "post_close_1500": "structured_review_cards",
    }[window]
    observed_times = sorted({str(card.get("market_data_as_of")) for card in cards if card.get("market_data_as_of")})
    payload = {
        "schema_version": "tw_window_decision_runtime_v2",
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
        "effective_trading_date": effective_trading_date,
        "source_data_time": observed_times[-1] if observed_times else None,
        "source_data_dates": source_dates,
        "source_data_time_status": "observed" if observed_times else "unavailable",
        "cards": cards,
        structured_key: cards,
        "tw_window_summary": summary,
        "tracking_stock_count": summary["tracking_count"],
        "structured_card_count": summary["structured_card_count"],
        "tracking_symbols": summary["symbols"],
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
    window = WINDOW_BY_PIPELINE[pipeline_type]
    timing_root = (
        Path(os.environ.get("STOCK_AI_STAGE_TIMING_DIR", "/tmp/stock-ai-stage-timing"))
        if dry_run else REPO_ROOT / "artifacts/runtime/stage_timing"
    )
    timing_path = timing_root / f"tw_{window}_latest.json"
    timing = StageTimingRecorder(
        timing_path, market="TW", window=window,
        run_id=context["pipeline_run_id"], budget=TW_INTRADAY_1305_BUDGET,
    )
    timing.heartbeat("entrypoint", "pipeline_context_created")
    print(f"pipeline_type: {context['pipeline_type']}")
    print(f"pipeline_run_id: {context['pipeline_run_id']}")
    print(f"run_date: {context['run_date']}")
    print(f"run_time: {context['run_time']}")

    if dry_run:
        print("dry-run 模式：略過 SQLite 初始化")
    else:
        with timing.stage("entrypoint"):
            init_database()

    print(f"{pipeline_type} historical CSV update skipped; using existing report-ready data")

    with timing.stage("market_data"):
        stock_ids = load_stock_ids()
    record_stage_result(timing_path, "fundamentals", status="not_applicable", elapsed_seconds=0)
    selected_stock_ids = [str(stock_id).zfill(4) for stock_id in stock_ids]
    quote_failure = None
    try:
        with timing.stage("observed_market_data"):
            quotes = normalize_snapshots(get_snapshots(selected_stock_ids))
    except Exception as exc:
        quote_failure = exc.__class__.__name__
        quotes = []
        record_stage_result(timing_path, "observed_market_data", status="failed_optional", elapsed_seconds=0, reason=quote_failure)
    quotes_by_symbol = {str(item.get("stock_id") or "").zfill(4): item for item in quotes}
    same_day_admitted = [
        item for item in load_admitted_snapshots(REPO_ROOT / "artifacts/archive/window_snapshots")
        if item.get("market") == "TW"
        and item.get("effective_trading_date") == context["run_date"]
    ]
    admitted = [item for item in same_day_admitted if item.get("window") == "pre_open_0700"]
    setup_snapshot = max(admitted, key=lambda item: int(item.get("revision") or 0), default=None)
    setup_payload = setup_snapshot.get("payload", {}) if setup_snapshot else {}
    setup_cards = setup_payload.get("structured_pre_open_cards", []) if isinstance(setup_payload, dict) else []
    setups_by_symbol = {str(item.get("symbol") or item.get("stock_id") or "").zfill(4): item for item in setup_cards if isinstance(item, dict)}
    prior_window = {"pre_close_1335": "intraday_1305", "post_close_1500": "pre_close_1335"}.get(window)
    prior_candidates = [item for item in same_day_admitted if item.get("window") == prior_window]
    prior_snapshot = max(prior_candidates, key=lambda item: int(item.get("revision") or 0), default=None)
    prior_payload = prior_snapshot.get("payload", {}) if prior_snapshot else {}
    prior_key = {"intraday_1305": "structured_intraday_cards", "pre_close_1335": "structured_pre_close_cards"}.get(prior_window or "")
    prior_cards = prior_payload.get(prior_key, []) if prior_key and isinstance(prior_payload, dict) else []
    prior_by_symbol = {str(item.get("symbol") or item.get("stock_id") or "").zfill(4): item for item in prior_cards if isinstance(item, dict)}
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
            timing.heartbeat("technical", stock_id)
            with timing.stage("technical"):
                indicator_result = build_indicator_result(stock_id, csv_path)
            technical_score = indicator_result.get("score", {}).get("bullish_score", 50)

            try:
                with timing.stage("adr", optional=True):
                    adr_result = get_adr_result(stock_id)
                    adr_score = calculate_adr_score(adr_result)
            except Exception as exc:
                adr_result, adr_score = {"status": "unavailable", "reason": exc.__class__.__name__}, 50

            try:
                with timing.stage("news", optional=True):
                    news_result = analyze_news(stock_id, stock_name)
                    news_score_result = calculate_news_score(news_result)
                    news_score = news_score_result.get("score", 50)
            except Exception as exc:
                news_result, news_score = {"status": "unavailable", "reason": exc.__class__.__name__}, 50

            try:
                with timing.stage("chip", optional=True):
                    chip_result = analyze_chip(stock_id)
                    chip_score = chip_result.get("chip_score", 50)
            except Exception as exc:
                chip_result, chip_score = {"status": "unavailable", "reason": exc.__class__.__name__}, 50

            with timing.stage("strategy"):
                total_score_result = calculate_total_score(
                    technical_score=technical_score,
                    news_score=news_score,
                    adr_score=adr_score,
                    chip_score=chip_score,
                )

            with timing.stage("prediction", optional=True):
                ai_analysis = analyze_stock(
                    indicator_result=indicator_result,
                    adr_result=adr_result,
                    news_result=news_result,
                )

            with timing.stage("formatter"):
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
            setup = setups_by_symbol.get(stock_id) or {
                "symbol": stock_id, "stock_id": stock_id, "name": stock_name,
                "stock_name": stock_name, "trading_date": context["run_date"],
                "setup_id": None, "entry_readiness": "unavailable", "strategy_type": "unavailable",
                "missing_fields": ["same_day_admitted_pre_open_setup"], "strategies": {"daily_tactical": {}},
            }
            quote = dict(quotes_by_symbol.get(stock_id) or {})
            if not quote and quote_failure:
                quote["source_error_category"] = quote_failure
            prior_card = dict(prior_by_symbol.get(stock_id) or {})
            prior_timeline = prior_card.get("lifecycle_timeline") if isinstance(prior_card.get("lifecycle_timeline"), list) else None
            if prior_card and prior_snapshot:
                prior_card.update({
                    "window": prior_window,
                    "source_snapshot_id": prior_snapshot.get("snapshot_id"),
                    "source_revision": int(prior_snapshot.get("revision") or 0),
                    "parent_source_payload_hash": stable_hash(prior_payload),
                })
            decision_cards.append(build_observed_card(
                window=window, setup_card=setup, quote=quote,
                trading_date=context["run_date"],
                generated_at=datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat(),
                source_snapshot_id=setup_snapshot.get("snapshot_id") if setup_snapshot else None,
                source_revision=int(setup_snapshot.get("revision") or 0) if setup_snapshot else 0,
                source_payload_hash=stable_hash(setup_payload) if setup_snapshot else None,
                prior_card=prior_card or None,
                lifecycle_timeline=prior_timeline,
            ))

        except Exception as exc:
            reason = exc.__class__.__name__
            print(f"分析失敗：{stock_name}({stock_id})，原因類型：{reason}")
            failed_reports.append({"stock_id": stock_id, "stock_name": stock_name, "reason": reason})

    if not decision_cards and not dry_run:
        timing.fail(stage="runtime_write", category="runtime_write_failure", reason="no_valid_decision_cards")
        raise RuntimeError("no_valid_decision_cards")
    with timing.stage("runtime_write"):
        runtime_path = None if dry_run else _write_window_runtime(pipeline_type, context, decision_cards)
    # These stages belong to the approved wrapper; record explicit handoff so
    # the pipeline artifact never implies they happened here.
    for handoff in ("snapshot_admission", "archive_build", "publish", "notification_format", "delivery"):
        timing.heartbeat(handoff, "pending_approved_wrapper")
    timing.complete()
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
        "stage_timing_path": str(timing_path),
    }
    print("pipeline_report_summary:")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result
