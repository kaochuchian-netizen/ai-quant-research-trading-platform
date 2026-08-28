"""Presentation-only summaries for the canonical TW four-window lifecycle."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.reports.tw_prediction_explainability import project_tw_prediction_card
from app.reports.tw_preopen_product_intelligence import project_tw_preopen_product

SCHEMA_VERSION = "tw_human_decision_summary_v1"
WINDOWS = {"pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"}
HYPOTHESIS_MAP = {
    "on_track": "CONFIRMED", "bullish_breakout": "CONFIRMED",
    "bearish_breakdown": "INVALIDATED", "partial_deviation": "WEAKENED",
    "invalidated": "INVALIDATED", "insufficient_data": "INSUFFICIENT_EVIDENCE",
}


def _number(value: Any) -> float | None:
    try:
        return round(float(value), 6) if value is not None else None
    except (TypeError, ValueError):
        return None


def _identity(prefix: str, value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _forecast(card: dict[str, Any], window: str) -> dict[str, Any]:
    projected = project_tw_prediction_card(card, window, strict=False)["prediction_presentation_v1"]
    interval = projected.get("today_range") or {}
    direction = str(projected.get("direction") or "").lower()
    direction = {"bullish": "BULLISH", "bearish": "BEARISH", "neutral": "SIDEWAYS", "range_bound": "SIDEWAYS"}.get(direction)
    low, high = _number(interval.get("predicted_low")), _number(interval.get("predicted_high"))
    snapshot = card.get("prediction_snapshot_v2") if isinstance(card.get("prediction_snapshot_v2"), dict) else {}
    point = snapshot.get("point_forecast") if isinstance(snapshot.get("point_forecast"), dict) else {}
    target = _number(point.get("price")) if point.get("owner") == "tw_prediction_engine" and point.get("is_execution_target") is False else None
    return {"projected": projected, "direction": direction, "low": low, "high": high, "target": target}


def _evidence_ids(card: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in card.get("evidence") or card.get("research_evidence") or []:
        if isinstance(item, dict) and item.get("evidence_id"):
            values.append(str(item["evidence_id"]))
    news = card.get("finalized_tw_news_projection_v1") or card.get("finalized_news_projection") or {}
    for item in news.get("selected_items") or []:
        if isinstance(item, dict) and (item.get("evidence_id") or item.get("news_id")):
            values.append(str(item.get("evidence_id") or item.get("news_id")))
    return list(dict.fromkeys(values))


def _important_news(card: dict[str, Any]) -> list[dict[str, Any]]:
    product = card.get("tw_preopen_product_intelligence_v1") or {}
    items = product.get("important_news") if isinstance(product, dict) else []
    if not items:
        finalized = card.get("finalized_tw_news_projection_v1") or card.get("finalized_news_projection") or {}
        items = finalized.get("selected_items") if isinstance(finalized, dict) else []
    output = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        output.append({
            "news_id": item.get("news_id"), "news_event_id": item.get("canonical_event_identity") or item.get("canonical_event_id"),
            "headline": item.get("headline") or item.get("title"), "publisher": item.get("publisher") or item.get("source_name") or "原始來源未解析",
            "published_at": item.get("published_at"), "role": str(item.get("research_role") or item.get("role") or "CONTEXT").upper(),
            "impact_summary": item.get("impact_summary") or item.get("summary") or item.get("expected_impact") or "提供當日研究脈絡，不單獨建立公司方向。",
        })
    return output[:4]


def _base(card: dict[str, Any], window: str) -> dict[str, Any]:
    forecast = _forecast(card, window)
    projected = forecast["projected"]
    research = projected.get("research_view") or {}
    tactical = projected.get("daily_tactical") or {}
    reasons = [str(value) for value in card.get("key_reasons") or [] if value][:4]
    if not reasons:
        reasons = [str(value) for value in (card.get("decision_reasons") or card.get("reasons") or []) if value][:4]
    return {
        "schema_version": SCHEMA_VERSION, "market": "TW", "window": window,
        "trading_date": card.get("trading_date") or card.get("effective_trading_date"),
        "symbol": str(card.get("symbol") or card.get("stock_id") or "").zfill(4),
        "company": card.get("stock_name") or card.get("name"), "direction": forecast["direction"],
        "confidence": projected.get("confidence", {}).get("score"), "forecast_target": forecast["target"],
        "forecast_low": forecast["low"], "forecast_high": forecast["high"],
        "research_stance": research.get("stance"), "daily_tactical_stance": tactical.get("direction") or tactical.get("action"),
        "key_reasons": reasons, "main_risk": card.get("main_risk") or card.get("closing_risk") or projected.get("scenario_switch", {}).get("invalidation_condition"),
        "important_news": _important_news(card), "origin_prediction_identity": projected.get("prediction_id"),
        "current_snapshot_identity": card.get("current_snapshot_id") or card.get("source_snapshot_id"),
        "new_evidence_identity": [], "inherited_evidence_identity": [], "hypothesis_state": None,
        "evaluation_state": None, "decision_authority": False,
    }


def build_tw_human_summary(card: dict[str, Any], window: str) -> dict[str, Any]:
    if window not in WINDOWS:
        raise ValueError("UNSUPPORTED_TW_WINDOW")
    if window == "pre_open_0700" and not isinstance(card.get("tw_preopen_product_intelligence_v1"), dict):
        try:
            card = dict(card)
            card = project_tw_preopen_product(card, strict=False)
        except (KeyError, TypeError, ValueError):
            pass
    result = _base(card, window)
    all_evidence = _evidence_ids(card)
    if window == "pre_open_0700":
        product = card.get("tw_preopen_product_intelligence_v1") or {}
        result.update({
            "direction": product.get("today_direction") or result["direction"],
            "forecast_target": _number(product.get("target_price")) if _number(product.get("target_price")) is not None else result["forecast_target"],
            "forecast_low": _number(product.get("predicted_low")) if _number(product.get("predicted_low")) is not None else result["forecast_low"],
            "forecast_high": _number(product.get("predicted_high")) if _number(product.get("predicted_high")) is not None else result["forecast_high"],
            "short_judgment": product.get("daily_thesis"), "hypothesis_state": "ORIGINATED",
            "evaluation_state": "PENDING_INTRADAY", "new_evidence_identity": all_evidence,
        })
    elif window in {"intraday_1305", "pre_close_1335"}:
        progress = _forecast(card, window)["projected"].get("intraday_prediction_status") or {}
        prior = card.get("prior_card") if isinstance(card.get("prior_card"), dict) else {}
        prior_ids = set(_evidence_ids(prior))
        current_ids = set(all_evidence)
        current = _number(progress.get("current_price") or card.get("current_price") or card.get("price"))
        low, high, target = result["forecast_low"], result["forecast_high"], result["forecast_target"]
        range_position = "INSUFFICIENT_DATA"
        if None not in (low, high, current):
            range_position = "BELOW_RANGE" if current < low else "ABOVE_RANGE" if current > high else "WITHIN_RANGE"
        reference = _number(card.get("reference_price") or card.get("previous_close"))
        target_progress = None if None in (reference, target, current) or target == reference else round((current - reference) / (target - reference) * 100, 2)
        result.update({
            "current_price": current, "current_high": _number(card.get("intraday_high") or card.get("current_high")),
            "current_low": _number(card.get("intraday_low") or card.get("current_low")), "range_position": range_position,
            "target_progress_pct": target_progress, "tactical_trigger_state": card.get("entry_trigger_state") or card.get("trigger_status"),
            "hypothesis_state": HYPOTHESIS_MAP.get(str(progress.get("status") or "insufficient_data"), "STILL_VALID"),
            "new_evidence_identity": sorted(current_ids - prior_ids), "inherited_evidence_identity": sorted(current_ids & prior_ids),
            "parent_snapshot_identity": card.get("parent_source_snapshot_id") or prior.get("source_snapshot_id"),
            "baseline_window": "pre_open_0700" if window == "intraday_1305" else "intraday_1305",
            "evaluation_state": "INTRADAY_OBSERVED" if window == "intraday_1305" else "PRE_CLOSE_OBSERVED",
            "closing_risk": card.get("closing_risk") or result.get("main_risk") if window == "pre_close_1335" else None,
        })
    else:
        review = card.get("review_snapshot") if isinstance(card.get("review_snapshot"), dict) else card
        actual_low = _number(card.get("actual_low") or (review.get("actual_range") or {}).get("low"))
        actual_high = _number(card.get("actual_high") or (review.get("actual_range") or {}).get("high"))
        actual_close = _number(card.get("actual_close"))
        low, high, target = result["forecast_low"], result["forecast_high"], result["forecast_target"]
        midpoint = None if None in (low, high) else (low + high) / 2
        result.update({
            "actual_low": actual_low, "actual_high": actual_high, "actual_close": actual_close,
            "direction_result": "HIT" if card.get("direction_hit") is True else "MISS" if card.get("direction_hit") is False else None,
            "range_result": card.get("prediction_range_result") or review.get("prediction_range_result"),
            "forecast_errors": {
                "low": None if None in (low, actual_low) else round(actual_low - low, 6),
                "high": None if None in (high, actual_high) else round(actual_high - high, 6),
                "midpoint": None if None in (midpoint, actual_close) else round(actual_close - midpoint, 6),
            },
            "mfe": card.get("mfe"), "mae": card.get("mae"),
            "tactical_outcome": card.get("trade_outcome") or review.get("trade_outcome"),
            "hypothesis_outcome": card.get("hypothesis_outcome") or card.get("prediction_range_result"),
            "major_evidence_lesson": card.get("major_evidence_lesson") or "依預測、實際行情與已保存證據完成檢討；不自動調整權重。",
            "error_attribution": card.get("prediction_explainability"),
            "next_session_carry_forward": card.get("next_session_carry_forward") or card.get("tomorrow_watch"),
            "hypothesis_state": "EVALUATED", "evaluation_state": "POST_CLOSE_REVIEWED",
            "evaluation_identity": (card.get("prediction_evaluation_v2") or {}).get("evaluation_identity") or _identity("eval_", [result["symbol"], result["trading_date"], actual_low, actual_high, actual_close]),
            "inherited_evidence_identity": all_evidence,
        })
    return result


def validate_tw_human_summary(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("schema_version") != SCHEMA_VERSION or value.get("market") != "TW": errors.append("identity")
    if value.get("window") not in WINDOWS: errors.append("window")
    if value.get("direction") not in {"BULLISH", "BEARISH", "SIDEWAYS", None}: errors.append("direction")
    low, target, high = map(_number, (value.get("forecast_low"), value.get("forecast_target"), value.get("forecast_high")))
    if any(item is not None for item in (low, target, high)) and (None in (low, target, high) or not low <= target <= high): errors.append("forecast_interval")
    if len(value.get("key_reasons") or []) > 4: errors.append("key_reasons")
    if len(value.get("important_news") or []) > 4: errors.append("important_news")
    if value.get("window") in {"intraday_1305", "pre_close_1335"} and value.get("hypothesis_state") != "INSUFFICIENT_EVIDENCE" and not value.get("origin_prediction_identity"): errors.append("source_lineage")
    if value.get("window") == "pre_close_1335" and value.get("current_snapshot_identity") and value.get("current_snapshot_identity") == value.get("parent_snapshot_identity"): errors.append("stale_snapshot")
    if value.get("decision_authority") is not False: errors.append("decision_authority")
    return sorted(set(errors))
