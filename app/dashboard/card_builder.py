"""Card builders and deterministic dashboard priority policy."""
from __future__ import annotations
from typing import Any, Dict, List

def dashboard_priority(stock: Dict[str, Any]) -> str:
    confidence = float(stock.get("confidence", 0))
    coverage = float(stock.get("source_coverage_score", 0))
    calibration_warning = bool(stock.get("calibration_warning"))
    missing_primary = bool(stock.get("missing_primary_sources"))
    recommendation = stock.get("adaptive_recommendation_summary", {})
    rec_direction = recommendation.get("recommended_direction")
    sample_status = stock.get("review_status")
    if sample_status in {"insufficient_sample", "pending_actual"}:
        return "watch"
    if confidence >= 0.75 and (calibration_warning or coverage < 0.65 or missing_primary):
        return "high"
    if rec_direction in {"decrease", "monitor"} and recommendation.get("major_factor", False):
        return "high"
    if coverage < 0.8 or calibration_warning or rec_direction == "monitor":
        return "medium"
    return "low"

def build_stock_card(stock: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "stock_id": stock["stock_id"],
        "stock_name": stock["stock_name"],
        "rating": stock["rating"],
        "score": stock["score"],
        "action": stock["action"],
        "confidence": stock["confidence"],
        "confidence_status": stock["confidence_status"],
        "prediction_targets": stock["prediction_targets"],
        "top_positive_factors": stock["top_positive_factors"],
        "top_negative_factors": stock["top_negative_factors"],
        "missing_data_factors": stock["missing_data_factors"],
        "source_coverage_readiness": stock["source_coverage_readiness"],
        "source_coverage_score": stock["source_coverage_score"],
        "calibration_warning": stock["calibration_warning"],
        "adaptive_recommendation_summary": stock["adaptive_recommendation_summary"],
        "dashboard_priority": dashboard_priority(stock),
        "review_status": stock["review_status"],
        "advisory_only": True,
    }

def summarize_stock_cards(stock_cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {key: 0 for key in ["high", "medium", "low", "watch", "not_available"]}
    for card in stock_cards:
        counts[card.get("dashboard_priority", "not_available")] += 1
    return {"count": len(stock_cards), "priority_counts": counts, "advisory_only": True}
