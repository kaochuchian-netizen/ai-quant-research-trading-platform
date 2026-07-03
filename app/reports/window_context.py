"""Window-specific report context for scheduled delivery content."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any
SCHEMA_VERSION = "report_window_context_v1"
@dataclass(frozen=True)
class ReportWindowContext:
    schema_version: str
    scheduler_window: str
    pipeline_type: str
    display_title: str
    display_label: str
    market_phase: str
    primary_purpose: str
    allowed_sections: list[str]
    disallowed_sections: list[str]
    line_policy: str
    email_policy: str
    dashboard_policy: str
    diagnostics_policy: str
    advisory_only: bool = True
    def to_dict(self) -> dict[str, Any]: return asdict(self)
CONTEXTS: dict[str, ReportWindowContext] = {
    "pre_open_0700": ReportWindowContext(SCHEMA_VERSION, "pre_open_0700", "pre_open", "Stock AI 盤前報告", "盤前", "pre_open", "開盤前重點、風險、個股分析、今日觀察", ["market_overview", "stock_cards", "risk_notes", "today_watchlist"], ["prediction_review_final", "raw_diagnostics"], "full report handled by production pre_open pipeline", "full scheduled report", "clean report plus diagnostics", "diagnostics separated from user-facing report"),
    "intraday_1305": ReportWindowContext(SCHEMA_VERSION, "intraday_1305", "intraday", "Stock AI 盤中報告", "盤中", "intraday", "盤中狀態、異常、風險提醒", ["market_status", "anomaly_notes", "risk_notes", "concise_summary"], ["pre_open_watchlist", "raw_diagnostics"], "concise summary and dashboard URL", "full intraday report", "clean report plus diagnostics", "diagnostics separated from user-facing report"),
    "pre_close_1335": ReportWindowContext(SCHEMA_VERSION, "pre_close_1335", "pre_close", "Stock AI 收盤前報告", "收盤前", "pre_close", "收盤前觀察、風險、是否需要人工 review", ["market_status", "risk_notes", "manual_review_items", "stock_cards"], ["pre_open_watchlist", "raw_diagnostics"], "concise risk reminder", "full pre-close report", "clean report plus diagnostics", "diagnostics separated from user-facing report"),
    "post_close_1500": ReportWindowContext(SCHEMA_VERSION, "post_close_1500", "post_close", "Stock AI 盤後報告", "盤後", "post_close", "收盤後摘要、當日結果、prediction review 狀態", ["close_summary", "prediction_review_state", "stock_cards", "review_cards"], ["pre_open_watchlist", "raw_diagnostics", "opening_call_to_action"], "concise post-close summary and dashboard URL", "full post-close / prediction review report", "clean report plus diagnostics", "raw pipeline logs only in diagnostics"),
    "prediction_review_1500": ReportWindowContext(SCHEMA_VERSION, "prediction_review_1500", "prediction_review", "Stock AI 預測檢討", "預測檢討", "post_close", "預測命中、pending outcome、insufficient data、evaluation summary", ["review_cards", "evaluation_summary", "pending_outcomes", "insufficient_data"], ["pre_open_watchlist", "raw_diagnostics", "opening_call_to_action"], "concise review state and dashboard URL", "full prediction review report", "clean review plus diagnostics", "raw pipeline logs only in diagnostics"),
}
PIPELINE_TO_WINDOW = {"pre_open": "pre_open_0700", "intraday": "intraday_1305", "pre_close": "pre_close_1335", "post_close": "post_close_1500", "prediction_review": "prediction_review_1500"}
def get_window_context(scheduler_window: str | None = None, pipeline_type: str | None = None) -> ReportWindowContext:
    key = scheduler_window or PIPELINE_TO_WINDOW.get(str(pipeline_type or ""), "pre_open_0700")
    if key not in CONTEXTS:
        raise ValueError(f"unsupported scheduler_window: {key}")
    return CONTEXTS[key]
def all_window_contexts() -> list[ReportWindowContext]: return list(CONTEXTS.values())
