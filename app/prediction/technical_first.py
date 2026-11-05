"""Versioned, pure technical/news/final boundaries. Never fetch or send here.

Technical outputs and their hashes survive every optional-news outcome. News
may veto an existing plan, but cannot manufacture direction, levels or confidence.
"""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
import math

from app.loaders.batch_universe import digest
from app.research.article_evidence import aware

KEY = "technical_first_decision_v1"


def number(value):
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def technical_base(*, market, symbol, as_of, features, bars, source_time,
                   prediction, confidence, plan, eligibility, price, source, session_date=None):
    """Accept only technical calculations and native risk-gate results.

    Daily price validity retains the TW seven-calendar-day ceiling. US execution
    additionally retains the existing 180-minute premarket gate in eligibility.
    Fetch timestamps are never used as market-data timestamps.
    """
    reasons = []
    target_session = session_date
    if number(price) is None or number(price) <= 0:
        reasons.append("PRICE_INVALID")
    if number(bars) is None or number(bars) < 20:
        reasons.append("INSUFFICIENT_HISTORY")
    if number(features.get("ma20")) is None:
        reasons.append("MA20_UNAVAILABLE")
    atr = next((number(features.get(k)) for k in ("atr14", "atr_like_range_pct", "atr_pct")
                if number(features.get(k)) is not None and number(features.get(k)) > 0), None)
    if atr is None:
        reasons.append("ATR_UNAVAILABLE")
    try:
        cutoff = aware(as_of)
        target_session = target_session or cutoff.astimezone(ZoneInfo("Asia/Taipei" if market == "TW" else "America/New_York")).date().isoformat()
        # Historical daily dates are trading dates, not invented intraday ticks.
        if len(str(source_time)) == 10:
            age = (cutoff.date() - datetime.fromisoformat(source_time).date()).days
        else:
            age = (cutoff - aware(source_time)).total_seconds() / 86400
        if not 0 <= age <= 7:
            reasons.append("PRICE_STALE_OR_FUTURE")
    except (ValueError, TypeError, OverflowError):
        reasons.append("PRICE_TIME_UNVERIFIED")
    if prediction.get("prediction_status") not in {"available", "evaluable"}:
        reasons.append("TECHNICAL_FORECAST_UNAVAILABLE")
    base = dict(schema_version="technical_base_v1", market=market, symbol=str(symbol), as_of=as_of,
                session_date=target_session,
                source=source, source_time=source_time, reference_price=price, history_bars=bars,
                indicators=deepcopy(features), prediction=deepcopy(prediction), confidence=confidence,
                trade_plan=deepcopy(plan), eligibility=deepcopy(eligibility),
                status="DATA_BLOCKED" if reasons else "PASS", reason_codes=reasons)
    if reasons:
        base["trade_plan"].update(status="data_blocked", entry=None, stop=None, target=None)
        base["eligibility"].update(actionable=False, entry_ready=False, top_opportunity=False,
                                   no_trade=True, watch_only=False,
                                   reason_codes=list(dict.fromkeys([*eligibility.get("reason_codes", []), *reasons])))
        base["unvalidated_prediction"] = deepcopy(base["prediction"])
        base["prediction"].update(prediction_status="insufficient_data", confidence=None,
                                  direction_forecast="insufficient_data", point_forecast={},
                                  predicted_session_low=None, predicted_session_high=None,
                                  predicted_next_session_low=None, predicted_next_session_high=None)
        if "range_forecast" in base["prediction"]:
            base["prediction"]["range_forecast"] = {"low": None, "high": None, "interval_width": None}
        base["confidence"] = None
    volume = number(features.get("volume_ma20"))
    base["technical_data_quality"] = {
        "level": "BLOCKED" if reasons else "FULL" if volume is not None and volume > 0 else "PARTIAL",
        "factor_status": {
            "price": "BLOCKED" if reasons else "AVAILABLE",
            "ma20": "AVAILABLE" if number(features.get("ma20")) is not None else "UNAVAILABLE",
            "atr": "AVAILABLE" if atr is not None else "UNAVAILABLE",
            "volume": "AVAILABLE" if volume is not None and volume > 0 else "UNAVAILABLE",
        },
    }
    base["base_id"] = digest(base)
    return base


