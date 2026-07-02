"""Schemas for AI-DEV-124 confidence calibration V1."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any
SCHEMA_VERSION = "confidence_calibration_v1"
INPUT_SCHEMA_VERSION = "confidence_calibration_input_v1"
SUPPORTED_TARGETS = {"intraday_high_low", "next_day_high_low", "one_month_trend", "three_month_trend", "rating_action"}
CALIBRATION_FINDINGS = {"well_calibrated", "over_confident", "under_confident", "unstable", "insufficient_sample", "not_available"}
RATINGS = ("A", "B", "C", "D", "E", "unknown")
PLATFORM_ACTIONS = ("偏多加碼", "偏多續抱", "中性觀察", "降低追價", "保守觀望", "unknown")
READINESS_GROUPS = ("ready", "partial", "insufficient", "unknown")
def is_number(value: Any) -> bool: return isinstance(value, (int, float)) and not isinstance(value, bool)
def as_float(value: Any) -> float | None: return float(value) if is_number(value) else None
def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool): return value
    if value in (0, 1) and not isinstance(value, bool): return bool(value)
    return None
def mean(values: list[float]) -> float | None: return sum(values) / len(values) if values else None
def median(values: list[float]) -> float | None:
    if not values: return None
    ordered = sorted(values); mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
def pct(value: float | None) -> float | None: return None if value is None else round(value, 6)
@dataclass(frozen=True)
class CalibrationSample:
    schema_version: str; run_id: str; stock_id: str; stock_name: str; prediction_target: str; prediction_date: str; target_date: str; confidence: float | None; confidence_status: str; rating: str; score: float | None; action: str; source_coverage_readiness: str; source_coverage_score: float | None; predicted_high: float | None; predicted_low: float | None; predicted_trend: str | None; actual_high: float | None; actual_low: float | None; actual_close: float | None; actual_return_1d: float | None; actual_return_5d: float | None; actual_return_20d: float | None; direction_hit: bool | None; close_direction_hit: bool | None; high_error_pct: float | None; low_error_pct: float | None; evaluation_status: str; source_ids: list[str] = field(default_factory=list); evidence_ids: list[str] = field(default_factory=list); advisory_only: bool = True
    def to_dict(self) -> dict[str, Any]: return asdict(self)
    def validate(self) -> list[str]:
        reasons: list[str] = []
        if self.schema_version != SCHEMA_VERSION: reasons.append("invalid calibration sample schema_version")
        if self.prediction_target not in SUPPORTED_TARGETS: reasons.append(f"invalid prediction_target: {self.prediction_target}")
        if self.confidence is not None and not 0 <= self.confidence <= 1: reasons.append("confidence must be between 0 and 1")
        if self.source_coverage_score is not None and not 0 <= self.source_coverage_score <= 1: reasons.append("source_coverage_score must be between 0 and 1")
        if self.source_coverage_readiness not in READINESS_GROUPS: reasons.append(f"invalid source_coverage_readiness: {self.source_coverage_readiness}")
        if not self.advisory_only: reasons.append("calibration sample must be advisory_only")
        return reasons
@dataclass(frozen=True)
class CalibrationInput:
    schema_version: str; samples: list[CalibrationSample]; input_summary: dict[str, Any] = field(default_factory=dict); advisory_only: bool = True
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self); data["samples"] = [s.to_dict() for s in self.samples]; return data
    def validate(self) -> list[str]:
        reasons: list[str] = []
        if self.schema_version != INPUT_SCHEMA_VERSION: reasons.append("invalid calibration input schema_version")
        if not self.advisory_only: reasons.append("calibration input must be advisory_only")
        for index, sample in enumerate(self.samples):
            for reason in sample.validate(): reasons.append(f"samples[{index}]: {reason}")
        return reasons
@dataclass(frozen=True)
class ConfidenceBucketResult:
    bucket: str; sample_size: int; unavailable_count: int; avg_confidence: float | None; direction_hit_rate: float | None; close_direction_hit_rate: float | None; calibration_gap: float | None; absolute_calibration_error: float | None; finding: str; recommendation: str
    def to_dict(self) -> dict[str, Any]: return asdict(self)
@dataclass(frozen=True)
class RatingEffectivenessResult:
    rating: str; sample_size: int; direction_hit_rate: float | None; avg_return_1d: float | None; avg_return_5d: float | None; avg_return_20d: float | None; median_return_1d: float | None; median_return_5d: float | None; median_return_20d: float | None; positive_return_rate_1d: float | None; positive_return_rate_5d: float | None; positive_return_rate_20d: float | None; finding: str
    def to_dict(self) -> dict[str, Any]: return asdict(self)
@dataclass(frozen=True)
class ActionEffectivenessResult:
    action: str; sample_size: int; direction_hit_rate: float | None; avg_return_1d: float | None; avg_return_5d: float | None; avg_return_20d: float | None; positive_return_rate_1d: float | None; positive_return_rate_5d: float | None; positive_return_rate_20d: float | None; finding: str
    def to_dict(self) -> dict[str, Any]: return asdict(self)
@dataclass(frozen=True)
class HighLowErrorResult:
    sample_size: int; avg_high_error_pct: float | None; avg_low_error_pct: float | None; median_high_error_pct: float | None; median_low_error_pct: float | None; avg_high_bias_pct: float | None; avg_low_bias_pct: float | None; high_overestimate_rate: float | None; high_underestimate_rate: float | None; low_overestimate_rate: float | None; low_underestimate_rate: float | None; range_too_wide_rate: float | None; range_too_narrow_rate: float | None; finding: str
    def to_dict(self) -> dict[str, Any]: return asdict(self)
@dataclass(frozen=True)
class SourceCoverageAccuracyResult:
    source_coverage_readiness: str; sample_size: int; direction_hit_rate: float | None; avg_confidence: float | None; calibration_gap: float | None; avg_return_1d: float | None; avg_return_5d: float | None; avg_return_20d: float | None; high_error_pct: float | None; low_error_pct: float | None; finding: str
    def to_dict(self) -> dict[str, Any]: return asdict(self)
@dataclass(frozen=True)
class CalibrationFinding:
    finding_id: str; target_area: str; finding: str; severity: str; evidence_summary: str; sample_size: int; limitations: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]: return asdict(self)
@dataclass(frozen=True)
class CalibrationRecommendation:
    recommendation_id: str; severity: str; target_area: str; finding: str; evidence_summary: str; recommended_action: str; production_mutation_allowed: bool; requires_human_review: bool; related_metrics: dict[str, Any]; sample_size: int; limitations: list[str]
    def to_dict(self) -> dict[str, Any]: return asdict(self)
@dataclass(frozen=True)
class ConfidenceCalibrationArtifact:
    schema_version: str; generated_at: str; input_summary: dict[str, Any]; sample_window: dict[str, Any]; sample_size_summary: dict[str, Any]; confidence_bucket_analysis: list[dict[str, Any]]; overall_calibration_metrics: dict[str, Any]; rating_effectiveness: list[dict[str, Any]]; action_effectiveness: list[dict[str, Any]]; high_low_error_analysis: dict[str, Any]; source_coverage_accuracy: list[dict[str, Any]]; calibration_findings: list[dict[str, Any]]; recommendations: list[dict[str, Any]]; safety_summary: dict[str, Any]; future_integration: dict[str, Any]
    def to_dict(self) -> dict[str, Any]: return asdict(self)
def sample_from_dict(payload: dict[str, Any]) -> CalibrationSample:
    high = as_float(payload.get("predicted_high")); low = as_float(payload.get("predicted_low")); actual_high = as_float(payload.get("actual_high")); actual_low = as_float(payload.get("actual_low")); high_error = as_float(payload.get("high_error_pct")); low_error = as_float(payload.get("low_error_pct"))
    if high_error is None and high is not None and actual_high not in (None, 0): high_error = abs(high - actual_high) / actual_high
    if low_error is None and low is not None and actual_low not in (None, 0): low_error = abs(low - actual_low) / actual_low
    rating = str(payload.get("rating") or "unknown"); rating = rating if rating in RATINGS else "unknown"
    action = str(payload.get("action") or "unknown"); action = action if action in PLATFORM_ACTIONS else "unknown"
    readiness = str(payload.get("source_coverage_readiness") or "unknown"); readiness = readiness if readiness in READINESS_GROUPS else "unknown"
    return CalibrationSample(str(payload.get("schema_version") or SCHEMA_VERSION), str(payload.get("run_id") or ""), str(payload.get("stock_id") or ""), str(payload.get("stock_name") or ""), str(payload.get("prediction_target") or "rating_action"), str(payload.get("prediction_date") or ""), str(payload.get("target_date") or ""), as_float(payload.get("confidence")), str(payload.get("confidence_status") or "unknown"), rating, as_float(payload.get("score")), action, readiness, as_float(payload.get("source_coverage_score")), high, low, payload.get("predicted_trend"), actual_high, actual_low, as_float(payload.get("actual_close")), as_float(payload.get("actual_return_1d")), as_float(payload.get("actual_return_5d")), as_float(payload.get("actual_return_20d")), as_bool(payload.get("direction_hit")), as_bool(payload.get("close_direction_hit")), high_error, low_error, str(payload.get("evaluation_status") or "unknown"), [str(x) for x in payload.get("source_ids", [])], [str(x) for x in payload.get("evidence_ids", [])], bool(payload.get("advisory_only", True)))
def input_from_dict(payload: dict[str, Any]) -> CalibrationInput:
    raw = payload.get("samples", []); samples = [sample_from_dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    return CalibrationInput(str(payload.get("schema_version") or INPUT_SCHEMA_VERSION), samples, dict(payload.get("input_summary", {})), bool(payload.get("advisory_only", True)))
