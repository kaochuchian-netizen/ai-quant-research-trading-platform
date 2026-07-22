"""Canonical US 20:00 premarket decision contract.

The module deliberately keeps observed extended-hours evidence separate from
daily OHLCV.  Every downstream channel consumes the same eligibility and
summary records; missing premarket evidence never becomes an actionable setup.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
MIN_CONFIDENCE = 35.0
MIN_REWARD_RISK = 1.0
MAX_PREMARKET_AGE_MINUTES = 180


def _number(value: Any) -> float | None:
    try:
        return round(float(value), 4) if value is not None else None
    except (TypeError, ValueError):
        return None


def _freshness(timestamp: Any, reference: datetime | None) -> str:
    if not timestamp:
        return "unavailable"
    try:
        observed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return "invalid"
        reference = reference or datetime.now(NEW_YORK)
        age = (reference.astimezone(NEW_YORK) - observed.astimezone(NEW_YORK)).total_seconds() / 60
        return "fresh" if -15 <= age <= MAX_PREMARKET_AGE_MINUTES else "stale"
    except (TypeError, ValueError):
        return "invalid"


def normalize_premarket_quote(quote: dict[str, Any], reference: datetime | None = None) -> dict[str, Any]:
    previous = _number(quote.get("previous_close"))
    price = _number(quote.get("pre_market_price"))
    timestamp = quote.get("pre_market_time")
    freshness = _freshness(timestamp, reference)
    change = round(price - previous, 4) if price is not None and previous not in (None, 0) else None
    change_pct = round(change / previous * 100, 4) if change is not None and previous else None
    available = price is not None and previous not in (None, 0) and timestamp is not None
    return {
        "previous_close": previous,
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "gap_pct": change_pct,
        "gap_direction": "up" if change_pct is not None and change_pct > 0.05 else "down" if change_pct is not None and change_pct < -0.05 else "flat" if change_pct is not None else "unavailable",
        "volume": _number(quote.get("pre_market_volume")),
        "timestamp": timestamp,
        "source": quote.get("market_data_source") or "Yahoo Finance / yfinance",
        "freshness": freshness,
        "availability": "available" if available and freshness == "fresh" else "stale" if available and freshness == "stale" else "unavailable",
    }


def normalize_market_context(context: dict[str, Any], reference: datetime | None = None) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for symbol in ("SPY", "QQQ", "SOXX"):
        source = (context.get("items") or {}).get(symbol, {})
        observed = source.get("premarket") if isinstance(source.get("premarket"), dict) else {}
        freshness = _freshness(observed.get("timestamp"), reference)
        has_values = observed.get("price") is not None and observed.get("previous_close") not in (None, 0)
        normalized[symbol.lower()] = {
            "symbol": symbol,
            "premarket_price": observed.get("price"),
            "previous_close": observed.get("previous_close"),
            "change_pct": observed.get("change_pct"),
            "timestamp": observed.get("timestamp"),
            "source": observed.get("source"),
            "freshness": freshness,
            "availability": "available" if has_values and freshness == "fresh" else "stale" if has_values and freshness == "stale" else "unavailable",
        }
    spy = normalized["spy"].get("change_pct")
    qqq = normalized["qqq"].get("change_pct")
    regime = "unavailable"
    if isinstance(spy, (int, float)) and isinstance(qqq, (int, float)):
        regime = "risk_on" if (spy + qqq) / 2 >= 0.3 else "risk_off" if (spy + qqq) / 2 <= -0.3 else "neutral"
    return {
        **normalized,
        "sector_proxy": normalized["soxx"],
        "regime": regime,
        "risk_direction": "偏多" if regime == "risk_on" else "偏空" if regime == "risk_off" else "中性" if regime == "neutral" else "尚未取得",
        "timestamp": max([str(x.get("timestamp")) for x in normalized.values() if x.get("timestamp")], default=None),
        "source": "Yahoo Finance / yfinance extended-hours quote",
    }


def canonical_event_risk(research: dict[str, Any]) -> dict[str, Any]:
    earnings = str((research.get("earnings") or {}).get("event_risk_level") or "unavailable")
    sec = research.get("sec") or {}
    filings = sec.get("recent_8k_items") or []
    sec_level = "medium" if any(isinstance(x, dict) and (x.get("materiality") in {"material", "high"} or x.get("item")) for x in filings) else "low" if sec.get("ok") else "unavailable"
    news_items = (research.get("material_news") or {}).get("items") or []
    news_level = "medium" if news_items else "unavailable"
    levels = [x for x in (earnings, sec_level, news_level) if x in {"low", "medium", "high"}]
    canonical = "high" if "high" in levels else "medium" if "medium" in levels else "low" if levels else "unavailable"
    return {
        "canonical_level": canonical,
        "earnings_risk": earnings,
        "sec_filing_risk": sec_level,
        "news_risk": news_level,
        "macro_event_risk": "unavailable",
        "reason_codes": (["RECENT_MATERIAL_SEC_FILING"] if sec_level == "medium" else []) + (["EARNINGS_RISK"] if earnings in {"medium", "high"} else []),
    }


def separate_sec_news(research: dict[str, Any], news_items: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    sec = research.get("sec") or {}
    filing = sec.get("recent_8k_items") or [sec.get("latest_quarterly_report"), sec.get("latest_annual_report")]
    filing = next((x for x in filing if isinstance(x, dict)), {})
    sec_evidence = {
        "availability": "available" if filing else "unavailable",
        "form": filing.get("form"), "filing_date": filing.get("filing_date") or filing.get("filed_at"),
        "item": filing.get("item") or filing.get("category"), "materiality": filing.get("materiality") or "unclassified",
        "summary": filing.get("summary"), "source": filing.get("source") or sec.get("source") or "SEC EDGAR",
    }
    news = next((x for x in news_items if isinstance(x, dict) and x.get("english_headline")), {})
    news_evidence = {
        "availability": "available" if news else "unavailable",
        "headline": news.get("english_headline"), "publisher": news.get("source"),
        "published_at": news.get("published_at"), "direction": news.get("direction") or "unavailable",
        "relevance": news.get("relevance") or "unavailable", "confidence": news.get("confidence") or "unavailable",
        "strategy_impact": news.get("investment_reading") if news else "不納入本次盤前方向判斷",
    }
    return sec_evidence, news_evidence


def build_premarket_card(card: dict[str, Any], quote: dict[str, Any], research: dict[str, Any], news_items: list[dict[str, Any]], market_context: dict[str, Any], reference: datetime | None = None) -> dict[str, Any]:
    tactical = card.get("daily_tactical_summary") or {}
    premarket = normalize_premarket_quote(quote, reference)
    confidence = _number(tactical.get("confidence")) or 0.0
    rr = _number(tactical.get("reward_risk_ratio"))
    direction = str(tactical.get("direction") or "unavailable")
    action = str(tactical.get("action") or "")
    chase = str(tactical.get("chase_risk") or "unavailable")
    event = canonical_event_risk(research)
    reasons: list[str] = []
    if premarket["availability"] != "available": reasons.append("PREMARKET_DATA_UNAVAILABLE_OR_STALE")
    if rr is None or rr < MIN_REWARD_RISK: reasons.append("RR_BELOW_THRESHOLD")
    if confidence < MIN_CONFIDENCE: reasons.append("LOW_CONFIDENCE")
    if direction not in {"bullish", "mildly_bullish"}: reasons.append("DIRECTION_NOT_BULLISH")
    if "等待" in action or "觀望" in action: reasons.append("SETUP_NOT_STABILIZED")
    if chase == "high": reasons.append("CHASE_RISK_HIGH")
    if event["canonical_level"] == "high": reasons.append("EVENT_RISK_HIGH")
    actionable = not reasons
    entry_ready = actionable
    top = actionable
    no_trade = not actionable and (rr is None or rr < MIN_REWARD_RISK or confidence < MIN_CONFIDENCE)
    sec_evidence, news_evidence = separate_sec_news(research, news_items)
    market = normalize_market_context(market_context, reference)
    qqq_change = (market.get("qqq") or {}).get("change_pct")
    sector_change = (market.get("sector_proxy") or {}).get("change_pct")
    return {
        **card,
        "premarket": premarket,
        "market_context": market,
        "relative_strength": {
            "vs_qqq_pct": round(premarket["change_pct"] - qqq_change, 4) if premarket["change_pct"] is not None and isinstance(qqq_change, (int, float)) else None,
            "vs_sector_pct": round(premarket["change_pct"] - sector_change, 4) if premarket["change_pct"] is not None and isinstance(sector_change, (int, float)) else None,
        },
        "eligibility": {"candidate": True, "entry_ready": entry_ready, "top_opportunity": top, "actionable": actionable, "watch_only": not actionable and not no_trade, "no_trade": no_trade, "reason_codes": reasons},
        "trade_plan": {"status": "active" if actionable else "watch_only", "entry": tactical.get("entry_zone") if actionable else None, "observation_zone": tactical.get("entry_zone") if not actionable else None, "stop": tactical.get("stop_reference") if actionable else None, "target": tactical.get("target_zone_1") if actionable else None, "reward_risk": rr, "reassessment_condition": "盤前資料完整、信心與報酬風險比達門檻，且價格完成止穩／觸發確認" if not actionable else "依正式觸發條件執行"},
        "event_risk": event,
        "sec_evidence": sec_evidence,
        "news_evidence": news_evidence,
        "confidence_policy": {"score": confidence, "level": "low" if confidence < MIN_CONFIDENCE else "medium_low" if confidence < 50 else "medium", "presentation_mode": "conditional" if not actionable else "active"},
    }


def summarize_premarket(cards: list[dict[str, Any]], market_context: dict[str, Any]) -> dict[str, Any]:
    def symbols(key: str) -> list[str]:
        return sorted(str(c.get("symbol")) for c in cards if (c.get("eligibility") or {}).get(key))
    groups = {key: symbols(key) for key in ("top_opportunity", "actionable", "watch_only", "no_trade", "entry_ready")}
    return {
        "tracking_count": len(cards),
        "top_opportunity_count": len(groups["top_opportunity"]),
        "actionable_count": len(groups["actionable"]),
        "watch_only_count": len(groups["watch_only"]),
        "no_trade_count": len(groups["no_trade"]),
        "entry_ready_count": len(groups["entry_ready"]),
        "premarket_available_count": sum((c.get("premarket") or {}).get("availability") == "available" for c in cards),
        "groups": groups,
        "market_context": market_context,
    }


def validate_premarket_contract(cards: list[dict[str, Any]], summary: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for card in cards:
        symbol = str(card.get("symbol"))
        e = card.get("eligibility") or {}
        if e.get("top_opportunity") and not e.get("actionable"): errors.append(f"{symbol}: top opportunity is not actionable")
        if e.get("actionable") and e.get("no_trade"): errors.append(f"{symbol}: actionable conflicts with no_trade")
        if e.get("watch_only") and e.get("top_opportunity"): errors.append(f"{symbol}: watch_only conflicts with top opportunity")
        if e.get("top_opportunity") and (card.get("trade_plan") or {}).get("reward_risk", 0) < MIN_REWARD_RISK: errors.append(f"{symbol}: RR below threshold")
    expected = sorted(str(c.get("symbol")) for c in cards if (c.get("eligibility") or {}).get("top_opportunity"))
    if expected != (summary.get("groups") or {}).get("top_opportunity", []): errors.append("top opportunity list mismatch")
    if len(expected) != summary.get("top_opportunity_count"): errors.append("top opportunity count mismatch")
    return errors
