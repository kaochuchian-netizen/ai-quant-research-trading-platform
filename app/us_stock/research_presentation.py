"""Canonical PM-facing projection of current US research news.

This module is presentation-only.  It does not score evidence, authorize a
Decision, or modify the immutable institutional research bundle.
"""
from __future__ import annotations

from typing import Any


STATE_LABELS = {
    "AVAILABLE": "當期個股新聞可用",
    "NO_RELEVANT": "有取得資料，但未找到與本標的足夠相關的當期新聞",
    "RETRIEVAL_FAILED": "新聞來源取得失敗",
    "STALE_ONLY": "僅有過期新聞，不納入本批次研究",
    "DISCOVERED_BUT_FILTERED": "有取得新聞，但未通過個股相關性／品質篩選",
    "ADMITTED_NOT_SELECTED": "合格新聞已收錄，本摘要未選用",
    "SELECTED_NOT_RENDERED": "研究已選用，但呈現層異常未顯示",
}

ABSENCE_TO_STATE = {
    "NEWS_RETRIEVAL_FAILED": "RETRIEVAL_FAILED",
    "NO_RELEVANT_NEWS_DISCOVERED": "NO_RELEVANT",
    "NEWS_DISCOVERED_BUT_FILTERED": "DISCOVERED_BUT_FILTERED",
    "NEWS_ADMITTED_NOT_SELECTED": "ADMITTED_NOT_SELECTED",
    "NEWS_SELECTED_NOT_RENDERED": "SELECTED_NOT_RENDERED",
    "STALE_ONLY": "STALE_ONLY",
}


def _bundle(card: dict[str, Any]) -> dict[str, Any]:
    value = card.get("institutional_research")
    return value if isinstance(value, dict) else {}


def _normalize_selected(item: dict[str, Any]) -> dict[str, Any]:
    direction = str(item.get("direction") or "unavailable")
    return {
        "news_id": item.get("news_id"),
        "headline": item.get("headline") or item.get("english_headline"),
        "english_headline": item.get("english_headline") or item.get("headline"),
        "chinese_translation": item.get("chinese_translation"),
        "chinese_summary": item.get("chinese_summary") or item.get("summary"),
        "investment_reading": item.get("investment_reading"),
        "publisher": item.get("publisher") or item.get("source_class"),
        "published_at": item.get("published_at"),
        "source_class": item.get("source_class") or "source_class_unavailable",
        "direction": direction,
        "direction_status": item.get("direction_status") or (
            "NOT_EVALUATED" if direction in {"", "unavailable", "neutral"} else "EVALUATED"
        ),
        "freshness": item.get("freshness"),
        "source_reference": item.get("source_reference"),
        "entity_attribution": item.get("entity_attribution"),
    }


