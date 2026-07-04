"""Schemas and constants for TWSE/yfinance formal report integration V1."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

SCHEMA_VERSION = "twse_yfinance_report_integration_v1"
SOURCE_IDS = ["twse_openapi", "yfinance_yahoo"]
REPORT_SECTION_IDS = [
    "twse_chip_institutional_summary",
    "twse_margin_trading_summary",
    "twse_official_market_attribution",
    "yfinance_adr_reference",
    "yfinance_us_index_etf_sector_proxy",
    "yfinance_external_market_sentiment_proxy",
    "freshness_and_failure_modes",
    "safety_and_governance",
]

@dataclass(frozen=True)
class ReportSourcePolicy:
    source_id: str
    provider: str
    source_role: str
    report_use: List[str]
    freshness_policy: str
    failure_mode: str
    official_source_replacement_allowed: bool
    direct_rating_action_confidence_impact: bool
    explainability_note: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def safety_summary() -> Dict[str, Any]:
    return {
        "read_only": True,
        "offline_sample_only": True,
        "external_api_called": False,
        "secrets_read": False,
        "production_db_write": False,
        "scheduler_modified": False,
        "line_email_sent": False,
        "dashboard_published": False,
        "broker_or_order_execution": False,
        "production_rating_action_confidence_weight_mutation": False,
    }
