"""Schemas for actual outcomes and deterministic evaluation V1."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any
ACTUAL_OUTCOME_SCHEMA_VERSION = "actual_outcome_v1"
EVALUATION_SCHEMA_VERSION = "prediction_evaluation_v1"
OUTCOME_STATUSES = {"completed", "pending", "missing", "insufficient_data"}
EVALUATION_STATUSES = {"evaluated", "pending_actual_outcome", "insufficient_prediction_data"}
NOT_AVAILABLE = "not_available"
@dataclass(frozen=True)
class ActualOutcome:
    schema_version: str; stock_id: str; target_date: str; actual_open: float | None; actual_high: float | None; actual_low: float | None; actual_close: float | None; actual_volume: float | None; actual_return_1d: float | None; actual_return_5d: float | None; actual_return_20d: float | None; outcome_status: str
    def to_dict(self) -> dict[str, Any]: return asdict(self)
    def validate(self) -> list[str]:
        reasons: list[str] = []
        if self.schema_version != ACTUAL_OUTCOME_SCHEMA_VERSION: reasons.append("invalid actual outcome schema_version")
        if self.outcome_status not in OUTCOME_STATUSES: reasons.append(f"invalid outcome_status: {self.outcome_status}")
        if self.outcome_status == "completed":
            for field in ["actual_open", "actual_high", "actual_low", "actual_close", "actual_volume"]:
                if getattr(self, field) is None: reasons.append(f"completed outcome missing {field}")
        return reasons
@dataclass(frozen=True)
class EvaluationResult:
    schema_version: str; run_id: str; stock_id: str; prediction_target: str; target_date: str; direction_hit: bool | str | None; high_error_pct: float | str | None; low_error_pct: float | str | None; close_direction_hit: bool | str | None; rating_return_1d: float | str | None; action_return_1d: float | str | None; evaluation_status: str; pending_reason: str | None
    def to_dict(self) -> dict[str, Any]: return asdict(self)
    def validate(self) -> list[str]:
        reasons: list[str] = []
        if self.schema_version != EVALUATION_SCHEMA_VERSION: reasons.append("invalid evaluation schema_version")
        if self.evaluation_status not in EVALUATION_STATUSES: reasons.append(f"invalid evaluation_status: {self.evaluation_status}")
        if self.evaluation_status == "pending_actual_outcome" and not self.pending_reason: reasons.append("pending evaluation requires pending_reason")
        return reasons
def as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool): return float(value)
    return None
