"""Constants for the US dedicated batch foundation.

This module is metadata-only: it does not call market data APIs,
production pipelines, schedulers, notification services, or trading systems.
"""
from __future__ import annotations

US_SOURCE_SHEET = "工作表2"
TW_SOURCE_SHEET = "工作表1"
DEFAULT_MARKET = "US"
DEFAULT_CURRENCY = "USD"
TIMEZONE = "Asia/Taipei"

US_BATCH_WINDOWS = {
    "us_pre_market_2000": {
        "scheduled_time_tw": "20:00",
        "purpose": "US pre-market report",
        "prediction_window": "upcoming_us_regular_session",
    },
    "us_intraday_2300": {
        "scheduled_time_tw": "23:00",
        "purpose": "US intraday report",
        "prediction_window": "same_session_intraday_adjusted",
    },
    "us_post_close_review_0630": {
        "scheduled_time_tw": "06:30",
        "purpose": "US post-close prediction review and next-day observation",
        "prediction_window": "post_close_review",
    },
}

US_SCORING_WEIGHTS = {
    "technical": 0.40,
    "news_company_event": 0.25,
    "market_environment": 0.20,
    "volatility_risk": 0.15,
}

DELIVERY_POLICY = {
    "email_delivery_allowed": False,
    "line_delivery_allowed": False,
    "dashboard_delivery_allowed": True,
    "notification_policy": "controlled_pending_pm_activation",
    "line_summary_only": True,
    "email_full_report_candidate": True,
    "delivery_executed": False,
    "line_sent": False,
    "email_sent": False,
}

SCHEDULER_POLICY = {
    "scheduler_runtime_activation": False,
    "cron_modified": False,
    "systemd_timer_modified": False,
    "timezone": TIMEZONE,
    "activation_requires_pm_review": True,
}

SAFETY_POLICY = {
    "external_api_called": False,
    "production_pipeline_executed": False,
    "python3_main_executed": False,
    "line_email_notification_sent": False,
    "scheduler_runtime_activation": False,
    "db_write": False,
    "trading_or_order_executed": False,
    "secrets_read": False,
    "valid_manual_rerun_triggered": False,
    "tw_rating_action_confidence_weight_modified": False,
}
