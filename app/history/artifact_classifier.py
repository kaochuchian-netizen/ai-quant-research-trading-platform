from __future__ import annotations
from typing import Any
def classify_payload(payload: Any, source_path: str|None=None)->str:
    if isinstance(payload,str):
        low=payload.lower()
        if "pre_open_0700_hung" in low or "incident" in low or "traceback" in low: return "incident_diagnostic"
        return "unknown"
    if not isinstance(payload,dict): return "unknown"
    sv=str(payload.get("schema_version","")).lower(); keys=set(payload)
    if "approved_scheduler_delivery" in sv or {"scheduler_window","line_delivery","email_delivery"}&keys and "dashboard_delivery" in keys: return "approved_delivery"
    if "prediction_snapshot" in sv or "prediction_snapshots" in keys: return "prediction_snapshot"
    if "actual_outcome" in sv or "actual_outcomes" in keys: return "actual_outcome"
    if "prediction_evaluation" in sv or "evaluations" in keys or "direction_hit" in keys: return "evaluation"
    if "source_coverage" in sv or "source_coverage_matrix" in keys: return "source_coverage"
    if "source_evidence" in sv or "source_evidence" in keys: return "source_evidence"
    if "feature_attribution" in sv or "feature_attributions" in keys: return "feature_attribution"
    if "stock_explanations" in keys: return "stock_explanation"
    if "confidence_calibration" in sv or "confidence_bucket_analysis" in keys: return "confidence_calibration"
    if "factor_recommendation" in sv or "factor_effectiveness" in keys or "adaptive_recommendations" in keys: return "factor_recommendation"
    if "dashboard_intelligence" in sv or "stock_intelligence_cards" in keys or "dashboard_ready_summary" in keys: return "dashboard_intelligence"
    return "unknown"
def status_for_payload(payload: Any, artifact_type:str)->str:
    if artifact_type=="unknown": return "unsupported"
    if isinstance(payload,dict) and str(payload.get("content_state","")).lower() in {"pending","prediction_review_pending"}: return "pending"
    if isinstance(payload,dict) and str(payload.get("content_state","")).lower() in {"insufficient_data","prediction_review_insufficient_data"}: return "insufficient_data"
    return "valid"
