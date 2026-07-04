from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "external_source_coverage_audit_v1"
STATUSES = {
    "production_used",
    "connector_exists_not_in_formal_report",
    "inventory_only_not_connectorized",
    "needs_connector",
    "low_priority_metadata_only",
}
READINESS = {"production_ready", "shadow_ready", "research_only", "not_ready", "not_recommended_primary"}
GAP_CLASSES = {"none", "report_integration_gap", "dashboard_integration_gap", "prediction_context_gap", "evaluation_gap", "connector_gap", "quality_priority_gap", "credential_policy_gap"}
SOURCE_PRIORITIES = {"A_primary", "B_official_or_company_linked", "C_market_or_industry", "D_low_priority_metadata_noise"}

@dataclass(frozen=True)
class ExternalSourceAuditRecord:
    source_id: str
    source_name: str
    source_type: str
    provider: str
    current_status: str
    connector_exists: bool
    runtime_used: bool
    artifact_used: bool
    report_used: bool
    dashboard_used: bool
    prediction_used: bool
    evaluation_used: bool
    credential_required: bool
    freshness_policy: str
    failure_mode: str
    source_priority: str
    explainability_support: str
    production_readiness: str
    gaps: list[str] = field(default_factory=list)
    recommended_next_action: str = ""
    evidence_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class ExternalSourceCoverageAuditArtifact:
    schema_version: str
    generated_at: str
    audit_mode: str
    repo_scan_summary: dict[str, Any]
    source_records: list[dict[str, Any]]
    coverage_summary: dict[str, Any]
    gap_summary: dict[str, Any]
    roadmap_recommendations: list[dict[str, Any]]
    safety_summary: dict[str, Any]
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
