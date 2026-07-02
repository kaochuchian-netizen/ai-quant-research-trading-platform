"""Read-only adaptive recommendation policy."""
from __future__ import annotations
from typing import Any, Dict, List
from .schemas import AdaptiveRecommendation

def _rec(idx: int, target_area: str, key: str, direction: str, reason: str, count: int, confidence: float) -> Dict[str, Any]:
    return AdaptiveRecommendation(
        recommendation_id=f"rec-{idx:03d}", target_area=target_area, target_key=key, direction=direction, reason=reason,
        evidence_count=count, confidence=round(confidence, 6), human_review_required=True, production_mutation_allowed=False,
        guardrails=["read-only dry-run recommendation", "no production forecast weight mutation", "no confidence/rating/action rule mutation", "requires human review before any future production change"],
    ).__dict__

def build_recommendations(factors: List[Dict[str, Any]], sources: List[Dict[str, Any]], horizons: List[Dict[str, Any]], targets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    idx = 1
    for row in factors:
        finding = row.get("finding")
        group = row.get("factor_group")
        if finding == "effective" and row.get("usable_sample_size", 0) >= 20:
            recs.append(_rec(idx, "factor_weight", group, "increase", "offline sample shows stable effectiveness", row["usable_sample_size"], row["effectiveness_score"] / 100)); idx += 1
        elif finding in {"weakly_effective", "noisy"}:
            recs.append(_rec(idx, "factor_weight", group, "hold", "effect is not strong enough for promotion", row.get("usable_sample_size", 0), row["effectiveness_score"] / 100)); idx += 1
        elif finding == "inverted":
            recs.append(_rec(idx, "factor_weight", group, "decrease", "sample suggests inverted or adverse contribution", row.get("usable_sample_size", 0), 0.6)); idx += 1
        elif finding == "insufficient_sample":
            recs.append(_rec(idx, "feature_group", group, "monitor", "insufficient sample; do not increase or decrease", row.get("usable_sample_size", 0), 0.2)); idx += 1
    for source in sources:
        priority = source.get("source_priority")
        key = f"{priority}:{source.get('source_id')}"
        if priority == "D_sentiment_or_noise":
            recs.append(_rec(idx, "source_priority", key, "exclude_from_increase", "sentiment/noise source can only support metadata", source.get("usable_sample_size", 0), 0.75)); idx += 1
        elif priority == "C_market_aggregated":
            recs.append(_rec(idx, "source_priority", key, "monitor", "aggregated market source remains context, not primary evidence", source.get("usable_sample_size", 0), 0.55)); idx += 1
    for target in targets:
        if target.get("hit_rate", 0) < 0.5:
            recs.append(_rec(idx, "prediction_target", target.get("prediction_target"), "hold", "target needs further review before production tuning", target.get("sample_size", 0), target.get("hit_rate", 0))); idx += 1
    if not recs:
        recs.append(_rec(idx, "feature_group", "all", "hold", "no change recommended", 0, 0.0))
    return recs
