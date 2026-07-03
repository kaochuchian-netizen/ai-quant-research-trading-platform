"""Clean report artifact contract for scheduled delivery windows."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from .diagnostics_separator import build_diagnostics, raw_log_summary
from .multi_window_formatter import build_user_facing_report
from .report_sanitizer import sanitize_report_text
from .window_context import get_window_context
SCHEMA_VERSION = "multi_window_report_content_v1"
CONTENT_STATES = {"stock_analysis_reports_available", "prediction_review_available", "prediction_review_pending", "prediction_review_insufficient_data", "no_fresh_artifact", "pipeline_timed_out", "failed", "partial"}
@dataclass(frozen=True)
class ReportContentArtifact:
    schema_version: str
    generated_at: str
    run_id: str
    scheduler_window: str
    pipeline_type: str
    content_state: str
    user_facing_report: dict[str, Any]
    diagnostics: dict[str, Any]
    raw_log_summary: dict[str, Any]
    delivery_policy: dict[str, Any]
    safety_summary: dict[str, Any]
    def to_dict(self) -> dict[str, Any]: return asdict(self)
def safety_summary() -> dict[str, bool]:
    return {"advisory_only": True, "broker_login": False, "simulation_order": False, "production_order": False, "line_send": False, "email_send": False, "dashboard_production_publish": False, "var_www_dashboard_write": False, "scheduler_time_change": False, "cron_systemd_timer_mutation": False, "production_db_write": False, "secrets_read": False, "production_pipeline_run": False, "python3_main_py": False, "trading_order_portfolio_action": False, "production_confidence_mutation": False, "production_forecast_weight_change": False, "rating_action_rule_mutation": False}
def build_report_content_artifact(scheduler_window: str, raw_text: str, content_state: str, run_id: str = "offline-sample", dashboard_url: str | None = None, stock_cards: list[dict[str, Any]] | None = None, source_warnings: list[str] | None = None) -> ReportContentArtifact:
    if content_state not in CONTENT_STATES: content_state = "partial"
    context = get_window_context(scheduler_window)
    sanitized = sanitize_report_text(raw_text)
    user_report = build_user_facing_report(context, content_state, sanitized.sanitized_text, stock_cards, dashboard_url)
    diagnostics = build_diagnostics("completed" if content_state not in {"failed", "pipeline_timed_out"} else content_state, sanitized, source_warnings, content_state)
    return ReportContentArtifact(SCHEMA_VERSION, datetime.now(timezone.utc).replace(microsecond=0).isoformat(), run_id, context.scheduler_window, context.pipeline_type, content_state, user_report, diagnostics, raw_log_summary(raw_text, sanitized), {"line": context.line_policy, "email": context.email_policy, "dashboard": context.dashboard_policy, "diagnostics": context.diagnostics_policy}, safety_summary())