def news_adjustment(*, entry, as_of, items, retrieval=None):
    """Revalidate persisted body evidence at the decision boundary; no refetch.

    A body-backed article need not imply positive/negative price impact. Until
    calibrated causal effects exist, keep forecast/confidence unchanged. An
    explicit high-risk event can only veto a plan, never create one.
    """
    from app.loaders.batch_universe import identity_terms
    retrieval = deepcopy(retrieval or {})
    accepted, rejected = [], []
    for item in items or []:
        ev = item.get("article_evidence") or {}
        reason = None
        company = item.get("company_identity") or {}
        facts = ev.get("facts") or []
        if (ev.get("investment_usable") is not True or ev.get("article_content_status") != "FULL_OR_SUBSTANTIVE"
                or not ev.get("content_sha256") or len(facts) < 2 or not ev.get("source_url")):
            reason = ev.get("reason") or "BODY_EVIDENCE_UNVERIFIED"
        elif not identity_terms(entry):
            reason = "COMPANY_IDENTITY_UNVERIFIED"
        elif company and str(company.get("symbol")) != str(entry.get("symbol")):
            reason = "COMPANY_MISMATCH"
        else:
            # Facts must actually contain a frozen company identity, even when
            # upstream investment_usable flags have been copied incorrectly.
            import re
            names = identity_terms(entry)
            attributable = [f for f in facts if any(
                re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", str(f.get("text", "")), re.I)
                if n.isascii() else n in str(f.get("text", "")) for n in names)]
            if len(attributable) < 2:
                reason = "FACT_COMPANY_ATTRIBUTION_UNVERIFIED"
            try:
                age = (aware(as_of) - aware(ev.get("published_at"))).total_seconds() / 3600
                if not 0 <= age <= (72 if entry.get("market") == "TW" else 96):
                    reason = "OUTSIDE_NEWS_WINDOW"
                for k in ("modified_at",):
                    if ev.get(k) and aware(ev[k]) > aware(as_of):
                        reason = "EVIDENCE_AFTER_AS_OF"
            except (ValueError, TypeError, OverflowError):
                reason = "CONTENT_TIME_UNVERIFIED"
        if reason:
            rejected.append({"source_url": ev.get("source_url") or item.get("source_url"), "reason": reason})
        else:
            # An unproven high-risk label must not masquerade as verified news.
            risk_claimed = item.get("event_risk") == "high"
            risk = item.get("event_risk_evidence") or {}
            proven = False
            if risk_claimed and isinstance(risk, dict):
                try:
                    proven = (bool(risk.get("event_type") and risk.get("reason") and risk.get("evidence_id"))
                              and risk.get("source_url") == ev.get("source_url")
                              and risk.get("content_sha256") == ev.get("content_sha256")
                              and 0 <= (aware(as_of) - aware(risk.get("observed_at"))).total_seconds()
                              and any(risk["evidence_id"] in {f.get("locator"), f.get("evidence_id")} for f in facts))
                except (ValueError, TypeError, OverflowError):
                    proven = False
            accepted.append({"candidate_id": item.get("candidate_id") or digest(ev),
                             "article_evidence": deepcopy(ev), "company_identity": deepcopy(entry),
                             "event_risk": "high" if proven else "UNKNOWN" if risk_claimed else "UNQUANTIFIED",
                             "event_risk_evidence": deepcopy(risk) if proven else None,
                             "event_risk_review_required": risk_claimed and not proven})
    attempts = retrieval.get("source_attempts") or {}
    content_failures = [e for e in (retrieval.get("content_quality") or {}).get("by_candidate", [])
                        if e.get("article_content_status") == "FAILED"]
    failed = (retrieval.get("status") in {"FAILED", "UNAVAILABLE"}
              or (retrieval.get("retrieval") or {}).get("status") == "FAILED"
              or bool(retrieval.get("failure_reason")) or bool(content_failures)
              or any(a.get("status") == "FAILED" for a in attempts.values()))
    observed = bool(retrieval) and not failed
    status = "AVAILABLE" if accepted else "UNAVAILABLE" if failed or not observed else "NO_RELEVANT_NEWS"
    high_risk = any(a["event_risk"] == "high" for a in accepted)
    review_required = any(a["event_risk_review_required"] for a in accepted)
    return {"schema_version": "news_adjustment_v1", "as_of": as_of, "news_status": status,
            "event_risk": "high" if high_risk else "UNKNOWN" if review_required else "UNQUANTIFIED" if accepted else "UNKNOWN",
            "event_risk_review_required": review_required, "accepted": accepted,
            "rejected": rejected, "retrieval": retrieval, "confidence_delta": 0,
            "direction_adjustment": None, "range_adjustment": None,
            "adjustment_reason": "EVENT_RISK_HIGH" if high_risk else "EVENT_RISK_UNVERIFIED_REVIEW" if review_required else "QUALIFIED_EVENT_CONTEXT_ONLY_UNCALIBRATED" if accepted else "NO_NEWS_ADJUSTMENT",
            "stages": {"discovery": "OBSERVED" if retrieval or items else "UNKNOWN",
                       "fetch": "BODY_EVIDENCE_RETAINED" if accepted else "SEE_REJECTIONS_OR_UNKNOWN",
                       "parse": "BODY_FACTS_RETAINED" if accepted else "UNKNOWN",
                       "admission": {"accepted": len(accepted), "rejected": len(rejected)},
                       "publish": "DECISION_CONTEXT" if accepted else "ABSENCE_EXPLICIT"}}


