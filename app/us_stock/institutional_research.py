"""Canonical US institutional research bundle (research context only)."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.us_stock.research_intelligence_v2 import (
    attach_initial as attach_research_v2,
    classify_sec_filing,
    effective_coverage,
    normalize_news,
    validate_projection,
)
from app.us_stock.market_context_contract import canonical_ticker, normalize_us_market_context
from app.runtime.intelligence_quality import (
    completeness_v2, intelligence_health, intelligence_readiness_v1,
    semantic_degradation,
)

SCHEMA_VERSION = "us_institutional_research_bundle_v1"
BOUNDARY = {"consumer": "existing_decision_engine", "mode": "read_only_context",
            "trade_action_exported": False, "ranking_modified": False,
            "scoring_modified": False, "prediction_modified": False,
            "strategy_weights_modified": False, "auto_learning": False}


def _provider(pid: str, name: str, tier: str, license_: str, status: str, *caps: str) -> dict[str, Any]:
    return {"provider_id": pid, "provider_name": name, "tier": tier, "license": license_,
            "status": status, "capability": list(caps), "supported_markets": ["US"]}


PROVIDERS = (
    _provider("sec_edgar", "SEC EDGAR", "A", "public_official", "CONNECTED", "official", "filing", "fundamental"),
    _provider("company_ir", "Company Investor Relations", "A", "public_official", "CONFIGURED", "official", "ir", "newsroom"),
    _provider("nasdaq", "NASDAQ", "A", "public_reference", "NOT_CONFIGURED", "exchange", "calendar"),
    _provider("nyse", "NYSE", "A", "public_reference", "NOT_CONFIGURED", "exchange", "calendar"),
    _provider("yfinance", "Yahoo Finance / yfinance", "B", "external_terms", "CONNECTED", "price", "fundamental", "earnings", "etf", "news_metadata"),
    _provider("fmp", "Financial Modeling Prep", "B", "commercial_required", "NOT_CONFIGURED", "fundamental", "analyst"),
    _provider("finnhub", "Finnhub", "B", "commercial_required", "NOT_CONFIGURED", "news", "analyst", "insider"),
    _provider("polygon", "Polygon", "B", "commercial_required", "NOT_CONFIGURED", "price", "news", "options"),
    _provider("reuters", "Reuters", "C", "licensed_feed_required", "NOT_LICENSED", "news", "macro", "sector"),
    _provider("ap", "Associated Press", "C", "licensed_feed_required", "NOT_LICENSED", "news"),
    _provider("bloomberg", "Bloomberg", "C", "licensed_feed_required", "NOT_LICENSED", "metadata_only"),
    _provider("cnbc", "CNBC", "C", "licensed_or_public_feed_required", "NOT_CONFIGURED", "news"),
    _provider("marketwatch", "MarketWatch", "C", "licensed_or_public_feed_required", "NOT_CONFIGURED", "news"),
    _provider("barrons", "Barron's", "C", "licensed_feed_required", "NOT_LICENSED", "news", "analyst"),
    _provider("social_unverified", "Social / Unverified", "D", "unverified_reference", "NOT_CONFIGURED", "sentiment_reference"),
    _provider("federal_reserve", "Federal Reserve", "A", "public_official", "NOT_CONFIGURED", "macro", "calendar"),
    _provider("bls", "U.S. Bureau of Labor Statistics", "A", "public_official", "NOT_CONFIGURED", "macro", "calendar"),
    _provider("bea", "U.S. Bureau of Economic Analysis", "A", "public_official", "NOT_CONFIGURED", "macro", "calendar"),
    _provider("treasury", "U.S. Treasury", "A", "public_official", "NOT_CONFIGURED", "macro"),
    _provider("options_provider", "Options Reference Provider", "B", "commercial_required", "NOT_CONFIGURED", "options"),
    _provider("analyst_provider", "Analyst Consensus Provider", "B", "commercial_required", "NOT_CONFIGURED", "analyst"),
    _provider("insider_provider", "Insider / 13F Provider", "B", "commercial_required", "NOT_CONFIGURED", "insider", "institutional_flow"),
)

KNOWLEDGE = {
    "AAPL": [["consumer_technology", "services"], ["iphone", "mac", "wearables"], ["device_cycle", "services_mix"], ["mobile_ecosystems"], ["semiconductors", "asia_manufacturing"], ["technology_hardware"], ["consumer_demand", "usd", "rates"], ["regulation", "supply_chain"], ["product_cycle", "capital_return"]],
    "NVDA": [["semiconductors", "accelerated_computing"], ["gpu", "data_center", "networking"], ["ai_capex", "cloud_demand"], ["accelerator_semiconductors"], ["foundry", "advanced_packaging", "memory"], ["semiconductors"], ["technology_capex", "export_controls"], ["customer_concentration", "export_controls"], ["ai_platform_adoption", "new_architecture"]],
    "TSLA": [["electric_vehicles", "energy_storage"], ["vehicles", "energy", "software"], ["deliveries", "pricing"], ["global_automakers"], ["batteries", "manufacturing"], ["automotive"], ["rates", "consumer_credit"], ["pricing_pressure", "execution"], ["new_models", "margin_recovery"]],
    "GOOGL": [["digital_advertising", "cloud"], ["search", "youtube", "cloud"], ["ad_demand", "cloud_growth", "ai_monetization"], ["digital_ads", "cloud"], ["data_centers", "semiconductors"], ["communication_services"], ["advertising_cycle"], ["antitrust", "ai_disruption"], ["cloud_margin", "ai_products"]],
    "TSM": [["semiconductor_foundry"], ["advanced_nodes", "packaging"], ["ai_demand", "smartphone_cycle"], ["global_foundries"], ["equipment", "materials"], ["semiconductors"], ["global_capex", "geopolitics"], ["geopolitics", "customer_concentration"], ["node_ramp", "advanced_packaging"]],
    "SPCX": [["special_purpose_acquisition"], [], ["transaction_completion"], ["capital_markets"], [], ["financial_vehicle"], ["rates", "risk_appetite"], ["deal_risk", "liquidity"], ["transaction_announcement"]],
}
KNOWLEDGE_KEYS = ("business", "products", "revenue_drivers", "competition", "supply_chain", "sector", "macro_exposure", "risk_factors", "catalysts")
QUALITY = {"A": 100, "B": 88, "C": 78, "D": 30}
COVERAGE_KEYS = ("official", "fundamental", "macro", "sector", "news", "knowledge", "etf", "options", "analyst", "insider")
EVENT_TYPES = {
    "earnings", "guidance", "product", "ai", "m_and_a", "litigation",
    "regulation", "macro", "sector", "supply_chain", "buyback", "dividend",
    "management", "partnership", "analyst", "insider", "options", "filing",
    "fundamental", "market_context", "news",
}


def stable_hash(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def _direction(value: Any) -> str:
    raw = str(value or "").lower().replace("-", "_")
    if raw in {"bullish", "positive", "up", "risk_on", "research_positive"}: return "bullish"
    if raw in {"bearish", "negative", "down", "risk_off", "research_risk"}: return "bearish"
    if raw in {"", "unavailable", "not_evaluated", "unknown", "insufficient_data"}: return "unavailable"
    return "neutral"


def _event_type(value: Any) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", str(value or "news").lower()).strip("_")
    aliases = {
        "m_a": "m_and_a", "merger": "m_and_a", "acquisition": "m_and_a",
        "product_launch": "product", "legal": "litigation",
        "regulatory": "regulation", "management_change": "management",
        "analyst_commentary": "analyst", "sentiment": "news",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in EVENT_TYPES else "news"


def _freshness(value: Any, observed_at: Any = None) -> str:
    if not value: return "unknown"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
        reference = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00")) if observed_at else datetime.now(timezone.utc)
        if reference.tzinfo is None: reference = reference.replace(tzinfo=timezone.utc)
        hours = (reference.astimezone(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600
    except (TypeError, ValueError): return "unknown"
    return "fresh" if hours <= 72 else "recent" if hours <= 720 else "stale"


def provider_snapshot(research: dict[str, Any], market_context: dict[str, Any]) -> list[dict[str, Any]]:
    # A configured IR URL is registry metadata, not proof that an IR collector
    # connected successfully.  Only adapters with observed data become AVAILABLE.
    canonical_market = normalize_us_market_context(market_context)
    observed = {"sec_edgar": bool((research.get("sec") or {}).get("ok")),
                "yfinance": bool((research.get("fundamentals") or {}).get("metrics")) or canonical_market["normalization_status"] in {"VALID", "PARTIAL"}}
    rows = []
    for configured in PROVIDERS:
        row, success = dict(configured), observed.get(configured["provider_id"])
        row["availability"] = "AVAILABLE" if success else "SOURCE_FAILED" if success is False and row["status"] == "CONNECTED" else row["status"]
        row["last_success"] = ((research.get("sec") or {}).get("provenance") or {}).get("retrieved_at") if row["provider_id"] == "sec_edgar" and success else None
        row["freshness"] = "current" if success else "unavailable"
        rows.append(row)
    return rows


def company_knowledge(symbol: str, research: dict[str, Any]) -> dict[str, Any]:
    values, official = KNOWLEDGE.get(symbol.upper()), research.get("official_sources") or {}
    return {"schema_version": "us_company_knowledge_v1", "symbol": symbol.upper(),
            "status": "AVAILABLE" if values else "PARTIAL",
            "dimensions": dict(zip(KNOWLEDGE_KEYS, values)) if values else {key: [] for key in KNOWLEDGE_KEYS},
            "source_references": [x for x in (official.get("investor_relations_url"), official.get("sec_company_page")) if x],
            "machine_readable": True}


def evidence_record(symbol: str, provider: str, tier: str, headline: str, summary: str,
                    observed_at: str, event_type: str, *, published_at: Any = None,
                    direction: Any = "neutral", materiality: str = "medium",
                    relevance: str = "high", confidence: float = .8,
                    official: bool = False, reference: Any = None) -> dict[str, Any]:
    normalized = re.sub(r"[^a-z0-9]+", " ", headline.lower()).strip()
    canonical_event_type = _event_type(event_type)
    freshness = _freshness(published_at, observed_at)
    item = {"event_cluster_id": "evt_" + stable_hash([symbol, canonical_event_type, normalized, str(published_at or "")[:10], reference])[:16],
            "market": "US", "symbol": symbol.upper(), "provider": provider,
            "source": provider, "source_class": "official_primary" if tier == "A" else "market_reference" if tier == "B" else "financial_media" if tier == "C" else "weak_reference",
            "source_quality": f"tier_{1 if tier == 'A' else 2 if tier == 'B' else 3 if tier == 'C' else 5}",
            "provider_tier": tier, "quality_score": QUALITY[tier], "headline": headline,
            "summary": summary, "published_at": published_at, "observed_at": observed_at,
            "freshness": freshness, "stale": freshness == "stale", "event_type": canonical_event_type,
            "direction": _direction(direction), "materiality": materiality,
            "relevance": relevance, "confidence": round(float(confidence), 2),
            "official_confirmation": official, "source_reference": reference,
            "primary_source_confirmed": official, "role": "supporting" if _direction(direction) == "bullish" else "opposing" if _direction(direction) == "bearish" else "neutral",
            "novelty": "new", "time_horizon": "near_term", "related_hypothesis": None,
            "duplicate_of": None, "counted_in_synthesis": True,
            "decision_context": "research_context_only_no_trade_action",
            "provenance": {"provider": provider, "source_reference": reference, "published_at": published_at, "observed_at": observed_at}}
    item["evidence_nature"] = "primary_source_fact" if official else "normalized_source_reference"
    contextual = canonical_event_type in {"market_context", "sector", "technical", "price", "volume", "adr", "etf"}
    item["direction_ownership"] = "contextual_confirmation_only" if contextual else "company_substantive"
    item["direction_ownership_version"] = "research_direction_ownership_v1"
    item["fact"] = {"headline": headline, "summary": summary, "published_at": published_at, "source_reference": reference}
    item["interpretation"] = {"direction": item["direction"], "materiality": materiality, "time_horizon": item["time_horizon"], "method": "deterministic_normalization_v2"}
    item["evidence_id"] = "ev_" + stable_hash(item)[:20]
    return item


def canonical_evidence(symbol: str, research: dict[str, Any], market_context: dict[str, Any], observed_at: str) -> list[dict[str, Any]]:
    rows = []
    for filing in [x for x in (research.get("sec") or {}).get("filings", []) if isinstance(x, dict)][:4]:
        classification = classify_sec_filing(filing)
        evidence = evidence_record(symbol, "sec_edgar", "A", f"{filing.get('form') or 'SEC'} filing", classification["explanation"], observed_at, "filing", published_at=filing.get("filing_date"), direction=classification["direction"], materiality=classification["materiality"], confidence=.98, official=True, reference=filing.get("filing_url") or filing.get("accession"))
        evidence["filing_intelligence"] = classification
        evidence["time_horizon"] = classification["time_horizon"]
        evidence["role"] = classification["role"]
        evidence["interpretation"] = {"direction": classification["direction"], "materiality": classification["materiality"], "time_horizon": classification["time_horizon"], "method": classification["method"]}
        rows.append(evidence)
    fundamentals = research.get("fundamentals") or {}; metrics = fundamentals.get("metrics") or {}
    available = [key for key, value in metrics.items() if isinstance(value, dict) and value.get("value") is not None]
    if available:
        rows.append(evidence_record(symbol, "yfinance", "B", "Fundamental reference metrics available", f"{len(available)} normalized fundamental metrics", observed_at, "fundamental", direction=(fundamentals.get("comparison") or {}).get("trend_direction"), confidence=.78, reference="fundamentals.metrics"))
    latest = (research.get("earnings") or {}).get("latest_earnings") or {}
    if latest.get("actual_eps") is not None or latest.get("actual_revenue") is not None:
        rows.append(evidence_record(symbol, "yfinance", "B", "Latest earnings reference available", "Actual fields available; official confirmation remains explicit", observed_at, "earnings", published_at=latest.get("reported_date"), materiality="high", confidence=.76, reference="earnings.latest_earnings"))
    for news in [x for x in (research.get("material_news") or {}).get("items", []) if isinstance(x, dict)]:
        provenance, official = news.get("provenance") or {}, bool(news.get("official_source"))
        row = evidence_record(symbol, "company_ir" if official else "yfinance", "A" if official else "C", str(news.get("english_headline") or "Material event metadata"), str(news.get("chinese_summary") or news.get("investment_reading") or ""), observed_at, str(news.get("event_type") or "news"), published_at=provenance.get("published_at"), direction=news.get("direction"), materiality=str(news.get("materiality") or "medium"), relevance=str(news.get("relevance") or "medium"), confidence=.9 if official else .68, official=official, reference=provenance.get("source_reference"))
        row["candidate_id"] = news.get("candidate_id")
        row["news_event_id"] = news.get("news_event_id") or news.get("canonical_event_identity")
        if row["news_event_id"]:
            row["event_cluster_id"] = row["news_event_id"]
        row["contextual_role"] = news.get("contextual_role")
        row["entity_attribution"] = json.loads(json.dumps(news.get("entity_attribution") or {}))
        rows.append(row)
    canonical_market = normalize_us_market_context(market_context)
    for ticker in ("SPY", "QQQ", "SOXX"):
        value = canonical_ticker(canonical_market, ticker)
        change = value.get("change_pct")
        if isinstance(change, (int, float)):
            market_evidence = evidence_record(symbol, "yfinance", "B", f"{ticker} market context", f"{ticker} change reference {change}", observed_at, "sector" if ticker == "SOXX" else "market_context", published_at=value.get("timestamp"), direction="bullish" if change > 0 else "bearish" if change < 0 else "neutral", confidence=.82, reference=ticker)
            market_evidence["observed_change_pct"] = round(float(change), 6)
            market_evidence["provenance"]["canonical_market_context"] = canonical_market["schema_version"]
            rows.append(market_evidence)
    return deduplicate(rows)


def deduplicate(evidence: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in evidence: groups.setdefault(item["event_cluster_id"], []).append(dict(item))
    output = []
    for cluster in sorted(groups):
        ordered = sorted(groups[cluster], key=lambda x: (x["official_confirmation"], x["quality_score"], x["confidence"]), reverse=True)
        primary, sources = ordered[0], sorted({x["provider"] for x in ordered})
        primary.update({"cross_source_confirmations": sources, "confirmation_count": len(sources)}); output.append(primary)
        for duplicate in ordered[1:]:
            duplicate.update({"duplicate_of": primary["evidence_id"], "counted_in_synthesis": False, "cross_source_confirmations": sources, "confirmation_count": len(sources)}); output.append(duplicate)
    return output


def analyze_coverage(evidence: list[dict[str, Any]], knowledge: dict[str, Any], providers: list[dict[str, Any]]) -> dict[str, Any]:
    counted = [x for x in evidence if x["counted_in_synthesis"]]
    available = {"official": any(x["official_confirmation"] for x in counted),
                 "fundamental": any(x["event_type"] == "fundamental" for x in counted),
                 "macro": any(x["event_type"] == "macro" for x in counted),
                 "sector": any(x["event_type"] in {"sector", "market_context"} for x in counted),
                 "news": any(x["provider_tier"] == "C" for x in counted),
                 "knowledge": knowledge["status"] == "AVAILABLE",
                 "etf": any(x.get("source_reference") in {"SPY", "QQQ", "SOXX"} for x in counted),
                 "options": False, "analyst": False, "insider": False}
    core = ("official", "fundamental", "macro", "sector", "news", "knowledge")
    required = ("sector", "knowledge")
    required_ready = sum(available[key] for key in required)
    required_status = "COMPLETE" if required_ready == len(required) else "PARTIAL" if required_ready else "NONE"
    optional_gaps = [key for key in COVERAGE_KEYS if key not in required and not available[key]]
    return {"score": round(sum(available.values()) / len(COVERAGE_KEYS) * 100, 2),
            "core_score": round(sum(available[x] for x in core) / len(core) * 100, 2),
            "categories": {k: "AVAILABLE" if v else "NOT_CONFIGURED" if k in {"macro", "options", "analyst", "insider"} else "MISSING" for k, v in available.items()},
            "coverage_gap": [x for x in COVERAGE_KEYS if not available[x]],
            "required_categories": list(required),
            "required_category_status": required_status,
            "missing_required_categories": [key for key in required if not available[key]],
            "optional_category_gaps": optional_gaps,
            "missing_sources": [x["provider_id"] for x in providers if x["availability"] in {"NOT_CONFIGURED", "NOT_LICENSED", "SOURCE_FAILED"}],
            "unlicensed_is_failure": False}


def analyze_conflict(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    counted = [x for x in evidence if x["counted_in_synthesis"]]
    owns = lambda x: x.get("direction_ownership") == "company_substantive"
    bullish, bearish = [x for x in counted if x["direction"] == "bullish" and owns(x)], [x for x in counted if x["direction"] == "bearish" and owns(x)]
    material = lambda items: any(x["materiality"] in {"high", "critical"} and x["quality_score"] >= 78 for x in items)
    level = "HIGH" if bullish and bearish and material(bullish) and material(bearish) else "MEDIUM" if bullish and bearish else "LOW"
    return {"level": level, "bullish_evidence_ids": [x["evidence_id"] for x in bullish], "bearish_evidence_ids": [x["evidence_id"] for x in bearish], "method": "material_directional_conflict_not_arithmetic_average"}


def synthesize(evidence: list[dict[str, Any]], coverage: dict[str, Any], conflict: dict[str, Any]) -> dict[str, Any]:
    counted = [x for x in evidence if x["counted_in_synthesis"]]
    direction_owners = [x for x in counted if x.get("direction_ownership") == "company_substantive"]
    contextual = [x for x in counted if x.get("direction_ownership") == "contextual_confirmation_only"]
    supporting, contradicting = [x for x in direction_owners if x["direction"] == "bullish"], [x for x in direction_owners if x["direction"] == "bearish"]
    values = []
    for item in direction_owners:
        sign = 1 if item["direction"] == "bullish" else -1 if item["direction"] == "bearish" else 0
        values.append(sign * item["quality_score"] * item["confidence"] * {"low": .5, "medium": .75, "high": 1., "critical": 1.2}.get(item["materiality"], .5))
    score = round(max(0., min(100., 50 + sum(values) / max(1, len(values)) / 2)), 2)
    high_enough = any(x["quality_score"] >= 65 for x in direction_owners)
    stance = "mixed" if high_enough and supporting and contradicting else "bullish" if high_enough and supporting else "bearish" if high_enough and contradicting else "insufficient_evidence"
    sources = sorted({source for item in counted for source in (item.get("cross_source_confirmations") or [item["provider"]])})
    caps = list(coverage["coverage_gap"])
    if len(sources) <= 1: caps.append("SINGLE_SOURCE_ONLY")
    if conflict["level"] != "LOW": caps.append("CROSS_SOURCE_CONFLICT")
    confidence = max(0., round(min(90., coverage["core_score"] * .65 + min(25, len(sources) * 8) - (20 if conflict["level"] == "HIGH" else 8 if conflict["level"] == "MEDIUM" else 0)), 2))
    return {"research_score": score, "research_stance": stance, "research_confidence": confidence,
            "supporting_evidence": [x["evidence_id"] for x in supporting[:5]],
            "contradicting_evidence": [x["evidence_id"] for x in contradicting[:5]],
            "highest_quality_sources": sorted(sources, key=lambda s: max((x["quality_score"] for x in counted if x["provider"] == s), default=0), reverse=True)[:5],
            "stale_evidence": [x["evidence_id"] for x in counted if x["freshness"] == "stale"],
            "coverage_gap": coverage["coverage_gap"], "confidence_cap_reason": sorted(set(caps)),
            "single_source_direct_stance": stance in {"bullish", "bearish"} and len(sources) <= 1,
            "direction_ownership": {"schema_version": "research_direction_ownership_v1", "company_directional_evidence_ids": [x["evidence_id"] for x in supporting + contradicting], "contextual_evidence_ids": [x["evidence_id"] for x in contextual], "market_context_can_establish_company_direction": False},
            "research_score_is_trade_score": False}


def build_bundle(symbol: str, research: dict[str, Any], market_context: dict[str, Any], observed_at: str) -> dict[str, Any]:
    providers, knowledge = provider_snapshot(research, market_context), company_knowledge(symbol, research)
    evidence = canonical_evidence(symbol, research, market_context, observed_at)
    coverage, conflict = analyze_coverage(evidence, knowledge, providers), analyze_conflict(evidence)
    synthesis = synthesize(evidence, coverage, conflict)
    canonical_market = normalize_us_market_context(market_context)
    research_complete = coverage["required_category_status"]
    market_ready = int(canonical_market["normalization_status"] == "VALID")
    research_ready = int(coverage["required_category_status"] == "COMPLETE")
    readiness = intelligence_readiness_v1(
        runtime_status="SUCCESS", total_symbols=1,
        market_ready=market_ready, history_ready=0, technical_ready=0,
        research_ready=research_ready, baseline_prediction_ready=0,
        full_prediction_ready=0, decision_required_inputs=[],
        applicability={
            "market_data": 1, "research_evidence": 1,
            "historical_data": 0, "technical_evidence": 0,
            "baseline_prediction": 0, "full_prediction": 0,
            "outcome_evaluation": 0,
        },
        zero_statuses={
            "historical_data": "NOT_EVALUATED", "technical_evidence": "NOT_EVALUATED",
            "baseline_prediction": "NOT_EVALUATED", "full_prediction": "NOT_EVALUATED",
            "outcome_evaluation": "NOT_EVALUATED",
        },
        reasons={
            "historical_data": ["NOT_EVALUATED_IN_RESEARCH_BUNDLE"],
            "technical_evidence": ["NOT_EVALUATED_IN_RESEARCH_BUNDLE"],
            "baseline_prediction": ["NOT_EVALUATED_IN_RESEARCH_BUNDLE"],
            "full_prediction": ["NOT_EVALUATED_IN_RESEARCH_BUNDLE"],
        },
    )
    completeness = completeness_v2(
        market_data="COMPLETE" if canonical_market["normalization_status"] == "VALID" else "PARTIAL",
        technical="NOT_EVALUATED", research=research_complete,
        decision_input=readiness["decision_input"]["readiness"], prediction_input="NOT_EVALUATED",
        research_score=coverage["score"], missing_categories=coverage["coverage_gap"],
        readiness=readiness,
    )
    degradation = semantic_degradation(
        provider_market_values=canonical_market["normalization_status"] == "VALID",
        research_market_available=any(x.get("source_reference") in {"SPY", "QQQ", "SOXX"} for x in evidence),
        expected_source_gaps=coverage["coverage_gap"],
        completeness=completeness,
    )
    bundle = {"schema_version": SCHEMA_VERSION, "market": "US", "symbol": symbol.upper(),
              "research_effective_at": observed_at, "provider_registry_version": "us_research_provider_registry_v1",
              "providers": providers, "knowledge": knowledge, "evidence": evidence,
              "canonical_market_context_v2": canonical_market,
              "completeness_v2": completeness,
              "intelligence_readiness_v1": readiness,
              "semantic_degradation": degradation,
              "intelligence_health": intelligence_health(
                  runtime_status="SUCCESS", data_quality_status="HEALTHY" if canonical_market["normalization_status"] == "VALID" else "DEGRADED",
                  research_status=research_complete, prediction_status="NOT_EVALUATED",
                  decision_status="NOT_EVALUATED", degradation=degradation, readiness=readiness,
              ),
              "coverage": coverage, "conflict": conflict, "synthesis": synthesis,
              "decision_context_export": {"research_score": synthesis["research_score"], "research_stance": synthesis["research_stance"], "confidence": synthesis["research_confidence"], "coverage_gap": coverage["coverage_gap"], "conflict_level": conflict["level"], "evidence_ids": [x["evidence_id"] for x in evidence if x["counted_in_synthesis"]], "trade_action": None},
              "decision_engine_boundary": BOUNDARY,
              "continuity": {"source_window": "us_pre_market_2000", "status": "originated"}}
    bundle["research_identity"] = "research_" + stable_hash(bundle)[:24]
    material_news = research.get("material_news") or {}
    news_intelligence = normalize_news(
        material_news.get("items", []), observed_at, material_news.get("evidence_funnel"),
    )
    return _apply_current_news(bundle, bundle, news_intelligence, observed_at)


def _news_evidence(item: dict[str, Any]) -> bool:
    return item.get("provider_tier") == "C" or item.get("provider") == "company_ir"


def _apply_current_news(base: dict[str, Any], current: dict[str, Any],
                        news_intelligence: dict[str, Any], observed_at: str) -> dict[str, Any]:
    """Attach selected current news while preserving Decision ownership."""
    updated = json.loads(json.dumps(base))
    selected_refs = {
        str(item.get("source_reference") or "")
        for item in news_intelligence.get("selected_items", []) if isinstance(item, dict)
    } - {""}
    non_news = [
        item for item in updated.get("evidence", [])
        if isinstance(item, dict) and not _news_evidence(item)
    ]
    selected_evidence = [
        item for item in current.get("evidence", [])
        if isinstance(item, dict) and _news_evidence(item)
        and str(item.get("source_reference") or "") in selected_refs
        and item.get("freshness") != "stale"
    ]
    updated["evidence"] = deduplicate([*non_news, *selected_evidence])
    updated["news_intelligence_v2"] = json.loads(json.dumps(news_intelligence))
    providers = updated.get("providers") or []
    knowledge = updated.get("knowledge") or {"status": "PARTIAL"}
    coverage = analyze_coverage(updated["evidence"], knowledge, providers)
    conflict = analyze_conflict(updated["evidence"])
    synthesis = synthesize(updated["evidence"], coverage, conflict)
    updated.update({"coverage": coverage, "conflict": conflict, "synthesis": synthesis})
    updated["decision_context_export"] = {
        "research_score": synthesis["research_score"],
        "research_stance": synthesis["research_stance"],
        "confidence": synthesis["research_confidence"],
        "coverage_gap": coverage["coverage_gap"],
        "conflict_level": conflict["level"],
        "evidence_ids": [x["evidence_id"] for x in updated["evidence"] if x.get("counted_in_synthesis")],
        "trade_action": None,
    }
    return attach_research_v2(updated, observed_at)


def refresh_current_news(origin: dict[str, Any], current: dict[str, Any], observed_at: str) -> dict[str, Any]:
    """Bridge later-window admitted news into the inherited research bundle."""
    news = current.get("news_intelligence_v2") if isinstance(current.get("news_intelligence_v2"), dict) else {}
    refreshed = _apply_current_news(origin, current, news, observed_at)
    refreshed["research_identity"] = origin.get("research_identity")
    refreshed["continuity"] = json.loads(json.dumps(origin.get("continuity") or {}))
    projection = refreshed.get("research_intelligence_v2") or {}
    projection["origin_research_identity"] = origin.get("research_identity")
    projection["window_research_identity"] = "us_rv2_" + stable_hash({k: v for k, v in projection.items() if k != "window_research_identity"})[:24]
    refreshed["research_intelligence_v2"] = projection
    refreshed["current_news_bridge"] = {
        "schema_version": "us_current_news_bridge_v1",
        "status": "APPLIED" if news.get("selected_count") else "NO_CURRENT_SELECTION",
        "selected_count": int(news.get("selected_count") or 0),
        "decision_layer_action_changed": False,
    }
    return refreshed


def resolve_bundle(archive_root: Path, effective_date: str, symbol: str) -> dict[str, Any] | None:
    candidates = []
    for path in (archive_root / "us" / "us_pre_market_2000" / effective_date).glob("revision-*.json"):
        try: wrapper = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): continue
        if wrapper.get("admitted") is not True or str(wrapper.get("effective_trading_date")) != effective_date: continue
        cards = ((wrapper.get("payload") or {}).get("dashboard_ready_contract") or {}).get("cards") or []
        card = next((x for x in cards if isinstance(x, dict) and str(x.get("symbol") or "").upper() == symbol.upper()), None)
        bundle = card.get("institutional_research") if isinstance(card, dict) else None
        if isinstance(bundle, dict): candidates.append((int(wrapper.get("revision") or 0), str(wrapper.get("admitted_at") or ""), wrapper, bundle))
    if not candidates: return None
    _, _, wrapper, bundle = max(candidates, key=lambda x: (x[0], x[1]))
    inherited = json.loads(json.dumps(bundle))
    if not isinstance(inherited.get("research_intelligence_v2"), dict):
        inherited = attach_research_v2(inherited, inherited.get("research_effective_at") or wrapper.get("admitted_at") or effective_date)
        inherited["v2_compatibility_projection"] = "derived_in_memory_from_immutable_v1_bundle"
    inherited["continuity"] = {"source_window": "us_pre_market_2000", "status": "inherited", "source_snapshot_id": wrapper.get("snapshot_id"), "source_revision": int(wrapper.get("revision") or 0), "source_hash": wrapper.get("source_payload_hash") or wrapper.get("snapshot_id"), "effective_trading_date": effective_date}
    return inherited


def aggregate_bundles(cards: Iterable[dict[str, Any]]) -> dict[str, Any]:
    bundles = [x["institutional_research"] for x in cards if isinstance(x, dict) and isinstance(x.get("institutional_research"), dict)]
    coverage, events = [x["coverage"]["score"] for x in bundles], [sum(y["counted_in_synthesis"] for y in x["evidence"]) for x in bundles]
    v2_coverage = [effective_coverage(x)["score"] for x in bundles]
    summary = {"schema_version": "us_institutional_research_summary_v1", "canonical_research_schema_version": "us_research_intelligence_v2", "bundle_count": len(bundles),
               "research_identities": {x["symbol"]: x["research_identity"] for x in bundles},
               "window_research_identities": {x["symbol"]: (x.get("research_intelligence_v2") or {}).get("window_research_identity") for x in bundles},
               "average_coverage_score": round(sum(v2_coverage) / len(v2_coverage), 2) if v2_coverage else 0.,
               "legacy_average_coverage_score_v1": round(sum(coverage) / len(coverage), 2) if coverage else 0.,
               "average_effective_coverage_score_v2": round(sum(v2_coverage) / len(v2_coverage), 2) if v2_coverage else 0.,
               "coverage_contract": {"schema_version": "us_effective_research_coverage_v2", "denominator": "applicable_weighted_categories", "dashboard_field": "average_effective_coverage_score_v2", "line_field": "average_coverage_score", "parity_required": True},
               "average_deduplicated_event_count": round(sum(events) / len(events), 2) if events else 0.,
               "provider_availability_counts": dict(sorted(Counter(y["availability"] for x in bundles for y in x["providers"]).items())),
               "single_source_stance_symbols": sorted(x["symbol"] for x in bundles if x["synthesis"]["single_source_direct_stance"]),
               "decision_engine_boundary": BOUNDARY}
    summary["research_summary_hash"] = stable_hash(summary); return summary


def review_diagnosis(card: dict[str, Any]) -> dict[str, Any]:
    bundle, prediction, trade = card.get("institutional_research") or {}, str(card.get("prediction_range_result") or "pending"), str(card.get("trade_review_outcome") or "pending_evidence")
    synthesis, coverage = bundle.get("synthesis") or {}, bundle.get("coverage") or {}
    evidence = [x["evidence_id"] for x in bundle.get("evidence", []) if x["counted_in_synthesis"]]
    used = set(synthesis.get("supporting_evidence") or []) | set(synthesis.get("contradicting_evidence") or [])
    failures = (["PREDICTION_RANGE_MISS"] if prediction == "miss" else []) + (["TRADE_OUTCOME_" + trade.upper()] if trade in {"loss", "pending_evidence"} else [])
    v2 = bundle.get("research_intelligence_v2") or {}
    evaluation = v2.get("prediction_evaluation") or {}
    learning = v2.get("no_trade_learning") or {}
    return {"prediction_failure_attribution": failures, "unused_evidence": [x for x in evidence if x not in used], "coverage_gap": (v2.get("effective_coverage") or {}).get("coverage_gap") or coverage.get("coverage_gap") or [], "research_diagnosis": f"研究假設 {((v2.get('hypothesis') or {}).get('state') or '尚未建立')}；預測 {prediction}；交易結果 {trade}。", "prediction_evaluation_v2": evaluation, "no_trade_learning": learning, "next_session_carryforward": v2.get("next_session_carryforward") or {}, "learning_candidate": bool(failures) or bool(learning.get("missed_opportunity_candidate")), "auto_learning_applied": False, "weights_modified": False, "research_identity": bundle.get("research_identity"), "window_research_identity": v2.get("window_research_identity")}


def validate_bundle(bundle: dict[str, Any]) -> list[str]:
    errors = [f"missing:{key}" for key in ("research_identity", "providers", "knowledge", "coverage", "conflict", "synthesis") if not bundle.get(key)]
    if bundle.get("market") != "US": errors.append("market_must_be_us")
    for item in bundle.get("evidence", []):
        for key in ("evidence_id", "event_cluster_id", "provider", "quality_score", "observed_at", "freshness", "event_type", "direction", "materiality", "relevance", "confidence"):
            if item.get(key) is None: errors.append(f"evidence_missing:{key}")
    if (bundle.get("decision_context_export") or {}).get("trade_action") is not None: errors.append("trade_action_exported")
    if any((bundle.get("decision_engine_boundary") or {}).get(key) for key in ("ranking_modified", "scoring_modified", "prediction_modified", "strategy_weights_modified", "auto_learning")): errors.append("decision_boundary_violation")
    projection = bundle.get("research_intelligence_v2")
    if not isinstance(projection, dict): errors.append("research_intelligence_v2_missing")
    else: errors.extend(f"v2:{error}" for error in validate_projection(projection))
    return sorted(set(errors))
