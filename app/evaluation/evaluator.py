"""Deterministic evaluation logic for prediction snapshots."""
from __future__ import annotations
from typing import Any
from app.evaluation.schemas import EVALUATION_SCHEMA_VERSION, NOT_AVAILABLE, ActualOutcome, EvaluationResult, as_float
from app.prediction.schemas import PredictionSnapshot, prediction_snapshot_from_dict

def _trend_from_return(value: float | None) -> str | None:
    if value is None: return None
    if value > 0: return "up"
    if value < 0: return "down"
    return "flat"
def _direction_hit(predicted: Any, actual_return: float | None) -> bool | str | None:
    if not isinstance(predicted, str) or predicted in {"pending", "insufficient_data", "unavailable", "not_applicable"}: return NOT_AVAILABLE
    actual = _trend_from_return(actual_return)
    if actual is None: return NOT_AVAILABLE
    normalized = predicted.lower()
    if normalized in {"positive", "bullish"}: normalized = "up"
    elif normalized in {"negative", "bearish"}: normalized = "down"
    elif normalized in {"neutral", "sideways"}: normalized = "flat"
    if normalized not in {"up", "down", "flat"}: return NOT_AVAILABLE
    return normalized == actual
def _error_pct(predicted: Any, actual: float | None) -> float | str:
    predicted_float = as_float(predicted)
    if predicted_float is None or actual in (None, 0): return NOT_AVAILABLE
    return round((predicted_float - float(actual)) / float(actual), 6)
def evaluate_prediction_snapshot(snapshot: PredictionSnapshot | dict[str, Any], actual: ActualOutcome | dict[str, Any]) -> EvaluationResult:
    snapshot_obj = prediction_snapshot_from_dict(snapshot) if isinstance(snapshot, dict) else snapshot
    actual_obj = ActualOutcome(**actual) if isinstance(actual, dict) else actual
    if actual_obj.outcome_status != "completed":
        return EvaluationResult(EVALUATION_SCHEMA_VERSION, snapshot_obj.run_id, snapshot_obj.stock_id, snapshot_obj.prediction_target, actual_obj.target_date, None, NOT_AVAILABLE, NOT_AVAILABLE, None, NOT_AVAILABLE, NOT_AVAILABLE, "pending_actual_outcome", f"actual_outcome_{actual_obj.outcome_status}")
    high_error = _error_pct(snapshot_obj.predicted_high, actual_obj.actual_high); low_error = _error_pct(snapshot_obj.predicted_low, actual_obj.actual_low); direction_hit = _direction_hit(snapshot_obj.predicted_trend, actual_obj.actual_return_1d)
    rating_return_1d: float | str | None = NOT_AVAILABLE; action_return_1d: float | str | None = NOT_AVAILABLE
    if isinstance(snapshot_obj.rating, str) and snapshot_obj.rating not in {"pending", "insufficient_data", "unavailable", "not_applicable"}: rating_return_1d = actual_obj.actual_return_1d if actual_obj.actual_return_1d is not None else NOT_AVAILABLE
    if isinstance(snapshot_obj.action, str) and snapshot_obj.action not in {"pending", "insufficient_data", "unavailable", "not_applicable"}: action_return_1d = actual_obj.actual_return_1d if actual_obj.actual_return_1d is not None else NOT_AVAILABLE
    status = "evaluated"; pending_reason = None
    if high_error == NOT_AVAILABLE and low_error == NOT_AVAILABLE and direction_hit == NOT_AVAILABLE: status = "insufficient_prediction_data"; pending_reason = "prediction_high_low_direction_not_available"
    return EvaluationResult(EVALUATION_SCHEMA_VERSION, snapshot_obj.run_id, snapshot_obj.stock_id, snapshot_obj.prediction_target, actual_obj.target_date, direction_hit, high_error, low_error, direction_hit if snapshot_obj.prediction_target != "rating_action" else NOT_AVAILABLE, rating_return_1d, action_return_1d, status, pending_reason)
def evaluate_many(snapshots: list[PredictionSnapshot], outcomes: list[ActualOutcome]) -> list[EvaluationResult]:
    outcome_by_key = {(item.stock_id, item.target_date): item for item in outcomes}; return [evaluate_prediction_snapshot(snapshot, outcome_by_key[(snapshot.stock_id, snapshot.run_date)]) for snapshot in snapshots if (snapshot.stock_id, snapshot.run_date) in outcome_by_key]
