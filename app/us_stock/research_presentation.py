"""Canonical PM-facing projection of current US research news.

This module is presentation-only.  It does not score evidence, authorize a
Decision, or modify the immutable institutional research bundle.
"""
from __future__ import annotations

from typing import Any


STATE_LABELS = {
    "AVAILABLE": "當期個股新聞可用",
    "NO_RELEVANT": "未發現相關即時新聞",
    "RETRIEVAL_FAILED": "新聞來源取得失敗",
    "STALE_ONLY": "僅有過期新聞，不納入本批次研究",
    "ADMITTED_NOT_SELECTED": "合格新聞已收錄，本摘要未選用",
    "SELECTED_NOT_RENDERED": "研究已選用，但尚未呈現",
}


def _bundle(card: dict[str, Any]) -> dict[str, Any]:
    value = card.get("institutional_research")
    return value if isinstance(value, dict) else {}


def _normalize_selected(item: dict[str, Any]) -> dict[str, Any]:
    direction = str(item.get("direction") or "unavailable")
    return {
        "headline": item.get("headline"),
        "publisher": item.get("publisher") or item.get("source_class"),
        "published_at": item.get("published_at"),
        "source_class": item.get("source_class") or "source_class_unavailable",
        "direction": direction,
        "direction_status": item.get("direction_status") or (
            "NOT_EVALUATED" if direction in {"", "unavailable", "neutral"} else "EVALUATED"
        ),
        "freshness": item.get("freshness"),
        "source_reference": item.get("source_reference"),
    }


def current_news_presentation(card: dict[str, Any]) -> dict[str, Any]:
    """Return one truthful news state shared by Dashboard and Email."""
    bundle = _bundle(card)
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

    if selected:
        state = "AVAILABLE"
    elif str(retrieval.get("status") or "").upper() in {"FAILED", "ERROR"}:
        state = "RETRIEVAL_FAILED"
    elif int(stages.get("RRE_USED") or 0) > 0 and int(stages.get("RENDERED") or 0) == 0:
        state = "SELECTED_NOT_RENDERED"
    elif int(stages.get("ADMITTED") or 0) > 0:
        state = "ADMITTED_NOT_SELECTED"
    elif int(reasons.get("STALE") or 0) > 0 or (
        int(stages.get("NORMALIZED") or 0) > 0 and int(stages.get("FRESH") or 0) == 0
    ):
        state = "STALE_ONLY"
    else:
        state = "NO_RELEVANT"

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
        "schema_version": "us_current_news_presentation_v1",
        "state": state,
        "state_label": label,
        "selected_count": len(selected),
        "selected_items": selected,
        "compact_summary": compact,
        "funnel": funnel,
        "source_contract": "institutional_research.news_intelligence_v2",
        "decision_authority": False,
    }


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