def finalized_current_news_projection(bundle: dict[str, Any]) -> dict[str, Any]:
    """Project the one finalized news truth consumed by every visible surface."""
    intelligence = bundle.get("news_intelligence_v2")
    intelligence = intelligence if isinstance(intelligence, dict) else {}
    projection = bundle.get("research_intelligence_v2")
    projection = projection if isinstance(projection, dict) else {}
    raw_selected = intelligence.get("selected_items")
    if not isinstance(raw_selected, list):
        raw_selected = projection.get("selected_news_evidence")
    selected = [
        _normalize_selected(item) for item in (raw_selected or [])
        if isinstance(item, dict)
        and item.get("freshness") != "stale"
        and item.get("selection_status") not in {"NOT_SELECTED", "REJECTED"}
    ]
    funnel = intelligence.get("evidence_funnel")
    funnel = funnel if isinstance(funnel, dict) else {}
    stages = funnel.get("stages") if isinstance(funnel.get("stages"), dict) else {}
    retrieval = funnel.get("retrieval") if isinstance(funnel.get("retrieval"), dict) else {}
    reasons = funnel.get("rejection_reasons") if isinstance(funnel.get("rejection_reasons"), dict) else {}

    absence = str(funnel.get("absence_state") or "")
    if not absence and str(retrieval.get("status") or "").upper() in {"FAILED", "ERROR"}:
        absence = "NEWS_RETRIEVAL_FAILED"
    if not absence and int(reasons.get("STALE") or 0) > 0 and not any(
        int(value or 0) > 0 for key, value in reasons.items() if key != "STALE"
    ):
        absence = "STALE_ONLY"
    absence = absence or "NO_RELEVANT_NEWS_DISCOVERED"
    if selected and int(stages.get("RENDERED") or 0) > 0:
        state = "AVAILABLE"
    elif str(retrieval.get("status") or "").upper() in {"FAILED", "ERROR"}:
        state = "RETRIEVAL_FAILED"
    elif int(stages.get("RRE_USED") or 0) > 0 and int(stages.get("RENDERED") or 0) == 0:
        state = "SELECTED_NOT_RENDERED"
    elif int(stages.get("ADMITTED") or 0) > 0:
        state = "ADMITTED_NOT_SELECTED"
    elif absence == "STALE_ONLY" and int(reasons.get("STALE") or 0) > 0:
        state = "STALE_ONLY"
    else:
        state = ABSENCE_TO_STATE.get(absence, "NO_RELEVANT")

    label = STATE_LABELS[state]
    top = selected[0] if selected else None
    if top:
        compact = (
            f"當期個股新聞：{len(selected)} 筆｜{top.get('headline') or '未命名事件'}"
            f"（{top.get('publisher') or '來源未標示'}｜{top.get('published_at') or '時間未標示'}"
            f"｜{top.get('source_class')}｜方向 {top.get('direction_status')}）"
        )
    else:
        compact = label
    return {
        "schema_version": "finalized_current_news_projection_v2",
        "state": state,
        "reason_code": absence,
        "state_label": label,
        "selected_count": len(selected),
        "selected_items": selected,
        "primary_item": top,
        "compact_summary": compact,
        "funnel": funnel,
        "source_contract": "institutional_research.news_intelligence_v2.finalized_selection",
        "decision_authority": False,
    }


def current_news_presentation(card: dict[str, Any]) -> dict[str, Any]:
    """Compatibility entry point; it never recomputes from provider inputs."""
    existing = card.get("finalized_current_news_projection_v2")
    if isinstance(existing, dict):
        return existing
    return finalized_current_news_projection(_bundle(card))


