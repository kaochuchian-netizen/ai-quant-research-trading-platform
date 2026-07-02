"""Build read-only factor recommendation artifacts."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List
from .contribution_analysis import compute_contribution_analysis
from .factor_effectiveness import compute_factor_effectiveness
from .horizon_effectiveness import compute_horizon_effectiveness
from .recommendation_policy import build_recommendations
from .schemas import FactorEffectivenessSample, sample_to_dicts
from .source_effectiveness import compute_source_effectiveness
from .target_effectiveness import compute_target_effectiveness

def _sample(i: int, group: str, factor: str, source: str, priority: str, category: str, target: str, horizon: str, hit: bool, actual: float, pred: float, contribution: float, confidence: float, evidence: float, complete: float = 0.95, available: bool = True, ready: bool = True, limitation: str = "") -> FactorEffectivenessSample:
    forecast = "up" if pred >= 0 else "down"
    actual_dir = forecast if hit else ("down" if forecast == "up" else "up")
    return FactorEffectivenessSample(f"sample-{i:03d}", group, factor, source, priority, category, target, horizon, forecast, actual_dir, pred, actual, confidence, evidence, min(1.0, abs(pred) / 3), contribution, complete, hit, hit or abs(actual - pred) < 1.2, available, ready, limitation)

def offline_sample_input() -> Dict[str, Any]:
    samples: List[FactorEffectivenessSample] = []
    i = 1
    targets = ["same_day_high_low", "next_day_high_low", "one_month_trend", "three_month_trend"]
    horizons = ["1D", "5D", "20D"]
    for n in range(24):
        hit = n % 4 != 0
        samples.append(_sample(i, "technical", "momentum_breakout", "sqlite_historical_csv", "B_verified_secondary", "price_history", targets[n % 4], horizons[n % 3], hit, 1.4 if hit else -0.5, 1.0, 0.68, 0.64, 0.72)); i += 1
    for n in range(24):
        hit = n % 5 != 0
        samples.append(_sample(i, "fundamental", "revenue_guidance", "company_filing", "A_primary", "company_disclosure", targets[n % 4], horizons[n % 3], hit, 1.8 if hit else -0.2, 1.2, 0.74, 0.68, 0.84)); i += 1
    for n in range(20):
        hit = n % 2 == 0 or n % 7 == 0
        samples.append(_sample(i, "chip", "foreign_institution_flow", "twse_chip", "B_verified_secondary", "chip_flow", targets[n % 4], horizons[n % 3], hit, 0.45 if hit else -0.35, 0.5, 0.36, 0.55, 0.58, limitation="marginal dry-run signal")); i += 1
    for n in range(20):
        hit = n % 3 == 0
        samples.append(_sample(i, "macro", "market_aggregate_pressure", "finmind_market", "C_market_aggregated", "market_context", targets[n % 4], horizons[n % 3], hit, -1.1 if not hit else 0.2, 0.9, 0.22, 0.58, 0.46, limitation="FinMind remains market-context only")); i += 1
    for n in range(14):
        hit = n % 2 == 0
        samples.append(_sample(i, "news", "rss_sentiment", "google_news_rss", "D_sentiment_or_noise", "sentiment", targets[n % 4], horizons[n % 3], hit, 0.1 if hit else -0.1, 0.4, 0.18, 0.52, 0.35, limitation="headline sentiment can be noisy")); i += 1
    for n in range(8):
        hit = n % 2 == 0
        samples.append(_sample(i, "adr", "adr_premarket_move", "yfinance_adr", "C_market_aggregated", "adr_context", targets[n % 4], horizons[n % 3], hit, 0.3 if hit else -0.3, 0.3, 0.25, 0.5, 0.42, limitation="yfinance is market-context metadata")); i += 1
    for n in range(3):
        samples.append(_sample(i, "missing_data", "unavailable_factor", "unknown_source", "D_sentiment_or_noise", "missing", targets[n % 4], horizons[n % 3], False, 0.0, 0.0, 0.0, 0.2, 0.1, complete=0.1, available=False, ready=False, limitation="missing attribution sample")); i += 1
    return {"schema_version": "1.0", "task_id": "AI-DEV-125", "generated_from": "offline_sample", "samples": sample_to_dicts(samples)}

def build_artifact(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = payload or offline_sample_input()
    samples = list(payload.get("samples", []))
    factor_effectiveness = compute_factor_effectiveness(samples)
    source_effectiveness = compute_source_effectiveness(samples)
    horizon_effectiveness = compute_horizon_effectiveness(samples)
    target_effectiveness = compute_target_effectiveness(samples, factor_effectiveness)
    contribution_analysis = compute_contribution_analysis(samples)
    return {
        "schema_version": "1.0", "task_id": "AI-DEV-125", "artifact_type": "factor_effectiveness_adaptive_recommendation_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_summary": {"sample_size": len(samples), "source": payload.get("generated_from", "provided_payload"), "production_data_used": False},
        "factor_effectiveness": factor_effectiveness, "source_effectiveness": source_effectiveness, "horizon_effectiveness": horizon_effectiveness,
        "target_effectiveness": target_effectiveness, "contribution_analysis": contribution_analysis,
        "adaptive_recommendations": build_recommendations(factor_effectiveness, source_effectiveness, horizon_effectiveness, target_effectiveness),
        "safety_summary": {"read_only": True, "dry_run": True, "production_mutation_allowed": False, "no_production_weight_change": True, "no_confidence_rule_change": True, "no_rating_or_action_change": True, "no_order_execution": True, "no_notification": True, "no_external_service_call": True, "human_review_required_for_all_changes": True},
        "future_integration": {"ai_dev_126_ready": True, "notes": ["Use this artifact as advisory input only.", "Future production tuning must pass a separate human-gated task.", "FinMind/yfinance/ADR/news sentiment remain secondary or metadata sources unless separately validated."]},
    }
