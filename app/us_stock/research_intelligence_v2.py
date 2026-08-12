"""Deterministic US research intelligence, continuity, and calibration V2.

This module is deliberately read-only with respect to the Decision Layer.  It
normalizes research context and evaluates hypotheses/predictions, but never
exports an action, eligibility decision, rank, threshold, or model weight.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

from app.research.news_evidence_funnel import with_downstream_counts

SCHEMA_VERSION = "us_research_intelligence_v2"
PREDICTION_SCHEMA_VERSION = "us_prediction_evaluation_v2"
WINDOWS = ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630")
HYPOTHESIS_STATES = {
    "created", "confirmed", "strengthened", "unchanged", "weakened",
    "contradicted", "invalidated", "insufficient_new_evidence",
}
SOURCE_QUALITY_POLICY = {
    "tier_1": {"score": 100, "classes": ["regulator", "company_ir", "official_earnings", "government"]},
    "tier_2": {"score": 90, "classes": ["exchange", "official_macro", "official_index", "market_feed"]},
    "tier_3": {"score": 78, "classes": ["recognized_financial_media"]},
    "tier_4": {"score": 55, "classes": ["aggregator", "secondary_research"]},
    "tier_5": {"score": 25, "classes": ["weak_or_unverified"]},
}
COVERAGE_WEIGHTS = {
    "official": 0.18, "fundamental": 0.13, "earnings": 0.12,
    "macro": 0.10, "market": 0.08, "sector": 0.10, "etf": 0.08,
    "news": 0.08, "options": 0.05, "analyst": 0.04, "insider": 0.04,
}
COVERAGE_UTILITY = {
    "AVAILABLE": 1.0, "PARTIAL": 0.55, "CONTRADICTORY": 0.45,
    "STALE": 0.25, "MISSING": 0.0, "FAILED": 0.0,
}
BOUNDARY = {
    "layer": "research", "decision_layer_read_only_consumer": True,
    "action_exported": False, "eligibility_modified": False,
    "ranking_modified": False, "scoring_modified": False,
    "strategy_weights_modified": False, "prediction_model_modified": False,
    "auto_learning": False,
}


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _direction(value: Any) -> str:
    raw = _text(value).lower().replace("-", "_")
    if raw in {"bullish", "positive", "up", "long", "risk_on"}:
        return "bullish"
    if raw in {"bearish", "negative", "down", "short", "risk_off"}:
        return "bearish"
    if raw in {"neutral", "mixed", "flat"}:
        return "neutral"
    return "unavailable"


def classify_sec_filing(filing: dict[str, Any]) -> dict[str, Any]:
    """Classify SEC metadata conservatively; unknown content stays neutral."""
    form = _text(filing.get("form")).upper()
    item = _text(filing.get("item") or filing.get("items") or filing.get("category"))
    summary = _text(filing.get("summary") or filing.get("title") or filing.get("description"))
    corpus = f"{form} {item} {summary}".lower()
    rules = (
        ("cybersecurity", ("1.05", "cybersecurity", "cyber incident"), "high"),
        ("earnings", ("2.02", "results of operations", "earnings release"), "high"),
        ("guidance", ("guidance", "outlook", "forecast revision"), "high"),
        ("m_and_a", ("merger", "acquisition", "business combination"), "high"),
        ("material_agreement", ("1.01", "material definitive agreement"), "medium"),
        ("financing", ("2.03", "credit agreement", "financing", "debt"), "medium"),
        ("share_issuance", ("3.02", "unregistered sales", "share issuance"), "medium"),
        ("buyback", ("repurchase", "buyback"), "medium"),
        ("management_change", ("5.02", "departure", "appointment", "director", "officer"), "medium"),
        ("legal", ("8.01 legal", "litigation", "lawsuit"), "medium"),
        ("regulatory", ("regulatory", "government investigation"), "medium"),
        ("restructuring", ("2.05", "restructuring", "workforce reduction"), "medium"),
        ("product_business_update", ("product", "business update", "commercial launch"), "medium"),
        ("insider_related", ("form 4", "insider transaction"), "low"),
    )
    classification, materiality = "other", "low"
    for candidate, keywords, level in rules:
        if any(keyword in corpus for keyword in keywords):
            classification, materiality = candidate, level
            break
    if form in {"10-Q", "10-K"} and classification == "other":
        classification, materiality = "earnings", "high"
    inferable = any(token in corpus for token in ("raised guidance", "increased guidance", "record revenue", "buyback"))
    adverse = any(token in corpus for token in ("lowered guidance", "investigation", "cyber incident", "restructuring"))
    direction = "bullish" if inferable and not adverse else "bearish" if adverse and not inferable else "neutral"
    return {
        "classification": classification, "materiality": materiality,
        "direction": direction, "direction_inferred": direction != "neutral",
        "time_horizon": "near_term" if form == "8-K" else "medium_term",
        "role": "supporting" if direction == "bullish" else "opposing" if direction == "bearish" else "neutral",
        "explanation": (
            f"依 {form or 'SEC filing'} 的 item/摘要規則分類為 {classification}。"
            if classification != "other" else
            "現有 SEC metadata 不足以安全判定事件類型或方向，保留 other／neutral。"
        ),
        "method": "deterministic_form_item_keyword_v1",
    }


def normalize_news(items: Iterable[dict[str, Any]], observed_at: str, diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize and deduplicate actual items. Never creates live-news facts."""
    normalized: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        provenance = raw.get("provenance") if isinstance(raw.get("provenance"), dict) else {}
        headline = _text(raw.get("english_headline") or raw.get("headline"))
        reference = _text(provenance.get("source_reference") or raw.get("source_url") or raw.get("source_id"))
        published = provenance.get("published_at") or raw.get("published_at")
        cluster = "news_" + stable_hash([re.sub(r"[^a-z0-9]+", " ", headline.lower()).strip(), str(published)[:10]])[:16]
        duplicate_of = seen.get(cluster)
        item = {
            "news_id": "news_" + stable_hash([cluster, reference, headline])[:20],
            "event_cluster_id": cluster, "headline": headline or None,
            "summary": _text(raw.get("chinese_summary") or raw.get("summary") or raw.get("investment_reading")) or None,
            "publisher": raw.get("publisher") or provenance.get("publisher"),
            "published_at": published, "observed_at": observed_at,
            "source_reference": reference or None,
            "source_class": "company_ir" if raw.get("official_source") else "recognized_financial_media",
            "source_quality_tier": "tier_1" if raw.get("official_source") else "tier_3",
            "event_type": _text(raw.get("event_type") or "news").lower().replace(" ", "_"),
            "direction": _direction(raw.get("direction")),
            "materiality": _text(raw.get("materiality") or "medium").lower(),
            "relevance": _text(raw.get("relevance") or "medium").lower(),
            "time_horizon": _text(raw.get("time_horizon") or "near_term").lower(),
            "primary_source_confirmed": bool(raw.get("official_source")),
            "duplicate_of": duplicate_of, "counted": duplicate_of is None,
        }
        if duplicate_of is None:
            seen[cluster] = item["news_id"]
        normalized.append(item)
    admitted = sum(1 for x in normalized if x["counted"])
    # The canonical card renderer selects the first admitted item.  Keep the
    # remainder traceable as intentionally not rendered.
    funnel = with_downstream_counts(diagnostics or {}, rre_used=admitted, rendered=min(1, admitted))
    return {
        "status": "AVAILABLE" if any(x["counted"] for x in normalized) else "MISSING",
        "items": normalized,
        "deduplicated_count": sum(x["counted"] for x in normalized),
        "missing_reason": None if normalized else "LIVE_NEWS_SOURCE_UNAVAILABLE_OR_NO_ADMITTED_ITEMS",
        "fabricated": False, "evidence_funnel": funnel,
    }


