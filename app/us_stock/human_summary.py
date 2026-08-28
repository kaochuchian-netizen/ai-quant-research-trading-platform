"""Presentation-only US decision summaries for the three canonical windows."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

SCHEMA_VERSION = "us_human_decision_summary_v1"
WINDOWS = {"us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"}
HYPOTHESIS_LABELS = {
    "confirmed": "CONFIRMED", "strengthened": "CONFIRMED", "unchanged": "STILL_VALID",
    "weakened": "WEAKENED", "contradicted": "WEAKENED", "invalidated": "INVALIDATED",
    "insufficient_new_evidence": "INSUFFICIENT_EVIDENCE", "created": "STILL_VALID",
}


def _number(value: Any) -> float | None:
    try:
        return round(float(value), 6) if value is not None else None
    except (TypeError, ValueError):
        return None


def _research(card: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = card.get("institutional_research") if isinstance(card.get("institutional_research"), dict) else {}
    projection = bundle.get("research_intelligence_v2") if isinstance(bundle.get("research_intelligence_v2"), dict) else {}
    return bundle, projection


def _news_impact(item: dict[str, Any]) -> dict[str, Any]:
    attribution = item.get("entity_attribution") if isinstance(item.get("entity_attribution"), dict) else {}
    direction = str(item.get("direction") or "unavailable").lower()
    contextual = item.get("contextual_role") or (
        "CONTEXTUALIZE" if attribution.get("framing_class") in {"MARKET_MACRO_REACTION", "SECTOR_ROUNDUP"} else None
    )
    role = str(item.get("role") or contextual or ("SUPPORTING" if direction == "bullish" else "OPPOSING" if direction == "bearish" else "CONTEXT")).upper()
    relationship = attribution.get("relationship_type")
    if relationship:
        impact = f"此事件涉及 {relationship} 關係，提供公司營運與事件風險脈絡；不單獨改寫交易方向。"
    elif contextual:
        impact = "此事件提供總體／產業價格脈絡，可確認或反駁研究情境，但不單獨建立公司方向。"
    elif direction == "bullish":
        impact = "此事件提供偏多研究證據，仍須與價格、官方資料及反方證據共同驗證。"
    elif direction == "bearish":
        impact = "此事件提供偏空風險證據，需檢查是否削弱或使原研究假設失效。"
    else:
        impact = "此事件提供當期研究脈絡，方向尚未評估，不單獨建立公司方向。"
    return {
        "news_id": item.get("news_id"), "news_event_id": item.get("news_event_id") or item.get("event_cluster_id"),
        "headline": item.get("headline") or item.get("english_headline"),
        "publisher": item.get("publisher") or "原始來源未解析", "published_at": item.get("published_at"),
        "source_class": item.get("source_class"), "role": role, "impact_summary": impact,
        "entity_attribution": deepcopy(attribution) if attribution else None,
    }


def _important_news(card: dict[str, Any]) -> list[dict[str, Any]]:
    finalized = card.get("finalized_current_news_projection_v3") if isinstance(card.get("finalized_current_news_projection_v3"), dict) else {}
    items = [item for item in finalized.get("selected_items") or [] if isinstance(item, dict)]
    return [_news_impact(item) for item in items[:4]]


def _base(card: dict[str, Any], window: str) -> dict[str, Any]:
    bundle, research = _research(card)
    synthesis = bundle.get("synthesis") if isinstance(bundle.get("synthesis"), dict) else {}
    strategies = card.get("strategies") if isinstance(card.get("strategies"), dict) else {}
    position = card.get("research_position_summary") if isinstance(card.get("research_position_summary"), dict) else strategies.get("research_position") or {}
    tactical = card.get("daily_tactical_summary") if isinstance(card.get("daily_tactical_summary"), dict) else strategies.get("daily_tactical") or {}
    hypothesis = research.get("hypothesis") if isinstance(research.get("hypothesis"), dict) else {}
    evidence_by_id = {str(item.get("evidence_id")): item for item in bundle.get("evidence") or [] if isinstance(item, dict) and item.get("evidence_id")}
    supporting = [item if isinstance(item, dict) else evidence_by_id.get(str(item), {}) for item in research.get("supporting_evidence") or []]
    opposing = [item if isinstance(item, dict) else evidence_by_id.get(str(item), {}) for item in research.get("opposing_evidence") or []]
    reasons = [str(item.get("headline") or item.get("summary")) for item in [*supporting[:2], *opposing[:2]] if item.get("headline") or item.get("summary")]
    if reasons:
        reasons[0] = "短評：" + reasons[0]
    return {
        "schema_version": SCHEMA_VERSION, "market": "US", "window": window,
        "symbol": str(card.get("symbol") or card.get("stock_id") or "").upper(),
        "direction": None, "confidence": card.get("confidence"),
        "forecast_target": None, "forecast_low": None, "forecast_high": None,
        "research_stance": synthesis.get("research_stance") or position.get("rating") or position.get("action"),
        "daily_tactical_stance": tactical.get("direction") or tactical.get("tactical_direction") or tactical.get("action"),
        "key_reasons": reasons[:4], "main_risk": research.get("primary_risk"),
        "important_news": _important_news(card), "continuity_state": None, "evaluation_state": None,
        "research_identity": bundle.get("research_identity"), "window_research_identity": research.get("window_research_identity"),
        "hypothesis_identity": research.get("hypothesis_identity") or research.get("window_research_identity"),
        "hypothesis_state": HYPOTHESIS_LABELS.get(str(hypothesis.get("state") or ""), "INSUFFICIENT_EVIDENCE"),
        "decision_authority": False,
    }


def build_us_human_summary(card: dict[str, Any], window: str) -> dict[str, Any]:
    if window not in WINDOWS:
        raise ValueError("UNSUPPORTED_US_WINDOW")
    result = _base(card, window)
    if window == "us_pre_market_2000":
        forecast = card.get("us_premarket_product_projection_v1") if isinstance(card.get("us_premarket_product_projection_v1"), dict) else {}
        result.update({
            "direction": forecast.get("direction"), "forecast_target": forecast.get("target_price"),
            "forecast_low": forecast.get("predicted_low"), "forecast_high": forecast.get("predicted_high"),
            "continuity_state": "ORIGINATED", "evaluation_state": "PENDING_INTRADAY",
        })
    elif window == "us_intraday_2300":
        source = card.get("source_plan") if isinstance(card.get("source_plan"), dict) else card.get("source_trade_plan") or {}
        forecast = source.get("forecast") if isinstance(source.get("forecast"), dict) else {}
        continuity = card.get("us_intraday_research_continuity_v1") if isinstance(card.get("us_intraday_research_continuity_v1"), dict) else {}
        low, high, target, current = map(_number, (forecast.get("predicted_low"), forecast.get("predicted_high"), forecast.get("target_price"), card.get("current_price")))
        position = "INSUFFICIENT_DATA"
        if None not in (low, high, current):
            position = "BELOW_RANGE" if current < low else "ABOVE_RANGE" if current > high else "WITHIN_RANGE"
        progress = None
        reference = _number(forecast.get("reference_price"))
        if None not in (current, target, reference) and target != reference:
            progress = round((current - reference) / (target - reference) * 100, 2)
        current_confidence, original_confidence = _number(card.get("confidence")), _number(source.get("confidence"))
        result.update({
            "direction": forecast.get("direction"), "confidence": current_confidence,
            "forecast_target": target, "forecast_low": low, "forecast_high": high,
            "current_price": current, "range_position": position, "target_progress_pct": progress,
            "original_confidence": original_confidence,
            "confidence_change": None if None in (current_confidence, original_confidence) else round(current_confidence - original_confidence, 2),
            "tactical_trigger_state": card.get("entry_trigger_state"),
            "continuity_state": result["hypothesis_state"] if continuity.get("lineage_sufficiency") != "INSUFFICIENT" else "INSUFFICIENT_EVIDENCE",
            "evaluation_state": "INTRADAY_OBSERVED", "source_snapshot_id": continuity.get("source_snapshot_id"),
            "source_revision": continuity.get("source_revision"),
        })
    else:
        review = card.get("review") if isinstance(card.get("review"), dict) else {}
        source = card.get("source_trade_plan") if isinstance(card.get("source_trade_plan"), dict) else {}
        forecast = source.get("forecast") if isinstance(source.get("forecast"), dict) else {}
        prediction = review.get("originating_prediction") if isinstance(review.get("originating_prediction"), dict) else {}
        evaluation = review.get("prediction_evaluation_v2") if isinstance(review.get("prediction_evaluation_v2"), dict) else {}
        if not evaluation:
            evaluation = card.get("prediction_evaluation_v2") if isinstance(card.get("prediction_evaluation_v2"), dict) else {}
        range_eval = evaluation.get("range") if isinstance(evaluation.get("range"), dict) else {}
        direction_eval = evaluation.get("direction") if isinstance(evaluation.get("direction"), dict) else {}
        low = forecast.get("predicted_low", prediction.get("predicted_session_low"))
        high = forecast.get("predicted_high", prediction.get("predicted_session_high"))
        target = forecast.get("target_price")
        diagnosis = card.get("research_review_diagnosis") if isinstance(card.get("research_review_diagnosis"), dict) else {}
        result.update({
            "direction": forecast.get("direction") or direction_eval.get("predicted_direction"),
            "forecast_target": target, "forecast_low": low, "forecast_high": high,
            "actual_high": review.get("actual_high"), "actual_low": review.get("actual_low"), "actual_close": review.get("actual_close"),
            "direction_result": direction_eval.get("result") or evaluation.get("direction_result"),
            "range_result": card.get("prediction_range_result") or ("hit" if range_eval.get("hit") else "miss" if range_eval.get("hit") is False else None),
            "forecast_errors": {"high": range_eval.get("high_error", review.get("high_error")), "low": range_eval.get("low_error", review.get("low_error")), "midpoint": range_eval.get("midpoint_error")},
            "mfe": review.get("mfe"), "mae": review.get("mae"), "trade_outcome": card.get("trade_review_outcome") or review.get("trade_review_outcome"),
            "continuity_state": result["hypothesis_state"], "evaluation_state": range_eval.get("status") or card.get("review_status"),
            "major_evidence_lesson": diagnosis.get("research_diagnosis") or "依來源預測、實際行情與研究證據完成檢討；不自動調整權重。",
            "next_session_carry_forward": diagnosis.get("next_session_carryforward") or review.get("next_session_action"),
        })
    return result


def validate_us_human_summary(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("schema_version") != SCHEMA_VERSION or value.get("market") != "US": errors.append("identity")
    if value.get("window") not in WINDOWS: errors.append("window")
    if value.get("direction") not in {"BULLISH", "BEARISH", "SIDEWAYS", None}: errors.append("direction")
    low, target, high = map(_number, (value.get("forecast_low"), value.get("forecast_target"), value.get("forecast_high")))
    if any(item is not None for item in (low, target, high)) and (None in (low, target, high) or not low <= target <= high): errors.append("forecast_interval")
    if len(value.get("key_reasons") or []) > 4: errors.append("key_reasons")
    if len(value.get("important_news") or []) > 4: errors.append("important_news")
    if value.get("window") == "us_pre_market_2000" and value.get("direction") is None: errors.append("direction_missing")
    if value.get("window") == "us_intraday_2300" and value.get("continuity_state") != "INSUFFICIENT_EVIDENCE" and not value.get("source_snapshot_id"): errors.append("source_lineage")
    if value.get("decision_authority") is not False: errors.append("decision_authority")
    return sorted(set(errors))
