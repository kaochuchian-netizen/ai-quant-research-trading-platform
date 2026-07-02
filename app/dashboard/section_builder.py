"""Dashboard Intelligence section builder."""
from __future__ import annotations
from typing import Any, Dict, List
from .diagnostics_policy import build_diagnostics, suppress_traceback
from .intelligence_schema import DashboardCard, DashboardSection, card_to_dict, section_to_dict, safety_summary


def _card(card_id: str, card_type: str, title: str, summary: str, status: str) -> Dict[str, Any]:
    return card_to_dict(DashboardCard(card_id, card_type, title, suppress_traceback(summary), status))


def build_sections(inputs: Dict[str, Any], stock_cards: List[Dict[str, Any]], generated_at: str) -> List[Dict[str, Any]]:
    prediction = inputs["prediction_performance"]
    source = inputs["source_coverage"]
    explain = inputs["explainability"]
    calibration = inputs["confidence_calibration"]
    factor = inputs["factor_recommendation"]
    diagnostics = build_diagnostics(inputs)
    high_or_watch = sum(1 for card in stock_cards if card["dashboard_priority"] in {"high", "watch"})
    sections = [
        DashboardSection("today_overview", "Today Overview", "Mobile-first advisory summary for prediction, confidence, source coverage, recommendations, and diagnostics.", "review_required" if high_or_watch else "normal", [
            _card("overview-priority", "summary", "Stocks needing attention", f"{high_or_watch} cards need review.", "review_required"),
            _card("overview-safety", "safety", "Advisory only", "No trading, delivery, scheduler, production DB, confidence, rating/action, or weight mutation occurred.", "safe"),
        ], generated_at),
        DashboardSection("prediction_performance", "Prediction Performance", "Evaluation and confidence reliability summary.", prediction["confidence_summary"].get("status", "sample"), [
            _card("prediction-calibration", "prediction_performance", "Calibration", f"Weighted ECE {prediction['weighted_ece']} with {prediction['sample_size_warning']}", "sample_warning")
        ], generated_at),
        DashboardSection("stock_intelligence_cards", "Stock Intelligence Cards", "Per-stock dashboard-ready intelligence cards.", "available", stock_cards, generated_at),
        DashboardSection("source_coverage_data_quality", "Source Coverage & Data Quality", "Primary source gaps, supporting source status, and confidence cap reasons.", source.get("primary_source_status", "partial"), [
            _card("source-primary", "source_coverage", "Primary source status", ", ".join(source.get("missing_primary_sources", [])) or "Primary sources available", source.get("primary_source_status", "partial"))
        ], generated_at),
        DashboardSection("explainability", "Explainability", "Deterministic explanation without invented evidence.", explain.get("explainability_status", "available"), [
            _card("explainability-evidence", "explainability", "Evidence summary", explain.get("evidence_summary", "No evidence summary"), explain.get("explainability_status", "available"))
        ], generated_at),
        DashboardSection("confidence_calibration", "Confidence Calibration", "Confidence bucket findings and limitations.", calibration.get("finding", "sample_demo"), [
            _card("calibration-gap", "calibration", "Calibration gap", f"Bucket {calibration['confidence_bucket']} gap {calibration['calibration_gap']}; {calibration['recommendation_summary']}", calibration.get("finding", "sample_demo"))
        ], generated_at),
        DashboardSection("factor_recommendation", "Factor Recommendation", "Advisory-only factor recommendation summaries.", "advisory_only", [
            _card("factor-recommendation", "recommendation", "Recommendation summary", factor.get("summary", "No recommendations"), "human_review_required")
        ], generated_at),
        DashboardSection("diagnostics", "Diagnostics", "Operator diagnostics separated from main user-facing content.", "action_required" if diagnostics["operator_action_required"] else "ok", [
            _card("diagnostics-status", "diagnostics", "Artifact status", f"Missing artifacts: {', '.join(diagnostics['missing_artifacts']) or 'none'}", diagnostics["artifact_status"])
        ], generated_at),
        DashboardSection("safety_governance", "Safety & Governance", "Advisory-only, no-trading, no-production-publish status.", "safe", [
            _card("safety-boundary", "safety", "Safety boundary", "production_publish_allowed=false; production_mutation_allowed=false; advisory_only=true", "safe")
        ], generated_at),
    ]
    return [section_to_dict(section) for section in sections]
