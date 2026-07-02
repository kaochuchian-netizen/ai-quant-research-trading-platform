"""Schemas for advisory-only prediction snapshots."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "prediction_snapshot_v1"
PREDICTION_TARGETS = {"intraday_high_low", "next_day_high_low", "one_month_trend", "three_month_trend", "rating_action"}
MISSING_STATES = {"pending", "insufficient_data", "unavailable", "not_applicable"}
CONFIDENCE_STATUSES = {"ready", "capped", "downgraded", "insufficient_data"}
REVIEW_STATUSES = {"pending_review", "ready_for_evaluation", "pending_actual_outcome", "insufficient_data"}

def unavailable(reason: str = "unavailable") -> dict[str, str]:
    return {"status": reason if reason in MISSING_STATES else "unavailable"}

def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def normalize_confidence(value: Any) -> float | None:
    if not is_number(value):
        return None
    numeric = float(value)
    if numeric > 1:
        numeric /= 100
    return min(max(numeric, 0.0), 1.0)

@dataclass(frozen=True)
class PredictionSnapshot:
    schema_version: str
    run_id: str
    run_date: str
    run_time: str
    scheduler_window: str
    pipeline_type: str
    stock_id: str
    stock_name: str
    prediction_target: str
    predicted_high: float | dict[str, str] | None
    predicted_low: float | dict[str, str] | None
    predicted_trend: str | dict[str, str]
    confidence: float | dict[str, str] | None
    confidence_status: str
    rating: str | dict[str, str]
    score: float | dict[str, str] | None
    action: str | dict[str, str]
    advisory_only: bool
    source_ids: list[str]
    evidence_summary: list[str]
    data_coverage_score: float
    source_quality_summary: dict[str, Any]
    review_status: str
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    def validate(self, known_source_ids: set[str] | None = None) -> list[str]:
        reasons: list[str] = []
        if self.schema_version != SCHEMA_VERSION: reasons.append("invalid prediction snapshot schema_version")
        if self.prediction_target not in PREDICTION_TARGETS: reasons.append(f"invalid prediction_target: {self.prediction_target}")
        if not self.advisory_only: reasons.append("prediction snapshot must be advisory_only")
        if self.confidence_status not in CONFIDENCE_STATUSES: reasons.append(f"invalid confidence_status: {self.confidence_status}")
        if self.review_status not in REVIEW_STATUSES: reasons.append(f"invalid review_status: {self.review_status}")
        if not self.source_ids: reasons.append("source_ids must be non-empty")
        if known_source_ids is not None:
            for source_id in self.source_ids:
                if source_id not in known_source_ids: reasons.append(f"snapshot references unknown source_id: {source_id}")
        if not 0 <= float(self.data_coverage_score) <= 1: reasons.append("data_coverage_score must be between 0 and 1")
        if is_number(self.confidence) and not 0 <= float(self.confidence) <= 1: reasons.append("confidence must be between 0 and 1")
        for label, value in (("predicted_high", self.predicted_high), ("predicted_low", self.predicted_low)):
            if value is None: reasons.append(f"{label} must use an explicit missing-state object when unavailable")
            elif isinstance(value, dict) and value.get("status") not in MISSING_STATES: reasons.append(f"{label} has invalid missing status")
        return reasons

@dataclass(frozen=True)
class SourceQualitySummary:
    readiness: str
    confidence_cap: float
    missing_sources: list[str] = field(default_factory=list)
    primary_source_count: int = 0
    official_source_count: int = 0
    market_context_source_count: int = 0
    noisy_metadata_source_count: int = 0
    notes: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def prediction_snapshot_from_dict(payload: dict[str, Any]) -> PredictionSnapshot:
    return PredictionSnapshot(
        schema_version=str(payload.get("schema_version", "")), run_id=str(payload.get("run_id", "")), run_date=str(payload.get("run_date", "")), run_time=str(payload.get("run_time", "")), scheduler_window=str(payload.get("scheduler_window", "")), pipeline_type=str(payload.get("pipeline_type", "")), stock_id=str(payload.get("stock_id", "")), stock_name=str(payload.get("stock_name", "")), prediction_target=str(payload.get("prediction_target", "")), predicted_high=payload.get("predicted_high"), predicted_low=payload.get("predicted_low"), predicted_trend=payload.get("predicted_trend", unavailable()), confidence=payload.get("confidence"), confidence_status=str(payload.get("confidence_status", "")), rating=payload.get("rating", unavailable("not_applicable")), score=payload.get("score"), action=payload.get("action", unavailable("not_applicable")), advisory_only=bool(payload.get("advisory_only", False)), source_ids=[str(item) for item in payload.get("source_ids", [])], evidence_summary=[str(item) for item in payload.get("evidence_summary", [])], data_coverage_score=float(payload.get("data_coverage_score", 0)), source_quality_summary=payload.get("source_quality_summary", {}), review_status=str(payload.get("review_status", ""))
    )
