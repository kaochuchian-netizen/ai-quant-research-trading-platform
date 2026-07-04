from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "external_source_connector_roadmap_v1"
SOURCE_PRIORITIES = {"A_primary", "B_official_or_company_linked", "C_market_or_industry", "D_low_priority_metadata_noise"}
DECISION_VALUES = {"high", "medium", "low"}
RISK_LEVELS = {"low", "medium", "high"}
COMPLEXITY_LEVELS = {"low", "medium", "high"}
PHASES = {"phase_0_maintain", "phase_1_prediction_context", "phase_2_formal_report", "phase_3_connector_build", "phase_4_defer_metadata_only", "manual_review_required"}
STATUSES = {"production_used", "connector_exists_not_in_formal_report", "inventory_only_not_connectorized", "needs_connector", "low_priority_metadata_only"}

@dataclass(frozen=True)
class SourceConnectorPriorityPolicy:
    source_id: str
    source_name: str
    source_type: str
    provider: str
    current_status: str
    source_priority: str
    decision_value: str
    freshness_requirement: str
    reliability_risk: str
    explainability_value: str
    credential_requirement: str
    implementation_complexity: str
    production_risk: str
    recommended_phase: str
    prediction_context_candidate: bool
    formal_report_candidate: bool
    low_priority_metadata_only: bool
    rating_action_confidence_allowed: bool
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class ExternalSourceConnectorRoadmapArtifact:
    schema_version: str
    generated_at: str
    input_summary: dict[str, Any]
    priority_policy: list[dict[str, Any]]
    roadmap: dict[str, list[str]]
    phase_summary: dict[str, Any]
    safety_summary: dict[str, bool]
    future_integration: dict[str, str]
    advisory_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def safety_summary() -> dict[str, bool]:
    return {
        "advisory_only": True,
        "external_api_called": False,
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