def final_decision(base, adjustment):
    if base.get("base_id") != digest({k: v for k, v in base.items() if k != "base_id"}):
        raise ValueError("TECHNICAL_BASE_HASH_MISMATCH")
    if base.get("as_of") != adjustment.get("as_of"):
        raise ValueError("DECISION_ASOF_MISMATCH")
    valid = base["status"] == "PASS"
    usable = bool(adjustment.get("accepted"))
    final = {"mode": "DATA_BLOCKED" if not valid else "TECHNICAL_PLUS_NEWS" if usable else "TECHNICAL_ONLY",
             "prediction": deepcopy(base["prediction"]), "confidence": base["confidence"],
             "trade_plan": deepcopy(base["trade_plan"]), "eligibility": deepcopy(base["eligibility"]),
             "news_status": adjustment["news_status"], "event_risk": adjustment["event_risk"],
             "technical_research_usable": valid, "news_evidence_usable": usable,
             "combined_research_usable": valid and usable,
             "news_adjustment_applied": False, "adjustment_reason": adjustment["adjustment_reason"]}
    final["technical_data_quality"] = deepcopy(base.get("technical_data_quality"))
    if valid and usable and (adjustment["event_risk"] == "high" or adjustment.get("event_risk_review_required")):
        reason = "EVENT_RISK_HIGH" if adjustment["event_risk"] == "high" else "EVENT_RISK_UNVERIFIED_REVIEW"
        final["trade_plan"].update(status="no_trade", entry=None, stop=None, target=None)
        final["eligibility"].update(actionable=False, entry_ready=False, top_opportunity=False,
                                    no_trade=True, watch_only=False,
                                    reason_codes=list(dict.fromkeys([*final["eligibility"].get("reason_codes", []), reason])))
        final["news_adjustment_applied"] = adjustment["event_risk"] == "high"
    result = {"schema_version": KEY, "technical_base": deepcopy(base), "news_adjustment": deepcopy(adjustment),
              "final_decision": final}
    result["decision_id"] = digest(result)
    return result


# Presentation-only vocabulary. Canonical enums in frozen decisions remain unchanged.
_PUBLIC_MODE = {
    "TECHNICAL_ONLY": "僅依技術分析",
    "TECHNICAL_PLUS_NEWS": "技術分析與新聞佐證",
    "DATA_BLOCKED": "技術資料不足",
}
_PUBLIC_NEWS = {
    "AVAILABLE": "有可用新聞證據",
    "NO_RELEVANT_NEWS": "未取得符合條件的相關新聞",
    "UNAVAILABLE": "新聞資料無法取得",
}
_PUBLIC_EVENT_RISK = {
    "high": "高風險",
    "UNQUANTIFIED": "尚未量化",
    "UNKNOWN": "尚無法判定",
}


def status_text(card):
    """Present frozen decision states in Traditional Chinese without mutating evidence.

    Never fall through to an unknown raw internal enum in a public channel.
    Missing or future enum values retain uncertainty rather than claiming safety.
    """
    decision = card.get(KEY) or {}
    final = decision.get("final_decision") or {}
    if not final:
        return "技術／新聞分層：舊產物未保存分層證據"
    technical = "可用" if final.get("technical_research_usable") is True else "資料不足"
    confidence = number(final.get("confidence"))
    confidence_text = str(final["confidence"]) if confidence is not None else "尚未取得"
    return (
        f"分析依據：{_PUBLIC_MODE.get(final.get('mode'), '尚無法判定')}"
        f"｜技術：{technical}"
        f"｜新聞：{_PUBLIC_NEWS.get(final.get('news_status'), '尚無法判定')}"
        f"｜事件風險：{_PUBLIC_EVENT_RISK.get(final.get('event_risk'), '尚無法判定')}"
        f"｜信心：{confidence_text}（技術信心，非校準勝率）"
    )


def attach(card, decision):
    """Project the same decision to every channel; never override native gates."""
    card[KEY] = deepcopy(decision)
    card["decision_basis_summary"] = status_text(card)
    return card
