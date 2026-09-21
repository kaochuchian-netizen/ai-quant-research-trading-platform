#!/usr/bin/env python3
"""Run an isolated AI-DEV-250 2330 post-report path diagnostic.

This does not execute the production 07:00 pipeline, send notifications,
publish a dashboard, or write production runtime artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pipelines.pre_open_pipeline import (  # noqa: E402
    _bounded_post_report_operation,
    _emit_post_report_progress,
    _store_structured_pre_open_card,
)
from app.reports.tw_pre_open_structured import build_card as build_pre_open_card  # noqa: E402


class _DiagnosticStageTiming:
    def __init__(self, pipeline_run_id: str) -> None:
        self.pipeline_run_id = pipeline_run_id
        self.events: list[dict[str, Any]] = []

    def _write(self, _stage: str) -> None:
        return None


def _run(symbol: str, timeout_seconds: int) -> dict[str, Any]:
    started = monotonic()
    stage_timing = _DiagnosticStageTiming(
        f"ai_dev_250_diagnostic_{datetime.now(ZoneInfo('Asia/Taipei')).strftime('%Y%m%d_%H%M%S')}"
    )
    stock_name = "台積電" if symbol == "2330" else symbol
    structured_card_by_symbol: dict[str, dict[str, Any]] = {}
    report = "台積電(2330)\n策略：中性觀察\n此為 AI-DEV-250 隔離 post-report diagnostic fixture。"
    indicator_result = {"close": 100, "date": "2026-09-18", "summary": "中性觀察"}
    adr_result = {"status": "neutral", "market_summary": "ADR 中性"}
    news_bundle = {
        "analysis": "具備新聞證據但無正式批次副作用",
        "items": [{
            "title": "台積電營運展望新聞 fixture",
            "published_at": "2026-09-18T09:00:00+08:00",
            "source": "fixture",
            "url": "https://example.invalid/news/2330",
            "content_status": "FULL_CONTENT",
        }],
    }
    chip_result = {"summary": "籌碼中性"}
    total_score_result = {"total_score": 50, "rating": "neutral", "action": "等待確認"}
    ai_analysis = {"entry_condition": "等待確認", "gap_risk": "low", "event_risk": "low"}

    _emit_post_report_progress(stage_timing, symbol, "REPORT_GENERATED", status="completed", report_chars=len(report))
    _emit_post_report_progress(stage_timing, symbol, "SQLITE_WRITE_DONE", status="completed", dry_run=True)
    _emit_post_report_progress(stage_timing, symbol, "STRUCTURED_CARD_START")

    def _card_progress(substage: str, status: str = "started", **metadata: Any) -> None:
        _emit_post_report_progress(stage_timing, symbol, substage, status=status, **metadata)

    with _bounded_post_report_operation(
        stage_timing=stage_timing,
        symbol=symbol,
        substage="STRUCTURED_CARD_BUILD",
        timeout_seconds=timeout_seconds,
    ):
        structured_card = build_pre_open_card(
            symbol=symbol,
            name=stock_name,
            trading_date="2026-09-21",
            indicator=indicator_result,
            adr=adr_result,
            news=news_bundle,
            chip=chip_result,
            score=total_score_result,
            analysis=ai_analysis,
            progress_hook=_card_progress,
        )
    _emit_post_report_progress(stage_timing, symbol, "STRUCTURED_CARD_DONE", status="completed")
    _emit_post_report_progress(stage_timing, symbol, "ARTIFACT_WRITE_START")
    with _bounded_post_report_operation(
        stage_timing=stage_timing,
        symbol=symbol,
        substage="ARTIFACT_WRITE",
        timeout_seconds=timeout_seconds,
    ):
        _store_structured_pre_open_card(structured_card_by_symbol, structured_card)
    _emit_post_report_progress(stage_timing, symbol, "ARTIFACT_WRITE_DONE", status="completed")
    _emit_post_report_progress(stage_timing, symbol, "STOCK_ANALYSIS_DONE", status="completed")

    elapsed = round(monotonic() - started, 3)
    return {
        "schema_version": "ai_dev_250_post_report_diagnostic_v1",
        "symbol": symbol,
        "stock_analysis_done": True,
        "structured_result_produced": bool(structured_card_by_symbol.get(symbol)),
        "elapsed_seconds": elapsed,
        "event_count": len(stage_timing.events),
        "events": stage_timing.events,
        "production_delivery_invoked": False,
        "line_email_sent": False,
        "dashboard_published": False,
        "db_sheet_mutation": False,
        "trading_or_order": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="2330")
    parser.add_argument("--timeout-seconds", type=int, default=5)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = _run(str(args.symbol).zfill(4), args.timeout_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["stock_analysis_done"] and result["structured_result_produced"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
