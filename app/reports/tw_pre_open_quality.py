"""Canonical TW 07:00 evidence, coverage and confidence contracts.

Pure helpers only: no network, filesystem writes, notifications or trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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
    eligible = bars >= REQUIRED_HISTORY_BARS and factors.get("ma20") is not None
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
        "freshness": "fresh" if factors.get("latest_date") else "unavailable",
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
        nested = value.get("items") or value.get("articles") or value.get("news")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
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


def news_contract(raw_news: Any, *, generated_at: str | None = None) -> dict[str, Any]:
    admitted = []
    reference = _parse_time(generated_at)
    for item in _news_items(raw_news):
        headline = item.get("headline") or item.get("title")
        publisher = item.get("publisher") or item.get("source")
        published = item.get("published_at") or item.get("published") or item.get("timestamp") or item.get("date")
        source_url = item.get("source_url") or item.get("url") or item.get("link") or item.get("source_id")
        if not all(_present(value) for value in (headline, publisher, published, source_url)):
            continue
        tier = _source_tier(item)
        published_time = _parse_time(published)
        age_hours = None if not reference or not published_time else max(0.0, (reference - published_time).total_seconds() / 3600)
        freshness = "fresh" if age_hours is not None and age_hours <= NEWS_LOOKBACK_HOURS else "stale" if age_hours is not None else "unknown"
        admitted.append({
            "headline": str(headline), "publisher": str(publisher), "published_at": str(published),
            "source_url": str(source_url), "source_tier": tier,
            "source_quality": {1: "high", 2: "medium_high", 3: "medium", 4: "low"}[tier],
            "direction": str(item.get("direction") or "unavailable"),
            "relevance": str(item.get("relevance") or "medium"),
            "materiality": str(item.get("materiality") or "medium"),
            "official_source": tier == 1,
            "dedupe_key": str(item.get("dedupe_key") or source_url),
            "freshness": freshness, "age_hours": None if age_hours is None else round(age_hours, 2),
        })
    unique = {item["dedupe_key"]: item for item in admitted}
    admitted = list(unique.values())
    admitted.sort(key=lambda item: (item["source_tier"], item["freshness"] == "stale", item["published_at"], item["headline"]))
    usable = [item for item in admitted if item["freshness"] != "stale" and item["direction"] in {"bullish", "neutral", "bearish"}]
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
    failure = str(supplied_retrieval.get("failure_reason") or ("NO_RESULT" if not _present(raw_news) else "LOW_QUALITY_ONLY"))
    attempted = list(supplied_retrieval.get("sources_attempted") or ["UNSPECIFIED_UPSTREAM"])
    configured_failed = list(supplied_retrieval.get("sources_failed") or [])
    succeeded = list(supplied_retrieval.get("sources_succeeded") or [])
    return {
        "status": "available" if primary else "partial" if admitted else "unavailable", "evidence": admitted, "primary_evidence": primary,
        "source_quality": quality, "confidence": confidence,
        "retrieval": {
            "lookback_hours": int(supplied_retrieval.get("lookback_hours") or NEWS_LOOKBACK_HOURS), "sources_attempted": attempted,
            "sources_succeeded": succeeded,
            "sources_failed": configured_failed,
            "query_started_at": supplied_retrieval.get("query_started_at") or generated_at, "query_completed_at": supplied_retrieval.get("query_completed_at") or generated_at,
            "result_count_raw": len(_news_items(raw_news)), "result_count_deduped": len(admitted), "result_count_admitted": len(usable),
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
