"""US-native PM presentation and intraday research-continuity contracts."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

CONTINUITY_STATES = {"ON_TRACK", "PARTIAL_DEVIATION", "BULLISH_BREAKOUT", "BEARISH_BREAKDOWN", "INVALIDATED", "INSUFFICIENT_SOURCE_LINEAGE"}

def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

def forecast_projection(card: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    """Create one US forecast truth consumed by Dashboard and delivery views."""
    if card.get("market_label") not in {"美股", "US"}:
        raise ValueError("US_MARKET_LINEAGE_REQUIRED")
    low, high = _number(prediction.get("predicted_session_low")), _number(prediction.get("predicted_session_high"))
    reference = _number(prediction.get("reference_price") or card.get("price"))
    if low is None or high is None or low > high:
        return {"schema_version": "us_premarket_product_projection_v1", "market": "US", "status": "INSUFFICIENT", "direction": "SIDEWAYS", "target_price": None, "predicted_low": low, "predicted_high": high, "reference_price": reference, "decision_authority": False}
    raw = str((card.get("daily_tactical_summary") or {}).get("direction") or "").lower()
    direction = "BULLISH" if "bull" in raw else "BEARISH" if "bear" in raw else "SIDEWAYS"
    return {"schema_version": "us_premarket_product_projection_v1", "market": "US", "status": "AVAILABLE", "direction": direction, "reference_price": reference, "target_price": round((low + high) / 2, 2), "predicted_low": low, "predicted_high": high, "horizon": "US_CURRENT_SESSION", "target_method": "canonical_prediction_interval_midpoint", "decision_authority": False, "execution_target": False}

def news_projection(value: dict[str, Any]) -> dict[str, Any]:
    """Expose compact funnel counts without recomputing provider evidence."""
    funnel = value.get("funnel") if isinstance(value.get("funnel"), dict) else {}
    stages = funnel.get("stages") if isinstance(funnel.get("stages"), dict) else {}
    retrieved = int(stages.get("NORMALIZED") or 0)
    qualified = min(int(stages.get("QUALITY_QUALIFIED") or 0), int(stages.get("FRESH") or 0), int(stages.get("RELEVANT") or 0), int(stages.get("MATERIAL") or 0))
    selected = int(value.get("selected_count") or 0)
    if not 0 <= selected <= qualified <= retrieved:
        raise ValueError("US_NEWS_FUNNEL_COUNT_ORDER_INVALID")
    return {"schema_version": "us_news_product_projection_v1", "market": "US", "retrieved_count": retrieved, "qualified_count": qualified, "selected_count": selected, "selected_items": deepcopy(list(value.get("selected_items") or [])[:3]), "state": value.get("state"), "state_label": value.get("state_label"), "rejection_reasons": deepcopy(funnel.get("rejection_reasons") or {}), "retrieval": deepcopy(funnel.get("retrieval") or {}), "source_contract": "finalized_current_news_projection_v3"}

def intraday_continuity(bundle: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    continuity = bundle.get("continuity") if isinstance(bundle.get("continuity"), dict) else {}
    origin = bundle.get("research_intelligence_v2") if isinstance(bundle.get("research_intelligence_v2"), dict) else {}
    source_id, revision = continuity.get("source_snapshot_id"), continuity.get("source_revision")
    if continuity.get("status") != "inherited" or not source_id or not revision:
        state = "INSUFFICIENT_SOURCE_LINEAGE"
    else:
        state = {"confirmed": "ON_TRACK", "strengthened": "BULLISH_BREAKOUT", "unchanged": "ON_TRACK", "weakened": "PARTIAL_DEVIATION", "contradicted": "PARTIAL_DEVIATION", "invalidated": "INVALIDATED", "insufficient_new_evidence": "PARTIAL_DEVIATION"}.get(str((origin.get("hypothesis") or {}).get("state")), "ON_TRACK")
    return {"schema_version": "us_intraday_research_continuity_v1", "market": "US", "source_market": "US", "source_window": "us_pre_market_2000", "source_snapshot_id": source_id, "source_revision": revision, "source_research_identity": bundle.get("research_identity"), "current_window_research_identity": origin.get("window_research_identity"), "continuity_state": state, "market_data_sufficiency": "COMPLETE" if observed.get("data_status") == "complete" else "PARTIAL" if observed.get("data_status") == "partial" else "INSUFFICIENT", "research_sufficiency": "INSUFFICIENT" if state == "INSUFFICIENT_SOURCE_LINEAGE" else "AVAILABLE", "news_sufficiency": "AVAILABLE" if (bundle.get("news_intelligence_v2") or {}).get("selected_items") else "LIMITED", "lineage_sufficiency": "INSUFFICIENT" if state == "INSUFFICIENT_SOURCE_LINEAGE" else "COMPLETE", "decision_authority": False}

def validate_us_product(value: dict[str, Any], *, expected_window: str) -> list[str]:
    errors: list[str] = []
    if value.get("market") != "US": errors.append("market_lineage")
    if any(str(v).upper().startswith("TW") for v in value.values() if isinstance(v, str)): errors.append("tw_lineage_injection")
    if expected_window == "us_pre_market_2000" and value.get("status") == "AVAILABLE":
        low, target, high = map(_number, (value.get("predicted_low"), value.get("target_price"), value.get("predicted_high")))
        if None in {low, target, high} or not low <= target <= high: errors.append("forecast_interval")
    if expected_window == "us_intraday_2300":
        if value.get("continuity_state") not in CONTINUITY_STATES: errors.append("continuity_state")
        if value.get("continuity_state") != "INSUFFICIENT_SOURCE_LINEAGE" and not value.get("source_snapshot_id"): errors.append("source_snapshot_id")
    return sorted(set(errors))
