from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "finmind_report_integration_artifact_v1"
INPUT_SCHEMA_VERSION = "finmind_report_integration_input_v1"
SUPPORTED_SECTION_TYPES = {
    "monthly_revenue",
    "financial_statement_summary",
    "eps",
    "roe",
    "margin",
    "institutional_trading",
    "dividend",
    "share_capital",
    "market_cap",
}

@dataclass(frozen=True)
class FinMindReportSection:
    section_id: str
    section_type: str
    title: str
    summary: str
    metrics: dict[str, Any]
    source_ids: list[str]
    freshness_policy: str
    explainability_notes: list[str]
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class FinMindReportIntegrationArtifact:
    schema_version: str
    generated_at: str
    input_summary: dict[str, Any]
    source_attribution: dict[str, Any]
    freshness_policy: dict[str, Any]
    report_sections: list[dict[str, Any]]
    explainability_notes: list[str]
    integration_policy: dict[str, Any]
    safety_summary: dict[str, bool]
    advisory_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def safety_summary() -> dict[str, bool]:
    return {
        "advisory_only": True,
        "external_api_called": False,
        "finmind_api_token_required": False,
        "secrets_read": False,
        "production_scheduler_modified": False,
        "line_sent": False,
        "email_sent": False,
        "dashboard_published": False,
        "production_db_write": False,
        "broker_login": False,
        "simulation_order": False,
        "production_order": False,
        "trading_execution": False,
        "production_rating_action_confidence_weight_changed": False,
    }
