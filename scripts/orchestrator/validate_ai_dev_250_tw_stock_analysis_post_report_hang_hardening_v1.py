#!/usr/bin/env python3
"""Validate AI-DEV-250 TW stock-analysis post-report hang hardening."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.reports.tw_pre_open_structured import build_card  # noqa: E402


def _run() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    pipeline_path = ROOT / "app/pipelines/pre_open_pipeline.py"
    structured_path = ROOT / "app/reports/tw_pre_open_structured.py"
    diagnostic_path = ROOT / "scripts/orchestrator/diagnose_ai_dev_250_post_report_2330_v1.py"
    pipeline = pipeline_path.read_text(encoding="utf-8")
    structured = structured_path.read_text(encoding="utf-8")
    diagnostic = diagnostic_path.read_text(encoding="utf-8")

    required_substages = [
        "REPORT_GENERATED",
        "SQLITE_WRITE_DONE",
        "STRUCTURED_CARD_START",
        "STRUCTURED_CARD_DONE",
        "NEWS_EVIDENCE_START",
        "NEWS_EVIDENCE_DONE",
        "ARTIFACT_WRITE_START",
        "ARTIFACT_WRITE_DONE",
        "STOCK_ANALYSIS_DONE",
    ]
    checks["post_report_substage_observability"] = all(token in pipeline + structured for token in required_substages)
    checks["structured_progress_schema"] = (
        "tw_stock_analysis_post_report_progress_v1" in pipeline
        and "file=sys.stderr" in pipeline
        and "stage_timing._write(event_name)" in pipeline
    )
    checks["stdout_contract_preserved"] = "print(report, flush=True)" in pipeline and "file=sys.stderr" in pipeline
    checks["bounded_post_report_operation"] = (
        "POST_REPORT_SUBSTAGE_TIMEOUT_SECONDS" in pipeline
        and "PostReportSubstageTimeout" in pipeline
        and "signal.setitimer(signal.ITIMER_REAL" in pipeline
    )
    checks["structured_card_timeout_boundary"] = (
        'substage="STRUCTURED_CARD_BUILD"' in pipeline
        and "with _bounded_post_report_operation" in pipeline
        and "build_pre_open_card(" in pipeline
    )
    checks["artifact_write_timeout_boundary"] = (
        'substage="ARTIFACT_WRITE"' in pipeline
        and "_store_structured_pre_open_card" in pipeline
    )
    checks["manual_progress_write_timeout_boundary"] = (
        'substage="MANUAL_PROGRESS_WRITE"' in pipeline
        and 'report_manual_rerun_stage("prediction_projection", "completed"' in pipeline
    )
    checks["news_evidence_progress_hook"] = (
        "progress_hook" in structured
        and "NEWS_EVIDENCE_START" in structured
        and "NEWS_EVIDENCE_DONE" in structured
        and "news_contract(news" in structured
    )
    checks["stock_stage_terminal_on_success"] = (
        "STOCK_ANALYSIS_DONE" in pipeline
        and "stage_timing.finish(stage_name, report_ready=True)" in pipeline
    )
    checks["stock_stage_terminal_on_failure"] = 'stage_timing.finish(stage_name, status="failed", reason=reason)' in pipeline
    checks["one_symbol_cannot_silently_consume_wrapper_timeout"] = (
        "PostReportSubstageTimeout" in pipeline
        and "reason=exc.__class__.__name__" in pipeline
        and 'status="failed"' in pipeline
    )
    checks["production_delivery_not_invoked_by_hardening"] = (
        "send_line" not in pipeline
        and "send_email" not in pipeline
        and "publish_dashboard" not in pipeline
    )
    checks["controlled_2330_diagnostic_isolated"] = (
        "ai_dev_250_post_report_diagnostic_v1" in diagnostic
        and "production_delivery_invoked" in diagnostic
        and "line_email_sent" in diagnostic
        and "dashboard_published" in diagnostic
        and "db_sheet_mutation" in diagnostic
        and "trading_or_order" in diagnostic
    )

    progress_events: list[tuple[str, str]] = []

    def _hook(substage: str, status: str = "started", **_metadata: Any) -> None:
        progress_events.append((substage, status))

    card = build_card(
        symbol="2330",
        name="台積電",
        trading_date="2026-09-21",
        indicator={"close": 100, "date": "2026-09-18", "summary": "中性"},
        adr={"status": "neutral"},
        news={"analysis": "news evidence", "items": []},
        chip={"summary": "中性"},
        score={"total_score": 50, "rating": "neutral", "action": "等待確認"},
        analysis={"entry_condition": "等待", "gap_risk": "low", "event_risk": "low"},
        progress_hook=_hook,
    )
    checks["structured_card_success"] = bool(card["symbol"] == "2330" and card.get("source_payload_hash"))
    checks["news_evidence_hook_runtime"] = ("NEWS_EVIDENCE_START", "started") in progress_events and ("NEWS_EVIDENCE_DONE", "completed") in progress_events

    details["required_substages"] = required_substages
    details["progress_events"] = progress_events
    details["checked_files"] = [
        str(pipeline_path.relative_to(ROOT)),
        str(structured_path.relative_to(ROOT)),
        str(diagnostic_path.relative_to(ROOT)),
    ]
    return {
        "ok": all(bool(value) for value in checks.values()),
        "passed_count": sum(1 for value in checks.values() if bool(value)),
        "total_count": len(checks),
        "checks": checks,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = _run()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