def _status_for(category: str, evidence: list[dict[str, Any]], providers: list[dict[str, Any]], knowledge: dict[str, Any]) -> str:
    if category == "official":
        matching = [x for x in evidence if x.get("official_confirmation")]
    elif category == "market":
        matching = [x for x in evidence if x.get("event_type") == "market_context" and x.get("source_reference") in {"SPY", "QQQ"}]
    elif category == "etf":
        matching = [x for x in evidence if x.get("source_reference") in {"SPY", "QQQ", "SOXX"}]
    elif category == "earnings":
        matching = [x for x in evidence if x.get("event_type") == "earnings"]
    elif category == "news":
        matching = [x for x in evidence if x.get("event_type") not in {"filing", "fundamental", "earnings", "macro", "sector", "market_context"}]
    elif category == "knowledge":
        return "AVAILABLE" if knowledge.get("status") == "AVAILABLE" else "PARTIAL"
    else:
        matching = [x for x in evidence if x.get("event_type") == category]
    if matching:
        stale = [x for x in matching if x.get("freshness") == "stale"]
        directions = {_direction(x.get("direction")) for x in matching} - {"neutral", "unavailable"}
        if stale and len(stale) == len(matching):
            return "STALE"
        if len(directions) > 1:
            return "CONTRADICTORY"
        return "AVAILABLE"
    capable = [p for p in providers if category in (p.get("capability") or [])]
    if any(p.get("availability") == "SOURCE_FAILED" for p in capable):
        return "FAILED"
    return "MISSING"


