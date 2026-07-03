from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "market_regime_artifact_v1"
INPUT_SCHEMA_VERSION = "market_regime_input_v1"
SUPPORTED_REGIMES = {
    "trend_up",
    "trend_down",
    "range_bound",
    "high_volatility",
    "risk_on",
    "risk_off",
    "insufficient_data",
}
SUPPORTED_REASON_CODES = {
    "positive_trend_strength",
    "negative_trend_strength",
    "low_trend_strength",
    "volatility_above_threshold",
    "volatility_below_threshold",
    "breadth_positive",
    "breadth_negative",
    "drawdown_elevated",
    "momentum_positive",
    "momentum_negative",
    "sample_size_below_minimum",
    "missing_required_metrics",
}

@dataclass(frozen=True)
class MarketRegimeInput:
    schema_version: str
    as_of_date: str
    market: str
    sample_size: int
    metrics: dict[str, Any]
    source_kind: str = "offline_sample"
    advisory_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class MarketRegimeResult:
    regime: str
    confidence: float
    reason_codes: list[str]
    metrics_used: dict[str, Any]
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class MarketRegimeArtifact:
    schema_version: str
    generated_at: str
    input_summary: dict[str, Any]
    regime_result: dict[str, Any]
    regime_history_readiness: dict[str, Any]
    integration_notes: dict[str, Any]
    safety_summary: dict[str, Any]
    advisory_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def safety_summary() -> dict[str, bool]:
    return {
        "advisory_only": True,
        "production_scheduler_connected": False,
        "line_sent": False,
        "email_sent": False,
        "dashboard_published": False,
        "secrets_read": False,
        "production_db_write": False,
        "broker_login": False,
        "simulation_order": False,
        "production_order": False,
        "trading_execution": False,
        "production_confidence_mutation": False,
        "production_forecast_weight_mutation": False,
        "rating_action_rule_mutation": False,
    }
