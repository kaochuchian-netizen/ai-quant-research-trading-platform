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
    ui_window_id: str | None = None
    def to_dict(self) -> dict[str, Any]: return asdict(self)
CONTEXTS: dict[str, ReportWindowContext] = {
    "pre_open_0700": ReportWindowContext(SCHEMA_VERSION, "pre_open_0700", "pre_open", "Stock AI 盤前預測", "盤前預測", "pre_open", "台股盤前預測、今日/隔日高低價、1M/3M trend、夜盤與美股盤後摘要狀態", ["taiwan_pre_open_forecast", "same_day_high_low", "next_day_high_low", "one_month_trend", "three_month_trend", "confidence", "rationale", "risk_notes", "night_futures_watch", "us_post_market_status"], ["prediction_review_final", "raw_diagnostics"], "short summary, prediction field status, major risks, dashboard URL", "full pre-open forecast report with all prediction fields", "full state, freshness, missing prediction reasons", "diagnostics separated from user-facing report", ui_window_id="pre_open_0700"),
    "intraday_1305": ReportWindowContext(SCHEMA_VERSION, "intraday_1305", "intraday", "Stock AI 盤中分析", "盤中追蹤", "intraday", "盤中價格、量能、籌碼、ADR/外部市場、盤前假設有效性與風險提醒", ["intraday_analysis", "current_price_state", "price_vs_forecast_range", "volume_state", "chip_adr_external_proxy", "pre_open_assumption_validity", "risk_notes"], ["full_prediction_review", "raw_diagnostics"], "intraday key reminder and dashboard URL", "full intraday analysis", "intraday state plus freshness", "diagnostics separated from user-facing report", ui_window_id="intraday_1305"),
    "pre_close_1335": ReportWindowContext(SCHEMA_VERSION, "pre_close_1335", "pre_close", "Stock AI 收盤快照", "收盤快照", "close_snapshot", "收盤快照；今日高低收狀態、與盤前預測初步比對，完整檢討待 15:00", ["close_snapshot", "actual_high_low_close", "initial_forecast_comparison", "direction_initial_status", "items_for_1500_review", "same_day_summary"], ["pre_close_primary_label", "full_prediction_review", "raw_diagnostics"], "close snapshot summary and dashboard URL", "same-day close snapshot and initial summary", "Close Snapshot state; full review deferred to 15:00", "runtime key pre_close_1335 allowed only in diagnostics", ui_window_id="close_snapshot_1335"),
    "post_close_1500": ReportWindowContext(SCHEMA_VERSION, "post_close_1500", "post_close", "Stock AI 盤後檢討", "盤後檢討", "post_close", "完整盤後檢討、forecast vs actual、7 日滾動預測品質與改善建議", ["prediction_review", "seven_day_rolling_review", "forecast_vs_actual", "high_low_error", "direction_hit", "confidence_calibration", "factor_effectiveness", "error_reason", "next_day_improvement"], ["opening_call_to_action", "raw_diagnostics"], "review highlights and dashboard URL", "full 7-day rolling prediction review", "complete prediction review state", "raw pipeline logs only in diagnostics", ui_window_id="prediction_review_1500"),
    "prediction_review_1500": ReportWindowContext(SCHEMA_VERSION, "prediction_review_1500", "prediction_review", "Stock AI 預測檢討", "預測檢討", "post_close", "預測命中、pending outcome、insufficient data、evaluation summary", ["review_cards", "evaluation_summary", "pending_outcomes", "insufficient_data"], ["pre_open_watchlist", "raw_diagnostics"], "concise review state and dashboard URL", "full prediction review report", "clean review plus diagnostics", "raw pipeline logs only in diagnostics", ui_window_id="prediction_review_1500"),
}
PIPELINE_TO_WINDOW = {"pre_open": "pre_open_0700", "intraday": "intraday_1305", "pre_close": "pre_close_1335", "post_close": "post_close_1500", "prediction_review": "prediction_review_1500"}
def get_window_context(scheduler_window: str | None = None, pipeline_type: str | None = None) -> ReportWindowContext:
    key = scheduler_window or PIPELINE_TO_WINDOW.get(str(pipeline_type or ""), "pre_open_0700")
    if key not in CONTEXTS:
        raise ValueError(f"unsupported scheduler_window: {key}")
    return CONTEXTS[key]
def all_window_contexts() -> list[ReportWindowContext]: return list(CONTEXTS.values())
