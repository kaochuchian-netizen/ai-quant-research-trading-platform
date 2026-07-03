#!/usr/bin/env python3
"""Build deterministic multi-window report content artifact."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from app.reports.report_content_contract import build_report_content_artifact
from app.reports.window_context import get_window_context
RAW_SAMPLE = """Response Code: 200
Event: Session up
APISUB/market data host '210.59.255.161'
開始分析股票 2330
SQLite 已寫入 data/stock_analysis.db
post_close selected stock ids: ['2330']
pipeline_report_summary:
{"pipeline_type":"post_close","raw":true}
收盤後重點：台股今日量縮整理，風險維持中性。
【2330 台積電】盤前 🟡
樣本分析：基本面穩定，等待 actual outcome 完成。
"""
def sample_payload(window: str) -> dict:
    content_state = {
        "pre_open_0700": "stock_analysis_reports_available",
        "intraday_1305": "partial",
        "pre_close_1335": "partial",
        "post_close_1500": "prediction_review_pending",
        "prediction_review_1500": "prediction_review_insufficient_data",
    }.get(window, "partial")
    return {"scheduler_window": window, "content_state": content_state, "raw_text": RAW_SAMPLE, "run_id": f"offline-{window}", "dashboard_url": "http://example.invalid/dashboard", "stock_cards": [{"stock_id":"2330", "stock_name":"台積電", "signal":"中性", "summary":"依目前樣本資料維持觀察；此為乾淨 user-facing 內容。", "advisory_only": True}], "source_warnings": ["offline sample includes intentionally suppressed raw logs"]}
def build_artifact(payload: dict) -> dict:
    window = payload.get("scheduler_window", "post_close_1500")
    contract = build_report_content_artifact(window, payload.get("raw_text", ""), payload.get("content_state", "partial"), payload.get("run_id", "offline-sample"), payload.get("dashboard_url"), payload.get("stock_cards"), payload.get("source_warnings"))
    ctx = get_window_context(window)
    return {"schema_version": "multi_window_report_artifact_v1", "generated_at": contract.generated_at, "input_summary": {"offline_sample": True, "raw_text_chars": len(payload.get("raw_text", ""))}, "window_context": ctx.to_dict(), "content_state": contract.content_state, "user_facing_report": contract.user_facing_report, "diagnostics": contract.diagnostics, "sanitization_summary": contract.raw_log_summary, "delivery_policy": contract.delivery_policy, "safety_summary": contract.safety_summary, "future_integration": {"real_historical_artifact_ingestion": "AI-DEV-129", "rolling_evaluation": "future", "production_dashboard_publish_candidate": "future approval required", "source_connector_timeout_hardening": "future"}}
def main() -> int:
    parser = argparse.ArgumentParser(description="Build multi-window report artifact.")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--window", default="post_close_1500", choices=["pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500", "prediction_review_1500"])
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--offline-sample", action="store_true")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else sample_payload(args.window)
    artifact = build_artifact(payload)
    text = json.dumps(artifact, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    if args.output: Path(args.output).write_text(text + "\n", encoding="utf-8")
    else: sys.stdout.write(text + "\n")
    return 0
if __name__ == "__main__": raise SystemExit(main())
