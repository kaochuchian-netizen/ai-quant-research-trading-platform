"""Explainability schemas for deterministic source-linked explanations."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any
FEATURE_ATTRIBUTION_SCHEMA_VERSION = "feature_attribution_v1"
STOCK_EXPLANATION_SCHEMA_VERSION = "stock_explanation_v1"
EXPLANATION_ARTIFACT_SCHEMA_VERSION = "source_explainability_artifact_v1"
FEATURE_GROUPS = {"technical", "news", "adr", "chip", "fundamental", "disclosure", "industry", "macro", "etf", "source_coverage", "missing_data", "market_price"}
DIRECTIONS = {"positive", "negative", "neutral", "not_available"}
STATUSES = {"complete", "partial", "limited_by_missing_primary_sources"}
@dataclass(frozen=True)
class FeatureContribution:
    feature_id: str; feature_name: str; feature_group: str; direction: str; magnitude: float; score_impact: float; confidence_impact: float; source_ids: list[str]; evidence_ids: list[str]; explanation_text: str; risk_note: str | None = None
    def to_dict(self) -> dict[str, Any]: return asdict(self)
    def validate(self) -> list[str]:
        reasons: list[str] = []
        if self.feature_group not in FEATURE_GROUPS: reasons.append(f"invalid feature_group: {self.feature_group}")
        if self.direction not in DIRECTIONS: reasons.append(f"invalid direction: {self.direction}")
        if not 0 <= float(self.magnitude) <= 1: reasons.append("magnitude must be 0..1")
        return reasons
@dataclass(frozen=True)
class FeatureAttribution:
    schema_version: str; run_id: str; stock_id: str; stock_name: str; contributions: list[dict[str, Any]]; policy_notes: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]: return asdict(self)
@dataclass(frozen=True)
class StockExplanation:
    schema_version: str; run_id: str; stock_id: str; stock_name: str; rating: str; score: float; action: str; prediction_targets: list[str]; top_positive_factors: list[dict[str, Any]]; top_negative_factors: list[dict[str, Any]]; neutral_factors: list[dict[str, Any]]; missing_data_factors: list[dict[str, Any]]; source_coverage_summary: dict[str, Any]; confidence_cap_reason: str | None; explainability_status: str; advisory_only: bool
    def to_dict(self) -> dict[str, Any]: return asdict(self)
@dataclass(frozen=True)
class ExplanationArtifact:
    schema_version: str; generated_at: str; source_connector_health: list[dict[str, Any]]; source_evidence: list[dict[str, Any]]; feature_attributions: list[dict[str, Any]]; stock_explanations: list[dict[str, Any]]; source_coverage_summary: dict[str, Any]; missing_data_summary: dict[str, Any]; safety_summary: dict[str, bool]; future_integration: dict[str, Any]
    def to_dict(self) -> dict[str, Any]: return asdict(self)