def compatibility_news_snippet(projection: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible snippet derived solely from the finalized primary."""
    primary = projection.get("primary_item") if isinstance(projection.get("primary_item"), dict) else {}
    return {
        "english_headline": primary.get("english_headline") or primary.get("headline"),
        "chinese_translation": primary.get("chinese_translation"),
        "chinese_summary": primary.get("chinese_summary"),
        "investment_reading": primary.get("investment_reading"),
        "publisher": primary.get("publisher"),
        "published_at": primary.get("published_at"),
        "source_url": primary.get("source_reference"),
        "direction": primary.get("direction") or "unavailable",
        "canonical_news_id": primary.get("news_id"),
        "canonical_news_state": projection.get("state"),
        "absence_label": None if primary else projection.get("state_label"),
        "compatibility_source": "finalized_current_news_projection_v2",
    }


def compatibility_material_news(projection: dict[str, Any]) -> dict[str, Any]:
    """Legacy material-news surface backed only by finalized selection."""
    return {
        "status": "AVAILABLE" if projection.get("state") == "AVAILABLE" else "MISSING",
        "items": list(projection.get("selected_items") or []),
        "selected_count": int(projection.get("selected_count") or 0),
        "absence_state": projection.get("reason_code"),
        "absence_label": projection.get("state_label"),
        "evidence_funnel": projection.get("funnel") or {},
        "canonical_news_state": projection.get("state"),
        "canonical_news_id": ((projection.get("primary_item") or {}).get("news_id")),
        "compatibility_source": "finalized_current_news_projection_v2",
    }


def apply_finalized_news_surfaces(
    card: dict[str, Any], research: dict[str, Any], bundle: dict[str, Any],
) -> dict[str, Any]:
    """Connect production card/research compatibility fields to one projection."""
    projection = finalized_current_news_projection(bundle)
    material = compatibility_material_news(projection)
    research["finalized_current_news_projection_v2"] = projection
    research["material_news"] = material
    card["finalized_current_news_projection_v2"] = projection
    card["bilingual_news_snippet"] = compatibility_news_snippet(projection)
    sections = card.setdefault("research_sections", {})
    sections["material_news"] = material
    return projection


def validate_finalized_news_projection(value: dict[str, Any]) -> list[str]:
    """Fail closed when state, counts, primary and finalized funnel disagree."""
    errors: list[str] = []
    selected = value.get("selected_items") if isinstance(value.get("selected_items"), list) else []
    funnel = value.get("funnel") if isinstance(value.get("funnel"), dict) else {}
    stages = funnel.get("stages") if isinstance(funnel.get("stages"), dict) else {}
    reasons = funnel.get("rejection_reasons") if isinstance(funnel.get("rejection_reasons"), dict) else {}
    state = value.get("state")
    primary = value.get("primary_item") if isinstance(value.get("primary_item"), dict) else None
    if value.get("schema_version") != "finalized_current_news_projection_v2":
        errors.append("schema")
    if value.get("selected_count") != len(selected):
        errors.append("selected_count")
    if bool(selected) != bool(primary):
        errors.append("primary_presence")
    if selected and primary and selected[0].get("news_id") != primary.get("news_id"):
        errors.append("primary_identity")
    if state == "AVAILABLE" and (not selected or int(stages.get("RENDERED") or 0) <= 0):
        errors.append("available_without_rendered_selection")
    if state == "STALE_ONLY" and int(reasons.get("STALE") or 0) <= 0:
        errors.append("stale_without_stale_evidence")
    if state == "DISCOVERED_BUT_FILTERED" and value.get("reason_code") != "NEWS_DISCOVERED_BUT_FILTERED":
        errors.append("filtered_reason_mismatch")
    return sorted(set(errors))


def validate_news_surface_parity(projection: dict[str, Any], surfaces: list[dict[str, Any]]) -> list[str]:
    """Validate compatibility surfaces against finalized state and primary ID."""
    errors = validate_finalized_news_projection(projection)
    canonical_id = ((projection.get("primary_item") or {}).get("news_id"))
    for index, surface in enumerate(surfaces):
        if surface.get("compatibility_source") != "finalized_current_news_projection_v2":
            errors.append(f"surface_{index}:source")
        if surface.get("canonical_news_state") != projection.get("state"):
            errors.append(f"surface_{index}:state")
        if surface.get("canonical_news_id") != canonical_id:
            errors.append(f"surface_{index}:primary")
    return sorted(set(errors))


def research_review_lines(card: dict[str, Any]) -> list[str]:
    """Material review text shared with Email and capture QA."""
    news = current_news_presentation(card)
    bundle = _bundle(card)
    projection = bundle.get("research_intelligence_v2")
    projection = projection if isinstance(projection, dict) else {}
    hypothesis = projection.get("hypothesis")
    hypothesis = hypothesis if isinstance(hypothesis, dict) else {}
    return [
        f"即時新聞：{news['compact_summary']}",
        f"研究假設：{hypothesis.get('statement') or '尚未建立'}",
        f"確認條件：{hypothesis.get('trigger') or '尚未建立'}",
        f"失效條件：{hypothesis.get('invalidation') or '尚未建立'}",
        f"主要風險：{projection.get('primary_risk') or '尚未建立'}",
    ]
