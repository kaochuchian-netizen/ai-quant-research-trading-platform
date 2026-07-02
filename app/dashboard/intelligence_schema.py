"""Schema constants and safety defaults for Dashboard Intelligence V1."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

REQUIRED_SECTION_IDS = [
    "today_overview",
    "prediction_performance",
    "stock_intelligence_cards",
    "source_coverage_data_quality",
    "explainability",
    "confidence_calibration",
    "factor_recommendation",
    "diagnostics",
    "safety_governance",
]
DASHBOARD_PRIORITIES = ["high", "medium", "low", "watch", "not_available"]

@dataclass(frozen=True)
class DashboardCard:
    card_id: str
    card_type: str
    title: str
    summary: str
    status: str
    advisory_only: bool = True

@dataclass(frozen=True)
class DashboardSection:
    section_id: str
    title: str
    summary: str
    status: str
    cards: List[Dict[str, Any]]
    last_updated: str
    advisory_only: bool = True

def card_to_dict(card: DashboardCard) -> Dict[str, Any]:
    return asdict(card)

def section_to_dict(section: DashboardSection) -> Dict[str, Any]:
    return asdict(section)

def safety_summary() -> Dict[str, Any]:
    return {
        "advisory_only": True,
        "production_publish_allowed": False,
        "production_mutation_allowed": False,
        "trading_disabled": True,
        "scheduler_mutation_allowed": False,
        "delivery_mutation_allowed": False,
        "human_review_required": True,
        "no_broker_login": True,
        "no_simulation_order": True,
        "no_production_order": True,
        "no_line_email_delivery": True,
        "no_production_db_write": True,
        "no_secrets_read": True,
        "no_forecast_weight_change": True,
        "no_confidence_mutation": True,
        "no_rating_action_mutation": True,
        "no_production_dashboard_publish": True,
        "no_var_www_write": True,
        "no_nginx_systemd_cron_change": True,
        "safety_notes": [
            "Repo-side dashboard intelligence artifact and preview only.",
            "All recommendations are advisory-only and require human review.",
            "Preview output is not published to the production dashboard directory.",
        ],
    }
