"""Canonical TW 07:00 PM-facing product intelligence projection.

This module is deliberately downstream of prediction and Research/RRE.  It
does not own strategy, scoring, eligibility, action, or execution.  Dashboard
and LINE consume the same projection and may not recompute forecast values.
"""
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any

from app.reports.tw_prediction_explainability import project_tw_prediction_card

SCHEMA_VERSION = "tw_preopen_product_intelligence_v1"
DIRECTIONS = ("BULLISH", "BEARISH", "SIDEWAYS")
LABELS = {
    "BULLISH": ("偏多", "↑"),
    "BEARISH": ("偏空", "↓"),
    "SIDEWAYS": ("盤整", "↔"),
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _hash(value: Any, prefix: str) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return prefix + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _direction(value: str) -> str:
    return {
        "bullish": "BULLISH",
        "bearish": "BEARISH",
        "neutral": "SIDEWAYS",
        "range_bound": "SIDEWAYS",
        "insufficient_evidence": "SIDEWAYS",
        "insufficient_data": "SIDEWAYS",
    }.get(str(value or "").lower(), "")


def _format_price(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _important_news(news: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in news.get("selected_items") or []:
        if not isinstance(item, dict):
            continue
        raw_tier = item.get("source_tier") or item.get("source_class") or 4
        try:
            tier = int(raw_tier)
        except (TypeError, ValueError):
            tier = {"official_primary": 1, "institutional_primary": 2, "reputable_media": 3, "sentiment_only": 4}.get(str(raw_tier).lower(), 4)
        if tier >= 4 or item.get("sentiment_only"):
            continue
        headline = str(item.get("headline") or item.get("title") or "").strip()
        if not headline:
            continue
        summary = str(
            item.get("summary")
            or item.get("materiality_reason")
            or item.get("relevance_reason")
            or "此事件具個股或產業關聯，納入今日情境判斷。"
        ).strip()
        direction = str(item.get("direction") or "unavailable").lower()
        impact = "偏多" if direction == "bullish" else "偏空" if direction == "bearish" else "中性/風險"
        rows.append(
            {
                "evidence_id": item.get("evidence_id") or item.get("news_id") or item.get("id"),
                "headline": headline,
                "summary": summary,
                "expected_impact": impact,
                "direction": direction,
                "source_tier": tier,
                "publisher": item.get("publisher") or item.get("source_name"),
                "published_at": item.get("published_at") or item.get("timestamp"),
                "source_url": item.get("source_url") or item.get("url"),
                "attribution_provenance": {
                    "symbol": symbol,
                    "subject_contract": item.get("subject_contract"),
                    "projection_source": "tw_finalized_news_projection_v1",
                },
            }
        )
    return rows[:3]


def _news_message(news: dict[str, Any], selected: list[dict[str, Any]]) -> str:
    if selected:
        return f"已選出 {len(selected)} 則足以影響今日情境判斷的重要消息。"
    state = str(news.get("state") or news.get("status") or "NO_RELEVANT").upper()
    if state == "RETRIEVAL_FAILED":
        return "新聞來源取得失敗；目前無法判定是否沒有重大消息。"
    if state == "STALE_ONLY":
        return "目前僅取得過期消息，未納入今日判斷。"
    if state == "DISCOVERED_BUT_FILTERED":
        return "有取得消息，但未通過個股相關性、品質或重大性門檻。"
    return "目前未取得足以改變今日判斷的重大消息。"


def project_tw_preopen_product(card: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    """Project a card into the single canonical 07:00 product truth."""
    projected = project_tw_prediction_card(card, "pre_open_0700", strict=strict)
    source_news = deepcopy(card.get("news_evidence") or {})
    source_retrieval_failed = str(source_news.get("state") or source_news.get("status") or source_news.get("reason_code") or "").upper() == "RETRIEVAL_FAILED"
    presentation = projected.get("prediction_presentation_v1") or {}
    snapshot = projected.get("prediction_snapshot_v2") or {}
    point = snapshot.get("point_forecast") if isinstance(snapshot.get("point_forecast"), dict) else {}
    direction = _direction(presentation.get("direction"))
    snapshot_direction = _direction(snapshot.get("direction_forecast"))
    low = _number((presentation.get("today_range") or {}).get("predicted_low"))
    high = _number((presentation.get("today_range") or {}).get("predicted_high"))
    target = _number(point.get("price"))
    errors: list[str] = []
    if direction not in DIRECTIONS:
        errors.append("missing_or_unsupported_today_direction")
    if snapshot_direction not in DIRECTIONS:
        errors.append("missing_or_unsupported_prediction_direction")
    elif snapshot_direction != direction:
        errors.append("same_horizon_direction_conflict")
    if low is None or high is None or low > high:
        errors.append("invalid_prediction_interval")
    if target is None:
        errors.append("missing_prediction_target")
    elif low is not None and high is not None and not (low <= target <= high):
        errors.append("prediction_target_outside_interval")
    if point.get("owner") != "tw_prediction_engine":
        errors.append("renderer_or_non_prediction_owned_target")
    if point.get("is_execution_target") is not False:
        errors.append("prediction_target_execution_alias")
    if point.get("is_support") is not False or point.get("is_resistance") is not False:
        errors.append("prediction_range_support_resistance_alias")
    if snapshot.get("confidence_owner") not in (None, "prediction_model"):
        errors.append("confidence_semantic_aliasing")
    news = projected.get("finalized_tw_news_projection_v1") or {}
    selected_news = _important_news(news, str(projected.get("symbol") or projected.get("stock_id") or ""))
    if len(selected_news) > 3:
        errors.append("primary_news_limit_exceeded")
    for item in selected_news:
        if not (item.get("attribution_provenance") or {}).get("subject_contract"):
            errors.append("selected_news_missing_attribution")
    if errors and strict:
        raise ValueError("|".join(sorted(set(errors))))

    label, arrow = LABELS.get(direction, ("盤整", "↔"))
    symbol = str(projected.get("symbol") or projected.get("stock_id") or "")
    name = str(projected.get("name") or projected.get("stock_name") or "")
    range_text = (
        f"{_format_price(low)}～{_format_price(high)}"
        if low is not None and high is not None
        else "尚未建立"
    )
    target_text = _format_price(target) if target is not None else "尚未建立"
    invalidation = str(
        (presentation.get("scenario_switch") or {}).get("invalidation_condition")
        or (f"跌破 {range_text.split('～')[0]}" if direction == "BULLISH" else f"突破 {range_text.split('～')[-1]}")
    )
    thesis = (
        f"{symbol} {name} 今日以{label}看待，主要預測目標約 {target_text} 元，"
        f"合理波動區間約 {range_text} 元。若{invalidation}，今日{label}情境需重新評估。"
    )
    contract = {
        "schema_version": SCHEMA_VERSION,
        "symbol": symbol,
        "name": name,
        "prediction_id": presentation.get("prediction_id") or projected.get("prediction_id"),
        "horizon": "today",
        "today_direction": direction,
        "direction_label": label,
        "direction_arrow": arrow,
        "direction_strength": str(snapshot.get("direction_strength") or "moderate"),
        "target_price": target,
        "target_provenance": deepcopy(point),
        "predicted_low": low,
        "predicted_high": high,
        "reference_price": _number(snapshot.get("reference_price") or projected.get("current_price")),
        "daily_thesis": thesis,
        "thesis_version": "tw_preopen_daily_thesis_v1",
        "important_news": selected_news,
        "news_state": news.get("state"),
        "news_message": "新聞來源取得失敗，目前無法判定是否存在重大消息。" if source_retrieval_failed and not selected_news else _news_message(news, selected_news),
        "news_diagnostics": {
            "source_funnel": deepcopy(news.get("source_funnel") or {}),
            "reason_code": news.get("reason_code"),
            "retrieval_failed": source_retrieval_failed or str(news.get("state") or news.get("status") or news.get("reason_code") or "").upper() == "RETRIEVAL_FAILED",
        },
        "decision": {
            "action": projected.get("action") or projected.get("decision"),
            "reason": projected.get("do_not_trade_reason") or projected.get("risk_summary"),
            "ownership": "Decision Layer",
        },
        "research_context": {
            "stance": (presentation.get("research_view") or {}).get("stance"),
            "news_conflict_preserved": bool(news.get("bullish_count") and news.get("bearish_count")),
        },
        "confidence": {
            "value": (presentation.get("confidence") or {}).get("score"),
            "owner": "prediction_model",
            "primary_surface": False,
        },
        "technical_indicators_primary_surface": False,
        "support_resistance_alias_prediction_range": False,
        "decision_ownership_preserved": True,
        "validation_errors": sorted(set(errors)),
    }
    contract["thesis_id"] = _hash(
        {"prediction_id": contract["prediction_id"], "direction": direction, "target": target, "range": [low, high]},
        "twthesis_",
    )
    contract["projection_id"] = _hash(contract, "tw0700_")
    result = deepcopy(projected)
    result["tw_preopen_product_intelligence_v1"] = contract
    return result


def portfolio_summary(cards: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [(card.get("tw_preopen_product_intelligence_v1") or {}) for card in cards]
    counts = {direction: sum(row.get("today_direction") == direction for row in rows) for direction in DIRECTIONS}
    priority = [
        {
            "symbol": row.get("symbol"),
            "name": row.get("name"),
            "direction": row.get("today_direction"),
            "direction_label": row.get("direction_label"),
            "target_price": row.get("target_price"),
            "predicted_low": row.get("predicted_low"),
            "predicted_high": row.get("predicted_high"),
        }
        for row in sorted(rows, key=lambda row: (row.get("today_direction") == "SIDEWAYS", row.get("symbol") or ""))[:3]
    ]
    return {"schema_version": "tw_preopen_portfolio_summary_v1", "counts": counts, "priority": priority}


def render_line(cards: list[dict[str, Any]], url: str) -> str:
    lines = ["【Stock AI】07:00 台股盤前", ""]
    for card in cards:
        product = card.get("tw_preopen_product_intelligence_v1") or {}
        if not product:
            continue
        lines.extend(
            [
                f"{product.get('symbol')} {product.get('name')}",
                f"{product.get('direction_label')} {product.get('direction_arrow')}",
                f"目標 {_format_price(product.get('target_price'))}",
                f"區間 {_format_price(product.get('predicted_low'))}～{_format_price(product.get('predicted_high'))}",
            ]
        )
        for item in (product.get("important_news") or [])[:2]:
            lines.append(f"• {item.get('headline')}（{item.get('expected_impact')}）")
        lines.append("")
    lines.extend([url, "僅供研究參考，非交易指令。"])
    return "\n".join(lines)
