"""Shared schemas for AI-DEV-125 recommendation dry-run artifacts."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from statistics import mean, median
from typing import Any, Dict, Iterable, List

FACTOR_GROUPS = ["technical", "fundamental", "chip", "macro", "news", "adr", "missing_data"]
SOURCE_PRIORITIES = ["A_primary", "B_verified_secondary", "C_market_aggregated", "D_sentiment_or_noise"]
PREDICTION_TARGETS = ["same_day_high_low", "next_day_high_low", "one_month_trend", "three_month_trend"]
RECOMMENDATION_DIRECTIONS = ["increase", "decrease", "hold", "monitor", "exclude_from_increase"]
EFFECTIVENESS_FINDINGS = ["effective", "weakly_effective", "noisy", "inverted", "insufficient_sample"]
TARGET_AREAS = ["factor_weight", "source_priority", "time_horizon", "prediction_target", "feature_group"]
HORIZONS = ["1D", "5D", "20D"]

@dataclass(frozen=True)
class FactorEffectivenessSample:
    sample_id: str
    factor_group: str
    factor_name: str
    source_id: str
    source_priority: str
    source_category: str
    prediction_target: str
    horizon: str
    forecast_direction: str
    actual_direction: str
    predicted_return_pct: float
    actual_return_pct: float
    confidence: float
    evidence_score: float
    factor_signal_strength: float
    contribution_score: float
    data_completeness: float
    is_hit: bool
    interval_covered: bool
    source_available: bool
    source_ready: bool
    limitation: str = ""

@dataclass(frozen=True)
class AdaptiveRecommendation:
    recommendation_id: str
    target_area: str
    target_key: str
    direction: str
    reason: str
    evidence_count: int
    confidence: float
    human_review_required: bool
    production_mutation_allowed: bool
    guardrails: List[str]

def sample_to_dicts(samples: Iterable[FactorEffectivenessSample]) -> List[Dict[str, Any]]:
    return [asdict(sample) for sample in samples]

def load_samples(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(payload.get("samples", []))

def safe_avg(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    return round(mean(vals), 6) if vals else 0.0

def safe_median(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    return round(median(vals), 6) if vals else 0.0

def positive_rate(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    return round(sum(1 for v in vals if v > 0) / len(vals), 6) if vals else 0.0

def bool_rate(values: Iterable[bool]) -> float:
    vals = list(values)
    return round(sum(1 for v in vals if bool(v)) / len(vals), 6) if vals else 0.0

def usable_samples(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in rows if row.get("data_completeness", 0) >= 0.7 and row.get("source_available")]