def effective_coverage(bundle: dict[str, Any]) -> dict[str, Any]:
    evidence = [x for x in bundle.get("evidence", []) if isinstance(x, dict) and x.get("counted_in_synthesis")]
    providers = [x for x in bundle.get("providers", []) if isinstance(x, dict)]
    knowledge = bundle.get("knowledge") if isinstance(bundle.get("knowledge"), dict) else {}
    categories = {key: _status_for(key, evidence, providers, knowledge) for key in COVERAGE_WEIGHTS}
    denominator = sum(COVERAGE_WEIGHTS.values())
    score = sum(COVERAGE_WEIGHTS[key] * COVERAGE_UTILITY.get(status, 0) for key, status in categories.items()) / denominator * 100
    return {
        "schema_version": "us_effective_research_coverage_v2",
        "score": round(score, 2), "categories": categories,
        "weights": COVERAGE_WEIGHTS, "utility": COVERAGE_UTILITY,
        "available": sorted(k for k, v in categories.items() if v == "AVAILABLE"),
        "coverage_gap": sorted(k for k, v in categories.items() if v in {"MISSING", "FAILED", "STALE"}),
        "not_applicable_penalized": False, "duplicate_evidence_counted": False,
        "used_as_trade_score": False,
    }


def _regime_context(bundle: dict[str, Any]) -> dict[str, Any]:
    evidence = [x for x in bundle.get("evidence", []) if x.get("counted_in_synthesis")]
    def regime(item: dict[str, Any]) -> str:
        change = _number(item.get("observed_change_pct"))
        if change is not None and abs(change) < 0.2:
            return "neutral"
        return _direction(item.get("direction"))
    by_ref = {x.get("source_reference"): regime(x) for x in evidence}
    broad_values = [by_ref.get("SPY"), by_ref.get("QQQ")]
    broad = "bullish" if broad_values.count("bullish") == 2 else "bearish" if broad_values.count("bearish") == 2 else "neutral" if broad_values.count("neutral") == 2 else "mixed" if any(x in {"bullish", "bearish", "neutral"} for x in broad_values) else "unavailable"
    sector = by_ref.get("SOXX", "unavailable")
    return {
        "broad_market": broad, "growth_technology": by_ref.get("QQQ", "unavailable"),
        "sector": sector, "industry_proxy": "SOXX",
        "etf_relative_regime": "supportive" if sector == "bullish" else "adverse" if sector == "bearish" else "unavailable",
        "volatility_risk_regime": "unavailable",
        "broad_and_sector_are_independent": True,
    }


