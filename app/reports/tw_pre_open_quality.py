"""Canonical TW 07:00 evidence, coverage and confidence contracts.

Pure helpers only: no network, filesystem writes, notifications or trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
from typing import Any

REQUIRED_HISTORY_BARS = 20
NEWS_LOOKBACK_HOURS = 72
NEWS_SOURCE_ATTEMPTS = ("MOPS", "TWSE", "COMPANY_IR", "GENERAL_FINANCIAL_MEDIA")
PUBLIC_REASON = {
    "INSUFFICIENT_HISTORY": "歷史資料不足最低需求",
    "TREND_UNAVAILABLE": "無法確認趨勢",
    "RR_BELOW_THRESHOLD": "報酬風險比低於最低門檻",
    "CONFIDENCE_DOWNGRADED": "因資料覆蓋不足，信心下調",
    "GAP_UNAVAILABLE": "Gap 尚未取得",
    "EVENT_RISK_UNAVAILABLE": "事件風險尚未取得",
    "CHIP_UNAVAILABLE": "籌碼資料尚未取得",
    "NEWS_UNAVAILABLE": "新聞證據尚未取得",
}


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def public_reason(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if text in PUBLIC_REASON:
        return PUBLIC_REASON[text]
    if "limited history below 20 bars" in lowered:
        return PUBLIC_REASON["INSUFFICIENT_HISTORY"]
    if "trend confirmation unavailable" in lowered:
        return PUBLIC_REASON["TREND_UNAVAILABLE"]
    if "reward/risk below" in lowered:
        return PUBLIC_REASON["RR_BELOW_THRESHOLD"]
    if "confidence downgraded" in lowered:
        return PUBLIC_REASON["CONFIDENCE_DOWNGRADED"]
    if text in {"setup not confirmed", "no actionable tactical setup"}:
        return "交易條件尚未確認"
    return text


def public_reasons(value: Any) -> str:
    parts = [item.strip() for item in str(value or "").replace("；", ";").split(";") if item.strip()]
    return "；".join(dict.fromkeys(public_reason(item) for item in parts))


def technical_contract(tactical: dict[str, Any]) -> dict[str, Any]:
    factors = tactical.get("technical_factors") if isinstance(tactical.get("technical_factors"), dict) else {}
    bars = int(factors.get("history_days") or 0)
    latest_date = str(factors.get("history_end") or factors.get("latest_date") or "")[:10]
    expected_date = str(tactical.get("effective_trading_date") or tactical.get("trading_date") or "")[:10]
    age_days = None
    if latest_date and expected_date:
        try:
            age_days = (datetime.fromisoformat(expected_date).date() - datetime.fromisoformat(latest_date).date()).days
        except ValueError:
            age_days = None
    freshness = (
        "fresh" if latest_date and (not expected_date or age_days is not None and 0 <= age_days <= 7)
        else "stale" if latest_date and expected_date else "unavailable"
    )
    eligible = bars >= REQUIRED_HISTORY_BARS and factors.get("ma20") is not None and freshness != "stale"
    raw_direction = str(tactical.get("direction") or "unavailable")
    direction = raw_direction if eligible and raw_direction in {"bullish", "neutral", "bearish"} else "unavailable"
    reasons = [] if eligible else ["INSUFFICIENT_HISTORY", "TREND_UNAVAILABLE"]
    return {
        "price_data_available": bars > 0,
        "history_bars": bars,
        "required_bars": REQUIRED_HISTORY_BARS,
        "history_start": factors.get("history_start"),
        "history_end": factors.get("history_end") or factors.get("latest_date"),
        "source": factors.get("source") or "canonical_historical_csv",
        "source_timestamp": factors.get("latest_date"),
        "freshness": freshness,
        "freshness_context": {"latest_date": latest_date or None, "canonical_trading_date": expected_date or None, "calendar_age_days": age_days, "maximum_calendar_age_days": 7},
        "calculation_method": "tw_daily_ohlcv_features_v2",
        "feature_provenance": {
            "period_end": factors.get("history_end") or factors.get("latest_date"),
            "bars": bars, "required_bars": REQUIRED_HISTORY_BARS,
            "source": factors.get("source") or "canonical_historical_csv",
        },
        "analysis_eligible": eligible,
        "direction": direction,
        "reason_codes": reasons,
        "history_fallback": tactical.get("history_fallback") or {
            "used": False, "primary_source": "shioaji_kbars", "fallback_source": None,
            "reason": None, "bars_before": bars, "bars_after": bars,
        },
    }


def _news_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("items", "articles", "news"):
            if key in value and isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, dict)]
        return [value]
    return []


def _source_tier(item: dict[str, Any]) -> int:
    source = str(item.get("publisher") or item.get("source") or "").lower()
    if item.get("official_source") is True or any(key in source for key in ("mops", "twse", "tpex", "公司", "ir")):
        return 1
    if any(key in source for key in ("協會", "研究", "產業")):
        return 2
    if source:
        return 3
    return 4


def _news_preference(item: dict[str, Any]) -> tuple[int, float, str]:
    published = _parse_time(item.get("published_at"))
    newest_first = -(published.timestamp()) if published else 0.0
    return int(item.get("source_tier") or 4), newest_first, str(item.get("headline") or "")


def canonical_tw_event_identity(item: dict[str, Any]) -> str:
    """Publisher-independent event identity; URLs remain provenance only."""
    headline = str(item.get("headline") or item.get("title") or "").lower()
    headline = re.sub(r"\s+", " ", headline)
    headline = re.sub(r"^(?:轉載|快訊|更新)\s*[：:]\s*", "", headline)
    publishers = r"reuters|bloomberg|中央社|經濟日報|工商時報|yahoo|google news"
    headline = re.sub(rf"\s*[-｜|]\s*(?:{publishers})\s*$", "", headline)
    headline = re.sub(rf"^(?:{publishers})\s*[-｜|]\s*", "", headline)
    subject = str(item.get("primary_subject") or item.get("symbol") or item.get("stock_id") or "unattributed")
    bucket = str(item.get("published_at") or item.get("published") or item.get("date") or "")[:10]
    facts = item.get("material_facts") if isinstance(item.get("material_facts"), list) else []
    raw = json.dumps([headline.strip(" -｜|"), item.get("event_type") or item.get("event_family"), subject, bucket, sorted(map(str, facts))], ensure_ascii=False, sort_keys=True)
    return "tw_event_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def news_contract(raw_news: Any, *, generated_at: str | None = None) -> dict[str, Any]:
    admitted = []
    raw_items = _news_items(raw_news)
    rejection_reasons: dict[str, int] = {}
    candidate_records: list[dict[str, Any]] = []
    def reject(code: str, candidate: dict[str, Any] | None = None) -> None:
        rejection_reasons[code] = rejection_reasons.get(code, 0) + 1
        if candidate is not None:
            candidate["admission_status"] = "REJECTED"
            candidate["rejection_reason"] = code
            candidate_records.append(candidate)
    reference = _parse_time(generated_at)
    normalized_count = 0
    attributed_count = 0
    relevant_count = 0
    material_count = 0
    quality_count = 0
    fresh_count = 0
    for item in raw_items:
        headline = item.get("headline") or item.get("title")
        publisher = item.get("publisher") or item.get("source")
        published = item.get("published_at") or item.get("published") or item.get("timestamp") or item.get("date")
        source_url = item.get("source_url") or item.get("url") or item.get("link") or item.get("source_id")
        candidate = {
            "candidate_id": item.get("news_id") or "candidate_" + hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20],
            "headline": headline, "publisher": publisher, "published_at": published,
            "source_reference": source_url, "fetched_at": item.get("fetched_at") or generated_at,
            "canonical_event_identity": canonical_tw_event_identity(item),
            "primary_subject": item.get("primary_subject"), "relationship_type": item.get("relationship_type") or "unattributed",
            "related_symbols": item.get("related_symbols") or [], "event_type": item.get("event_type"),
            "materiality": item.get("materiality") or "UNKNOWN", "relevance": item.get("relevance") or "UNKNOWN",
            "research_role": str(item.get("research_role") or item.get("contextual_role") or "NOT_USED").upper(),
            "counted_in_synthesis": bool(item.get("counted_in_synthesis")), "evidence_id": item.get("evidence_id"),
        }
        if not all(_present(value) for value in (headline, publisher, published, source_url)):
            reject("INSUFFICIENT_PROVENANCE", candidate)
            continue
        normalized_count += 1
        relationship = str(item.get("relationship_type") or "").lower()
        contextual_role = str(item.get("contextual_role") or item.get("research_role") or "").upper()
        symbol_attributed = item.get("symbol_attributed") is True or relationship in {"primary", "customer", "supplier", "competitor", "sector", "macro", "regulatory", "geopolitical"}
        if not symbol_attributed:
            reject("SYMBOL_ATTRIBUTION_FAILED", candidate)
            continue
        attributed_count += 1
        relevance = str(item.get("relevance") or "unknown").lower()
        if relevance not in {"medium", "high", "critical"}:
            reject("RELEVANCE_NOT_EVALUATED" if relevance == "unknown" else "LOW_RELEVANCE", candidate)
            continue
        relevant_count += 1
        materiality = str(item.get("materiality") or "unknown").lower()
        if materiality not in {"medium", "high", "critical"}:
            reject("MATERIALITY_NOT_EVALUATED" if materiality == "unknown" else "LOW_MATERIALITY", candidate)
            continue
        material_count += 1
        tier = _source_tier(item)
        if tier > 3:
            reject("LOW_SOURCE_QUALITY", candidate)
            continue
        quality_count += 1
        published_time = _parse_time(published)
        age_hours = None if not reference or not published_time else max(0.0, (reference - published_time).total_seconds() / 3600)
        freshness = "fresh" if age_hours is not None and age_hours <= NEWS_LOOKBACK_HOURS else "stale" if age_hours is not None else "unknown"
        if freshness == "stale":
            reject("STALE", candidate)
            continue
        if freshness != "fresh":
            reject("OUTSIDE_WINDOW", candidate)
            continue
        fresh_count += 1
        direction = str(item.get("direction") or "unavailable").lower()
        if direction not in {"bullish", "neutral", "bearish", "unavailable"}:
            direction = "unavailable"
        if relationship in {"macro", "sector", "regulatory", "geopolitical"} or contextual_role in {"CONTEXT", "EXPLAIN", "CONTEXTUALIZE"}:
            direction = "unavailable"
            contextual_role = contextual_role or "CONTEXT"
        canonical_event_id = item.get("canonical_event_id") or item.get("event_cluster_id") or candidate["canonical_event_identity"]
        admitted_item = {
            "headline": str(headline), "publisher": str(publisher), "published_at": str(published),
            "source_url": str(source_url), "source_tier": tier,
            "source_quality": {1: "high", 2: "medium_high", 3: "medium", 4: "low"}[tier],
            "direction": direction,
            "direction_status": "QUALIFIED" if direction in {"bullish", "neutral", "bearish"} else "NOT_EVALUATED",
            "relevance": relevance,
            "materiality": materiality,
            "official_source": tier == 1,
            "canonical_event_id": str(canonical_event_id) if canonical_event_id else None,
            "dedupe_key": str(canonical_event_id or item.get("dedupe_key") or source_url),
            "freshness": freshness, "age_hours": None if age_hours is None else round(age_hours, 2),
            "relationship_type": relationship or "primary", "contextual_role": contextual_role or None,
        }
        admitted.append(admitted_item)
        candidate.update({"source_tier": tier, "source_quality": admitted_item["source_quality"], "freshness": freshness,
                          "admission_status": "ADMITTED", "rejection_reason": None,
                          "canonical_event_identity": canonical_event_id, "relationship_type": relationship or "primary",
                          "research_role": contextual_role or candidate["research_role"]})
        candidate_records.append(candidate)
    before_dedupe = len(admitted)
    unique: dict[str, dict[str, Any]] = {}
    for item in admitted:
        incumbent = unique.get(item["dedupe_key"])
        if incumbent is None or _news_preference(item) < _news_preference(incumbent):
            unique[item["dedupe_key"]] = item
    admitted = list(unique.values())
    duplicate_count = before_dedupe - len(admitted)
    if duplicate_count:
        rejection_reasons["DUPLICATE"] = duplicate_count
    admitted.sort(key=_news_preference)
    usable = list(admitted)
    primary = usable[0] if usable else None
    quality = primary["source_quality"] if primary else "not_applicable"
    if primary:
        base = {"high": 82, "medium_high": 70, "medium": 58, "low": 35}[quality]
        confidence = {
            "score": base, "level": "high" if base >= 75 else "medium" if base >= 50 else "low",
            "components": {"source_quality": base, "freshness": 80, "cross_source_consistency": 70 if len(admitted) > 1 else 50, "direct_relevance": 90, "materiality": 60, "official_confirmation": 100 if primary["official_source"] else 0},
            "reason_codes": [] if primary["official_source"] else ["NO_OFFICIAL_CONFIRMATION"],
        }
    else:
        confidence = {"score": None, "level": "not_applicable", "components": {}, "reason_codes": ["NO_ADMITTED_NEWS_EVIDENCE"]}
    supplied_retrieval = raw_news.get("retrieval") if isinstance(raw_news, dict) and isinstance(raw_news.get("retrieval"), dict) else {}
    failure = str(supplied_retrieval.get("failure_reason") or ("NO_RESULT" if not raw_items else "FILTERED"))
    attempted = list(supplied_retrieval.get("sources_attempted") or ["UNSPECIFIED_UPSTREAM"])
    configured_failed = list(supplied_retrieval.get("sources_failed") or [])
    succeeded = list(supplied_retrieval.get("sources_succeeded") or [])
    discovered = max(len(raw_items), int(supplied_retrieval.get("result_count_discovered") or supplied_retrieval.get("result_count_raw") or 0))
    retrieved = len(raw_items)
    funnel = {
        "schema_version": "tw_research_evidence_funnel_v1",
        "count_semantics": "EXACT",
        "stages": {
            "DISCOVERED": discovered, "RETRIEVED": retrieved,
            "NORMALIZED": normalized_count, "SYMBOL_ATTRIBUTED": attributed_count,
            "RELEVANT": relevant_count, "MATERIAL": material_count,
            "QUALITY_QUALIFIED": quality_count, "FRESH": fresh_count,
            "DEDUPLICATED": len(admitted), "ADMITTED": len(usable),
            "RRE_USED": 0, "RENDERED": 0,
        },
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
        "candidate_records": candidate_records[:64],
    }
    absence_state = (
        "NEWS_SELECTED_AND_RENDERED" if supplied_retrieval.get("rendered_count") else
        "NEWS_ADMITTED_NOT_SELECTED" if usable else
        "NEWS_RETRIEVAL_FAILED" if failure in {"RETRIEVAL_FAILED", "TIMEOUT", "UPSTREAM_ERROR", "PARSER_ERROR"} else
        "STALE_ONLY" if raw_items and rejection_reasons.get("STALE") == len(raw_items) else
        "NEWS_DISCOVERED_BUT_FILTERED" if discovered else
        "NO_RELEVANT_NEWS_DISCOVERED"
    )
    return {
        "status": "available" if primary else "partial" if admitted else "unavailable", "evidence": admitted, "primary_evidence": primary,
        "source_quality": quality, "confidence": confidence,
        "evidence_funnel": funnel, "absence_state": absence_state,
        "retrieval": {
            "lookback_hours": int(supplied_retrieval.get("lookback_hours") or NEWS_LOOKBACK_HOURS), "sources_attempted": attempted,
            "sources_succeeded": succeeded,
            "sources_failed": configured_failed,
            "query_started_at": supplied_retrieval.get("query_started_at") or generated_at, "query_completed_at": supplied_retrieval.get("query_completed_at") or generated_at,
            "result_count_raw": len(raw_items), "result_count_deduped": len(admitted), "result_count_admitted": len(usable),
            "failure_reason": None if usable else "OUTSIDE_LOOKBACK" if admitted and all(item["freshness"] == "stale" for item in admitted) else "NO_RELIABLE_NEWS" if admitted else failure,
        },
    }


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(str(value))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def data_gaps(technical: dict[str, Any], card: dict[str, Any]) -> list[str]:
    gaps = list(technical.get("reason_codes") or [])
    if str(card.get("news_status") or "") != "available" or not card.get("news_items"): gaps.append("NEWS_UNAVAILABLE")
    if str(card.get("chip_summary") or "") in {"", "unavailable", "尚未取得", "資料尚未取得"}: gaps.append("CHIP_UNAVAILABLE")
    if str(card.get("gap_risk") or "") not in {"low", "medium", "high"}: gaps.append("GAP_UNAVAILABLE")
    if str(card.get("event_risk") or "") not in {"low", "medium", "high"}: gaps.append("EVENT_RISK_UNAVAILABLE")
    return list(dict.fromkeys(gaps))


def market_confidence(coverage: dict[str, dict[str, int]], total: int) -> dict[str, Any]:
    total = max(total, 1)
    components = {
        "technical": {"score": round(100 * coverage["history_sufficient"]["available"] / total), "weight": .35},
        "overnight_adr": {"score": round(100 * coverage["overnight"]["available"] / total), "weight": .15},
        "chip": {"score": round(100 * coverage["chip"]["available"] / total), "weight": .20},
        "news": {"score": round(100 * coverage["news"]["available"] / total), "weight": .15},
        "gap": {"score": round(100 * coverage["gap"]["available"] / total), "weight": .10},
        "event_risk": {"score": round(100 * coverage["event_risk"]["available"] / total), "weight": .05},
    }
    score = round(sum(item["score"] * item["weight"] for item in components.values()))
    reasons = [name for name, ok in (
        ("TECH_HISTORY_INSUFFICIENT", coverage["history_sufficient"]["available"] == total),
        ("CHIP_UNAVAILABLE", coverage["chip"]["available"] == total),
        ("NEWS_COVERAGE_LOW", coverage["news"]["available"] == total),
        ("GAP_UNAVAILABLE", coverage["gap"]["available"] == total),
        ("EVENT_RISK_UNAVAILABLE", coverage["event_risk"]["available"] == total),
    ) if not ok]
    return {"score": score, "level": "high" if score >= 75 else "medium" if score >= 50 else "low", "components": components, "reason_codes": reasons}
