"""Source connector and evidence schemas for AI-DEV-123."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

SOURCE_EVIDENCE_SCHEMA_VERSION = "source_evidence_v1"
FETCH_RESULT_SCHEMA_VERSION = "source_fetch_result_v1"
CONNECTOR_HEALTH_SCHEMA_VERSION = "source_connector_health_v1"
ENDPOINT_SCHEMA_VERSION = "source_endpoint_v1"
EVIDENCE_TYPES = {"monthly_revenue", "material_information", "financial_statement", "investor_conference", "market_context", "chip_structure", "etf_reference", "news_event", "missing_source_notice", "institutional_flow", "margin_short", "market_price"}
SOURCE_PRIORITIES = {"A_primary", "B_official_or_company_linked", "C_market_or_industry", "C_market_or_aggregated_data", "D_sentiment_or_noise"}
NOISE_RISKS = {"low", "medium", "high"}
CONNECTOR_STATUSES = {"available", "unavailable", "skipped", "error"}

@dataclass(frozen=True)
class SourceEndpoint:
    source_id: str; provider: str; endpoint_name: str; category: str; priority: str; credential_required: bool | str; url: str | None; evidence_type: str; read_only: bool; usage_policy: list[str] = field(default_factory=list); notes: str = ""
    schema_version: str = ENDPOINT_SCHEMA_VERSION
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class SourceFetchRequest:
    source_id: str; stock_id: str; stock_name: str = ""; offline_sample: bool = True; allow_network: bool = False; token: str | None = None
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class SourceEvidence:
    schema_version: str; evidence_id: str; source_id: str; provider: str; category: str; priority: str; stock_id: str; stock_name: str; event_date: str; retrieved_at: str; title: str; summary: str; raw_fields: dict[str, Any]; normalized_fields: dict[str, Any]; source_url: str | None; evidence_type: str; quality_score: float; noise_risk: str; lineage: dict[str, Any]; usage_policy: list[str]
    def to_dict(self) -> dict[str, Any]: return asdict(self)
    def validate(self) -> list[str]:
        reasons: list[str] = []
        if self.schema_version != SOURCE_EVIDENCE_SCHEMA_VERSION: reasons.append("invalid source evidence schema_version")
        if self.evidence_type not in EVIDENCE_TYPES: reasons.append(f"invalid evidence_type: {self.evidence_type}")
        if self.priority not in SOURCE_PRIORITIES: reasons.append(f"invalid priority: {self.priority}")
        if self.noise_risk not in NOISE_RISKS: reasons.append(f"invalid noise_risk: {self.noise_risk}")
        if not 0 <= float(self.quality_score) <= 1: reasons.append("quality_score must be 0..1")
        if not self.source_id or not self.evidence_id: reasons.append("source_id and evidence_id are required")
        return reasons

@dataclass(frozen=True)
class SourceEvidenceBatch:
    schema_version: str; source_id: str; evidence: list[dict[str, Any]]; missing_reasons: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class SourceConnectorHealth:
    schema_version: str; source_id: str; provider: str; status: str; read_only: bool; checked_at: str; missing_reason: str | None; error_message: str | None; evidence_count: int; usage_policy: list[str]
    def to_dict(self) -> dict[str, Any]: return asdict(self)
    def validate(self) -> list[str]:
        reasons: list[str] = []
        if self.schema_version != CONNECTOR_HEALTH_SCHEMA_VERSION: reasons.append("invalid connector health schema_version")
        if self.status not in CONNECTOR_STATUSES: reasons.append(f"invalid connector status: {self.status}")
        if not self.read_only: reasons.append("connector health must be read_only")
        return reasons

@dataclass(frozen=True)
class SourceFetchResult:
    schema_version: str; request: dict[str, Any]; health: dict[str, Any]; evidence_batch: dict[str, Any]
    def to_dict(self) -> dict[str, Any]: return asdict(self)