def _role_lists(bundle: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    counted = [x for x in bundle.get("evidence", []) if x.get("counted_in_synthesis")]
    supporting = [x for x in counted if _direction(x.get("direction")) == "bullish"]
    opposing = [x for x in counted if _direction(x.get("direction")) == "bearish"]
    neutral = [x for x in counted if _direction(x.get("direction")) not in {"bullish", "bearish"}]
    order = lambda x: (x.get("quality_score") or 0, x.get("confidence") or 0)
    return sorted(supporting, key=order, reverse=True), sorted(opposing, key=order, reverse=True), sorted(neutral, key=order, reverse=True)


def build_initial_projection(bundle: dict[str, Any], *, observed_at: str) -> dict[str, Any]:
    coverage = effective_coverage(bundle)
    supporting, opposing, neutral = _role_lists(bundle)
    regime = _regime_context(bundle)
    support_quality = sum((x.get("quality_score") or 0) * (x.get("confidence") or 0) for x in supporting)
    oppose_quality = sum((x.get("quality_score") or 0) * (x.get("confidence") or 0) for x in opposing)
    directional_total = support_quality + oppose_quality
    research_score = None if directional_total <= 0 else round(50 + 35 * (support_quality - oppose_quality) / directional_total, 2)
    if support_quality > oppose_quality * 1.2 and supporting:
        stance = "bullish"
    elif oppose_quality > support_quality * 1.2 and opposing:
        stance = "bearish"
    elif supporting or opposing:
        stance = "mixed"
    else:
        stance = "insufficient_evidence"
    confidence = min(90.0, coverage["score"] * 0.72 + min(18.0, (len(supporting) + len(opposing)) * 3.0))
    if supporting and opposing:
        confidence = max(0.0, confidence - 8.0)
    missing = coverage["coverage_gap"]
    hypothesis = {
        "statement": {
            "bullish": "高品質支持證據目前多於反對證據，後續需由量價與相對強弱確認。",
            "bearish": "高品質反對證據目前多於支持證據，後續需觀察跌勢與風險是否延續。",
            "mixed": "支持與反對證據並存，需等待價格與新事件化解衝突。",
            "insufficient_evidence": "現有研究證據不足以建立方向性結論，保留可驗證的觀察假設。",
        }[stance],
        "expected_direction": stance if stance in {"bullish", "bearish"} else "unavailable",
        "trigger": "23:00 以 Gap 延續、相對強弱與量能確認研究假設",
        "invalidation": "價格與量能形成與研究方向相反的明確延續，或出現高品質反向事件",
        "counter_argument": "市場／類股脈絡可能與個股證據背離；缺失來源可能改變目前結論。",
        "state": "created", "method": "deterministic_evidence_balance_v2",
    }
    brief = (
        f"研究立場為 {stance}；{len(supporting)} 項支持、{len(opposing)} 項反對。"
        f"有效覆蓋 {coverage['score']:.1f}%，主要缺口：{', '.join(missing[:4]) or '無'}。"
    )
    context_contracts = {
        "news": {
            "status": (bundle.get("news_intelligence_v2") or {}).get("status") or coverage["categories"].get("news"),
            "items": (bundle.get("news_intelligence_v2") or {}).get("items") or [],
            "missing_reason": (bundle.get("news_intelligence_v2") or {}).get("missing_reason"),
        },
        "macro": {"status": coverage["categories"].get("macro"), "rates": None, "yield_regime": None, "inflation": None, "labor": None, "usd": None, "liquidity": None, "oil": None, "volatility": None, "macro_event_risk": None},
        "options": {"status": coverage["categories"].get("options"), "implied_volatility": None, "expected_move": None, "put_call": None, "skew": None, "unusual_activity": None, "gamma_regime": None},
        "analyst": {"status": coverage["categories"].get("analyst"), "rating_change": None, "target_revision": None, "estimate_revision": None, "consensus_dispersion": None},
        "insider": {"status": coverage["categories"].get("insider"), "form_4": None, "transaction": None, "relative_size": None, "cluster_activity": None, "planned_sale": None},
    }
    projection = {
        "schema_version": SCHEMA_VERSION, "market": "US", "symbol": bundle.get("symbol"),
        "window": "us_pre_market_2000", "observed_at": observed_at,
        "origin_research_identity": bundle.get("research_identity"),
        "research_brief": brief, "research_stance": stance,
        "research_score": research_score, "research_score_is_trade_score": False,
        "research_score_method": "quality_confidence_weighted_directional_balance_v2",
        "research_confidence": round(confidence, 2),
        "confidence_explanation": {
            "supporting_count": len(supporting), "opposing_count": len(opposing),
            "missing_inputs": missing, "freshness_quality": "degraded" if "news" in missing or "macro" in missing else "adequate",
            "evidence_consistency": "conflicted" if supporting and opposing else "one_sided_or_sparse",
            "confidence_cap_reason": missing + (["EVIDENCE_CONFLICT"] if supporting and opposing else []),
        },
        "supporting_evidence": [x["evidence_id"] for x in supporting[:6]],
        "opposing_evidence": [x["evidence_id"] for x in opposing[:6]],
        "neutral_evidence": [x["evidence_id"] for x in neutral[:6]],
        "missing_evidence": missing, "effective_coverage": coverage,
        "market_sector_context": regime, "hypothesis": hypothesis,
        "context_contracts": context_contracts,
        "window_update": {"state": "created", "new_evidence": [], "explanation": "20:00 建立初始研究假設。"},
        "decision_context_export": {"trade_action": None, "eligibility": None, "ranking": None},
        "boundary": BOUNDARY,
    }
    projection["window_research_identity"] = "us_rv2_" + stable_hash(projection)[:24]
    return projection


def evolve_intraday(origin: dict[str, Any], observed: dict[str, Any], *, observed_at: str) -> dict[str, Any]:
    projection = json.loads(json.dumps(origin))
    hypothesis = dict(projection.get("hypothesis") or {})
    expected = hypothesis.get("expected_direction")
    gap = _number(observed.get("gap_current_pct"))
    volume = _number(observed.get("volume_ratio"))
    gap_state = _text(observed.get("gap_state"))
    usable = observed.get("data_status") in {"complete", "partial"} and gap is not None
    if not usable:
        state, explanation = "insufficient_new_evidence", "23:00 行情證據不足或過舊，不能把缺資料視為中性確認。"
    else:
        positive = gap > 0.35 and "follow_through" in gap_state and (volume or 0) >= 1.0
        negative = gap < -0.35 and "follow_through" in gap_state and (volume or 0) >= 1.0
        if expected == "bullish" and positive or expected == "bearish" and negative:
            state = "strengthened" if abs(gap) < 2.0 else "confirmed"
            explanation = f"Gap {gap:+.2f}% 延續且量能 {volume:.2f} 倍，與原研究方向一致。"
        elif expected == "bullish" and negative or expected == "bearish" and positive:
            state = "invalidated" if abs(gap) >= 2.0 and (volume or 0) >= 1.5 else "contradicted"
            explanation = f"Gap {gap:+.2f}% 延續且量能 {volume:.2f} 倍，與原研究方向相反。"
        elif expected == "unavailable":
            state = "unchanged"
            explanation = f"新增 Gap {gap:+.2f}%／量能 {volume if volume is not None else '不足'}，但 20:00 未建立方向假設；保留研究觀察。"
        else:
            state = "weakened" if (expected == "bullish" and gap < 0) or (expected == "bearish" and gap > 0) else "unchanged"
            explanation = f"Gap {gap:+.2f}% 與量能尚未形成足以確認或推翻假設的組合。"
    hypothesis["state"] = state
    projection.update({
        "window": "us_intraday_2300", "observed_at": observed_at,
        "hypothesis": hypothesis,
        "window_update": {
            "state": state, "explanation": explanation,
            "new_evidence": [
                {"type": "gap", "value_pct": gap, "state": gap_state, "source": observed.get("source")},
                {"type": "volume", "ratio": volume, "state": observed.get("volume_confirmation_state"), "source": observed.get("source")},
            ],
            "decision_layer_action_changed": False,
        },
    })
    projection["window_research_identity"] = "us_rv2_" + stable_hash({k: v for k, v in projection.items() if k != "window_research_identity"})[:24]
    return projection


def prediction_evaluation(prediction: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    low, high = _number(prediction.get("predicted_session_low")), _number(prediction.get("predicted_session_high"))
    actual_low, actual_high = _number(review.get("actual_low")), _number(review.get("actual_high"))
    actual_close, reference = _number(review.get("actual_close")), _number(prediction.get("reference_price"))
    available = None not in (low, high, actual_low, actual_high)
    width = None if not available else round(high - low, 4)
    midpoint_error = None if not available else round(((actual_high + actual_low) / 2) - ((high + low) / 2), 4)
    direction_expected = _direction(prediction.get("direction_forecast"))
    if direction_expected == "unavailable" and reference is not None and low is not None and high is not None:
        midpoint = (low + high) / 2
        direction_expected = "bullish" if midpoint > reference else "bearish" if midpoint < reference else "neutral"
    actual_direction = "unavailable" if actual_close is None or reference is None else "bullish" if actual_close > reference else "bearish" if actual_close < reference else "neutral"
    direction_hit = None if "unavailable" in {direction_expected, actual_direction} else direction_expected == actual_direction
    probability = _number(prediction.get("direction_probability"))
    method = prediction.get("direction_probability_method")
    brier = None
    if probability is not None and method and actual_direction in {"bullish", "bearish"}:
        p = probability / 100 if probability > 1 else probability
        brier = round((p - (1 if actual_direction == "bullish" else 0)) ** 2, 6)
    return {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "range": {"status": "evaluated" if available else "insufficient_evidence", "hit": review.get("prediction_range_result") == "hit" if available else None, "interval_width": width, "high_error": review.get("high_error"), "low_error": review.get("low_error"), "midpoint_error": midpoint_error},
        "direction": {"status": "evaluated" if direction_hit is not None else "insufficient_evidence", "forecast": direction_expected, "actual": actual_direction, "hit": direction_hit},
        "regime": {"status": "insufficient_evidence", "hit": None},
        "setup": {"status": "evaluated" if review.get("trade_review_outcome") else "insufficient_evidence", "outcome": review.get("trade_review_outcome")},
        "calibration": {"probability_available": probability is not None and bool(method), "probability": probability, "method": method, "brier_score": brier, "bucket": None if probability is None else int(min(9, max(0, probability // 10 if probability > 1 else probability * 10)))},
        "wide_interval_not_sufficient_success": True,
    }


def evolve_post_close(origin: dict[str, Any], intraday: dict[str, Any] | None, prediction: dict[str, Any], review: dict[str, Any], *, observed_at: str) -> dict[str, Any]:
    base = evolve_intraday(origin, intraday or {}, observed_at=observed_at) if intraday else json.loads(json.dumps(origin))
    evaluation = prediction_evaluation(prediction, review)
    trade_outcome = review.get("trade_review_outcome") or "pending_evidence"
    range_hit = review.get("prediction_range_result")
    hypothesis_state = (base.get("hypothesis") or {}).get("state") or "insufficient_new_evidence"
    missed_opportunity = trade_outcome == "no_trade" and range_hit == "hit" and hypothesis_state in {"confirmed", "strengthened"}
    learning = {
        "no_trade_still_evaluated": trade_outcome == "no_trade",
        "range_forecast_useful": range_hit == "hit",
        "direction_hypothesis_correct": (evaluation.get("direction") or {}).get("hit"),
        "conservative_decision_review": "requires_pm_review" if trade_outcome == "no_trade" else "not_applicable",
        "missed_opportunity_candidate": missed_opportunity,
        "trigger_too_strict_candidate": missed_opportunity,
        "evidence_quality_insufficient": bool(base.get("missing_evidence")),
        "auto_threshold_change": False, "auto_learning": False,
    }
    carry = {
        "unresolved_hypothesis": hypothesis_state not in {"invalidated", "confirmed"},
        "invalidated_hypothesis": hypothesis_state == "invalidated",
        "major_forecast_miss": range_hit == "miss",
        "contradictory_intraday_evidence": hypothesis_state in {"contradicted", "invalidated"},
        "missing_critical_sources": list(base.get("missing_evidence") or []),
        "carryforward_reason": "保留未解假設、重大預測誤差、盤中矛盾與關鍵來源缺口供下一個 20:00 研究。",
    }
    base.update({
        "window": "us_post_close_review_0630", "observed_at": observed_at,
        "prediction_evaluation": evaluation, "no_trade_learning": learning,
        "next_session_carryforward": carry,
        "window_update": {"state": "reviewed", "hypothesis_state": hypothesis_state, "range_result": range_hit, "trade_outcome": trade_outcome, "decision_layer_action_changed": False},
    })
    base["window_research_identity"] = "us_rv2_" + stable_hash({k: v for k, v in base.items() if k != "window_research_identity"})[:24]
    return base


def attach_initial(bundle: dict[str, Any], observed_at: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(bundle))
    updated["research_intelligence_v2"] = build_initial_projection(updated, observed_at=observed_at)
    updated["canonical_research_schema_version"] = SCHEMA_VERSION
    return updated


def validate_projection(projection: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("research_brief", "research_confidence", "supporting_evidence", "opposing_evidence", "missing_evidence", "hypothesis", "effective_coverage", "window_research_identity"):
        if projection.get(key) is None:
            errors.append(f"missing:{key}")
    hypothesis = projection.get("hypothesis") or {}
    if hypothesis.get("state") not in HYPOTHESIS_STATES:
        errors.append("invalid_hypothesis_state")
    if not hypothesis.get("trigger") or not hypothesis.get("invalidation") or not hypothesis.get("counter_argument"):
        errors.append("hypothesis_incomplete")
    boundary = projection.get("boundary") or {}
    if projection.get("decision_context_export", {}).get("trade_action") is not None:
        errors.append("research_exported_trade_action")
    if any(boundary.get(key) for key in ("eligibility_modified", "ranking_modified", "scoring_modified", "strategy_weights_modified", "prediction_model_modified", "auto_learning")):
        errors.append("layer_boundary_violation")
    return sorted(set(errors))
