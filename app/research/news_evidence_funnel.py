"""Cross-market research/news funnel primitives.

Pure deterministic helpers.  Provider adapters own retrieval; this module owns
truthful stage accounting and never turns a headline into a trade direction.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Iterable

NEWS_FUNNEL_SCHEMA = "cross_market_research_news_funnel_v1"
NEWS_STAGES = (
    "DISCOVERED", "RETRIEVED", "NORMALIZED", "SYMBOL_ATTRIBUTED",
    "QUALITY_QUALIFIED", "FRESH", "RELEVANT", "MATERIAL", "DEDUPLICATED",
    "ADMITTED", "RRE_USED", "RENDERED",
)

US_ENTITY_ALIASES = {
    "AAPL": ("aapl", "apple"), "AMD": ("amd", "advanced micro devices"),
    "GOOGL": ("googl", "google", "alphabet"), "META": ("meta", "facebook"),
    "NVDA": ("nvda", "nvidia"), "TSLA": ("tsla", "tesla"),
    "TSM": ("tsm", "tsmc", "taiwan semiconductor"),
    "SPCX": ("spcx", "space x", "spacex"),
}
KNOWN_US_ENTITIES = {
    "AAPL": ("aapl", "apple"), "AMD": ("amd", "advanced micro devices"),
    "GOOGL": ("googl", "goog", "google", "alphabet"), "META": ("meta", "facebook"),
    "NVDA": ("nvda", "nvidia"), "TSLA": ("tsla", "tesla"),
    "ABT": ("abt", "abbott", "abbott laboratories"),
    "TSM": ("tsm", "tsmc", "taiwan semiconductor"),
    "ASML": ("asml",), "VZ": ("verizon",), "LMT": ("lockheed", "lockheed martin"),
    "MSFT": ("msft", "microsoft"), "AMZN": ("amzn", "amazon"),
    "PLTR": ("pltr", "palantir"), "ASTS": ("asts", "ast spacemobile"),
    "RKLB": ("rklb", "rocket lab"), "ANTHROPIC": ("anthropic",),
}

MARKET_ROUNDUP_MARKERS = (
    "stocks in focus", "names to watch", "stocks to watch", "on watch",
    "market roundup", "markets move", "market movers", "top stocks",
    "in focus", "these stocks", "s&p", "nasdaq", "dow jones",
    "feature highlights", "featured stocks", "featured names", "top picks",
    "investment ideas", "investor picks", "stocks include", "basket of stocks",
)
MACRO_REACTION_MARKERS = (
    "cpi", "inflation", "fed", "rate hike", "rate cut", "interest rates",
    "payrolls", "jobs report", "treasury yields", "market selloff", "market rally",
)
MATERIAL_RELATIONSHIP_PATTERNS = (
    (r"\bpartners? with\b|\bpartnership\b", "partnership"),
    (r"\bteams? up with\b", "teams_up"),
    (r"\bcollaborat(?:es?|ion)\b", "collaboration"),
    (r"\b(?:signs?|signed) (?:an? )?(?:commercial )?agreement\b", "agreement"),
    (r"\b(?:wins?|awards?|signs?) (?:an? )?contract\b|\bcontract with\b", "contract"),
    (r"\bsuppl(?:y|ies|ier)\b", "supplier"),
    (r"\bcustomer(?:s)?\b", "customer"),
    (r"\bsupply deal\b", "supply_deal"),
    (r"\bjoint venture\b|\bjv\b", "joint_venture"),
    (r"\bacquires?\b|\bacquisition of\b", "acquisition"),
    (r"\binvests? in\b|\bstrategic investment in\b|\bequity stake in\b|\bownership interest in\b", "strategic_investment"),
    (r"\bcapacity (?:agreement|expansion|commitment|equipment|supply)\b", "capacity"),
)
TICKER_STOPWORDS = {"AI", "CPI", "ETF", "CEO", "CFO", "IPO", "US", "USA"}
MAX_LEDGER_CANDIDATES_PER_SYMBOL_WINDOW = 64


def _stable_id(prefix: str, value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def normalized_event_topic(title: str) -> str:
    """Return a publisher-independent topic without storing article content."""
    text = re.sub(r"\s+(?:[-|]\s*)?(?:reuters|bloomberg|cnbc|marketwatch|yahoo finance)$", "", title, flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def canonical_news_event_id(
    *, title: str, published_at: Any, attribution: dict[str, Any] | None = None,
    event_type: str | None = None, related_symbols: Iterable[str] = (),
) -> str:
    """Group syndicated reports while keeping distinct updates separate."""
    attribution = attribution or {}
    subject = attribution.get("primary_subject") or attribution.get("target_symbol")
    relationship = attribution.get("relationship_type")
    bucket = str(published_at or "")[:10]
    return _stable_id("news_evt_", [
        normalized_event_topic(title), str(event_type or "news").lower(), subject,
        relationship, sorted({str(value).upper() for value in related_symbols if value}), bucket,
    ])


def _alias_matches(text: str, aliases: Iterable[str]) -> list[str]:
    return [
        alias for alias in aliases
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text)
    ]


def _headline_tickers(title: str) -> set[str]:
    """Extract explicit ticker-like tokens without depending on the watchlist."""
    return {
        value for value in re.findall(r"(?<![A-Za-z0-9])([A-Z]{2,5})(?![A-Za-z0-9])", title)
        if value not in TICKER_STOPWORDS
    }


def _material_relationship(title_lower: str) -> str | None:
    return next((name for pattern, name in MATERIAL_RELATIONSHIP_PATTERNS if re.search(pattern, title_lower)), None)


def _comparative_reference(title_lower: str, aliases: Iterable[str]) -> bool:
    target = "(?:" + "|".join(re.escape(value) for value in aliases) + ")"
    comparison = r"(?:above|over|top(?:s|ping|ped)?|surpass(?:es|ed)?|exceed(?:s|ed)?|more than|higher than)"
    patterns = (
        rf"\b(?:chase|chases|follow|follows|copy|copies)\b.+\b{target}\b.+\b(?:playbook|model|strategy)\b",
        rf"\b(?:like|versus|vs\.?|compared with|compared to)\b.+\b{target}\b",
        rf"\b(?:valuation|worth|market value)\b.+\b{comparison}\b.+\b{target}\b",
        rf"\b{comparison}\b.+\b{target}\b.+\b(?:valuation|worth|market value)\b",
        rf"\b(?:benchmark(?:ed)?|comparison)\b.+\b(?:against|with|to)\b.+\b{target}\b",
    )
    return any(re.search(pattern, title_lower) for pattern in patterns)


def _entity_attribution(item: dict[str, Any], *, symbol: str, title: str, summary: str) -> dict[str, Any]:
    """Classify company attribution without promoting roundup/co-mention noise.

    V3 deliberately separates provider association from editorial subject
    ownership.  A ticker in ``relatedTickers`` or a multi-name headline is not
    sufficient to make the target company the primary subject.
    """
    target = symbol.upper()
    aliases = US_ENTITY_ALIASES.get(target, (target.lower(),))
    title_lower, summary_lower = title.lower(), summary.lower()
    related = item.get("relatedTickers") or item.get("related_tickers") or item.get("symbols") or []
    if isinstance(related, str):
        related = [related]
    related = {str(value).upper() for value in related if value}
    title_matches = _alias_matches(title_lower, aliases)
    summary_matches = _alias_matches(summary_lower, aliases)
    competing: set[str] = set()
    matched_entities: list[str] = [target] if title_matches else []
    for ticker, entity_aliases in KNOWN_US_ENTITIES.items():
        if ticker == target:
            continue
        if _alias_matches(title_lower, entity_aliases):
            competing.add(ticker)
            matched_entities.append(ticker)
    title_tickers = _headline_tickers(title)
    for ticker in title_tickers | related:
        if ticker != target:
            competing.add(ticker)
            matched_entities.append(ticker)
    roundup = any(marker in title_lower for marker in MARKET_ROUNDUP_MARKERS)
    macro_reaction = any(marker in title_lower for marker in MACRO_REACTION_MARKERS)
    comparative = bool(title_matches) and _comparative_reference(title_lower, aliases)
    relationship = _material_relationship(title_lower)
    multi_ticker = len(related) >= 3 or len(competing) >= 2
    if comparative:
        accepted, attribution_class, framing_class = False, "COMPARATIVE_REFERENCE", "COMPARATIVE_REFERENCE"
        reason, method = "COMPARATIVE_REFERENCE_NOT_COMPANY_EVENT", "headline_comparative_subject_structure"
        primary_subject, relationship_type = None, None
    elif roundup or (multi_ticker and not relationship):
        accepted, attribution_class, framing_class = False, "MARKET_ROUNDUP", "MULTI_TICKER_ROUNDUP"
        reason, method = "MARKET_ROUNDUP_NOT_COMPANY_EVIDENCE", "market_or_multi_ticker_frame"
        primary_subject, relationship_type = "market_or_multi_entity", None
    elif macro_reaction and (competing or len(related) > 1):
        accepted, attribution_class, framing_class = False, "CONTEXTUAL_MENTION", "MARKET_MACRO_REACTION"
        reason, method = "MARKET_MACRO_REACTION_NOT_COMPANY_EVENT", "macro_multi_company_reaction_frame"
        primary_subject, relationship_type = "market_macro", None
    elif title_matches and competing and relationship:
        accepted, attribution_class, framing_class = True, "MATERIAL_CO_SUBJECT", "MATERIAL_RELATIONSHIP_EVENT"
        reason, method = "MATERIAL_RELATIONSHIP_CO_SUBJECT", "title_relationship_structure"
        primary_subject, relationship_type = target, relationship
    elif title_matches and not competing:
        accepted, attribution_class, framing_class = True, "PRIMARY_SUBJECT", "PRIMARY_COMPANY_EVENT"
        reason, method = "PRIMARY_SUBJECT_TITLE_MATCH", "explicit_title_entity_match"
        primary_subject, relationship_type = target, None
    elif target in related and len(related) <= 2:
        accepted, attribution_class, framing_class = True, "MATERIAL_CO_SUBJECT", "MATERIAL_RELATIONSHIP_EVENT"
        reason, method = "PROVIDER_RELATED_TICKER", "bounded_provider_relationship_metadata"
        primary_subject, relationship_type = target, "provider_related_ticker"
    elif title_matches and competing:
        accepted, attribution_class, framing_class = False, "AMBIGUOUS", "AMBIGUOUS_SUBJECT"
        reason, method = "AMBIGUOUS_PRIMARY_SUBJECT", "competing_title_entities_without_relationship"
        primary_subject, relationship_type = None, None
    elif summary_matches:
        accepted, attribution_class, framing_class = False, "CONTEXTUAL_MENTION", "CONTEXTUAL_MENTION"
        reason, method = "WEAK_CONTEXTUAL_COMENTION", "summary_only_entity_match"
        primary_subject, relationship_type = None, None
    else:
        accepted, attribution_class, framing_class = False, "REJECTED", "NO_TARGET_RELATIONSHIP"
        reason, method = "SYMBOL_ATTRIBUTION_FAILED", "no_entity_evidence"
        primary_subject, relationship_type = None, None
    return {
        "accepted": accepted, "reason_code": reason, "method": method,
        "target_symbol": target, "matched_aliases": sorted(set(title_matches + summary_matches)),
        "provider_related_tickers": sorted(related), "competing_primary_symbols": sorted(competing),
        "competing_entities": sorted(competing),
        "contract_version": "us_entity_subject_resolution_v5",
        "attribution_class": attribution_class,
        "attribution_reason": reason,
        "matched_entities": sorted(set(matched_entities)),
        "competing_entities": sorted(competing),
        "related_ticker_metadata": sorted(related),
        "primary_subject": primary_subject,
        "relationship_type": relationship_type,
        "framing_class": framing_class,
        "headline_subject": primary_subject,
        "target_entity": target,
        "quality": "high" if attribution_class == "PRIMARY_SUBJECT" else "medium" if accepted else "rejected",
        "classification": attribution_class,
        "reason": reason,
        "confidence": "high" if attribution_class == "PRIMARY_SUBJECT" else "medium" if accepted else "rejected",
        "status": "ACCEPTED" if accepted else "REJECTED",
    }


def validate_entity_attribution_contract(value: dict[str, Any]) -> list[str]:
    """Fail closed on internally contradictory subject-resolution provenance."""
    errors: list[str] = []
    required = (
        "classification", "reason", "target_symbol", "target_entity", "headline_subject",
        "competing_entities", "relationship_type", "framing_class", "confidence", "status",
    )
    errors.extend(f"missing:{field}" for field in required if field not in value)
    framing = value.get("framing_class")
    classification = value.get("classification") or value.get("attribution_class")
    accepted = value.get("accepted") is True or value.get("status") == "ACCEPTED"
    non_company_frames = {
        "MULTI_COMPANY_EVENT", "MULTI_TICKER_ROUNDUP", "MARKET_MACRO_REACTION",
        "SECTOR_ROUNDUP", "COMPARATIVE_REFERENCE", "CONTEXTUAL_MENTION",
        "AMBIGUOUS_SUBJECT", "NO_TARGET_RELATIONSHIP",
    }
    if framing in non_company_frames and (accepted or classification == "PRIMARY_SUBJECT"):
        errors.append("non_company_frame_promoted_to_company_evidence")
    if classification == "PRIMARY_SUBJECT" and framing != "PRIMARY_COMPANY_EVENT":
        errors.append("primary_subject_frame_mismatch")
    if classification == "MATERIAL_CO_SUBJECT" and framing != "MATERIAL_RELATIONSHIP_EVENT":
        errors.append("material_relationship_frame_mismatch")
    if accepted and not value.get("reason"):
        errors.append("accepted_without_reason")
    return sorted(set(errors))


def validate_entity_attribution_semantics(
    item: dict[str, Any], *, symbol: str, title: str, summary: str, attribution: dict[str, Any]
) -> list[str]:
    """Recompute subject resolution so internally consistent semantic mutations fail."""
    expected = _entity_attribution(item, symbol=symbol, title=title, summary=summary)
    fields = (
        "accepted", "attribution_class", "reason_code", "framing_class",
        "relationship_type", "primary_subject", "competing_entities",
    )
    errors = [f"semantic_mismatch:{field}" for field in fields if attribution.get(field) != expected.get(field)]
    errors.extend(validate_entity_attribution_contract(attribution))
    return sorted(set(errors))


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _nested(raw: dict[str, Any]) -> dict[str, Any]:
    content = raw.get("content")
    return content if isinstance(content, dict) else raw


def _url(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("url")
    text = str(value or "").strip()
    return text or None


def normalize_yfinance_news(
    raw_items: Iterable[Any], *, symbol: str, observed_at: str,
    retrieval_error: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Normalize current nested and legacy Yahoo payloads with exact counts."""
    raw = list(raw_items or [])
    counts = {stage: 0 for stage in NEWS_STAGES}
    reasons: dict[str, int] = {}
    counts["DISCOVERED"] = counts["RETRIEVED"] = len(raw)
    reference = parse_time(observed_at) or datetime.now(timezone.utc)
    candidates: list[dict[str, Any]] = []
    candidate_records: list[dict[str, Any]] = []

    def reject(code: str) -> None:
        reasons[code] = reasons.get(code, 0) + 1

    for candidate_index, value in enumerate(raw):
        if not isinstance(value, dict):
            reject("PARSER_ERROR")
            candidate_records.append({
                "record_version": "us_news_candidate_metadata_v1", "market": "US", "symbol": symbol.upper(),
                "candidate_id": _stable_id("news_cand_", [symbol.upper(), "invalid", candidate_index, observed_at]),
                "admission_status": "REJECTED", "rejection_reason": "PARSER_ERROR",
            })
            continue
        item = _nested(value)
        title = str(item.get("title") or "").strip()
        provider_obj = item.get("provider") if isinstance(item.get("provider"), dict) else {}
        publisher = str(item.get("publisher") or provider_obj.get("displayName") or "").strip()
        published = item.get("pubDate") or item.get("providerPublishTime") or item.get("published_at")
        source_url = _url(item.get("canonicalUrl") or item.get("clickThroughUrl") or item.get("link") or item.get("url"))
        candidate_base = {
            "record_version": "us_news_candidate_metadata_v1", "market": "US", "symbol": symbol.upper(),
            "headline": title or None, "publisher": publisher or None, "published_at": published,
            "source_reference": source_url, "fetched_at": observed_at,
        }
        candidate_base["candidate_id"] = _stable_id("news_cand_", [symbol.upper(), title, published, source_url])
        if not title or not published or not source_url:
            reject("PARSER_ERROR")
            candidate_records.append({**candidate_base, "admission_status": "REJECTED", "rejection_reason": "PARSER_ERROR"})
            continue
        counts["NORMALIZED"] += 1
        summary = re.sub(r"<[^>]+>", " ", str(item.get("summary") or item.get("description") or ""))
        attribution = _entity_attribution(item, symbol=symbol, title=title, summary=summary)
        contextual_admission = False
        if not attribution["accepted"]:
            reject(str(attribution["reason_code"]))
            candidate_records.append({
                **candidate_base, "entity_attribution": attribution,
                "news_event_id": canonical_news_event_id(title=title, published_at=published, attribution=attribution, related_symbols=attribution.get("related_ticker_metadata") or []),
                "admission_status": "REJECTED", "rejection_reason": attribution["reason_code"],
            })
            continue
        counts["SYMBOL_ATTRIBUTED"] += 1
        # Yahoo Finance is contextual Tier 3. Official/IR evidence remains a
        # separate higher-priority adapter and is never impersonated here.
        publisher_resolution_status = "resolved" if publisher else "unresolved"
        if not publisher:
            reject("PUBLISHER_UNRESOLVED")
            publisher = "原始來源未解析"
        counts["QUALITY_QUALIFIED"] += 1
        published_at = parse_time(published)
        if published_at is None:
            reject("PARSER_ERROR")
            candidate_records.append({**candidate_base, "entity_attribution": attribution, "admission_status": "REJECTED", "rejection_reason": "PARSER_ERROR"})
            continue
        age_hours = (reference - published_at).total_seconds() / 3600
        if age_hours < 0:
            reject("OUTSIDE_WINDOW")
            candidate_records.append({**candidate_base, "entity_attribution": attribution, "admission_status": "REJECTED", "rejection_reason": "OUTSIDE_WINDOW"})
            continue
        if age_hours > 72:
            reject("STALE")
            candidate_records.append({**candidate_base, "entity_attribution": attribution, "admission_status": "REJECTED", "rejection_reason": "STALE"})
            continue
        counts["FRESH"] += 1
        counts["RELEVANT"] += 1
        content_type = str(item.get("contentType") or "STORY").upper()
        if content_type not in {"STORY", "PRESS_RELEASE", "VIDEO"}:
            reject("LOW_MATERIALITY")
            candidate_records.append({**candidate_base, "entity_attribution": attribution, "admission_status": "REJECTED", "rejection_reason": "LOW_MATERIALITY"})
            continue
        counts["MATERIAL"] += 1
        news_event_id = canonical_news_event_id(
            title=title, published_at=published, attribution=attribution,
            event_type=content_type, related_symbols=attribution.get("related_ticker_metadata") or [],
        )
        normalized = {
            "source": publisher, "publisher": publisher,
            "published_at": published_at.isoformat().replace("+00:00", "Z"),
            "source_url": source_url, "english_headline": title,
            "chinese_translation": "英文標題摘要：" + title,
            "english_excerpt": None,
            "chinese_summary": "依可取得標題整理，未複製完整文章。",
            "investment_reading": "新聞供事件脈絡參考，不單獨決定評等。",
            "source_quality": "recognized_financial_media",
            "source_tier": 3, "official_source": False,
            "symbol_attributed": attribution["accepted"], "contextual_admission": contextual_admission,
            "contextual_role": "CONTEXTUALIZE" if contextual_admission else None,
            "relevance": "medium",
            "materiality": "medium", "freshness": "fresh",
            "direction": "unavailable", "direction_status": "NOT_EVALUATED",
            "entity_attribution": attribution,
            "publisher_resolution_status": publisher_resolution_status,
            "discovery_channel": "YAHOO_FINANCE",
            "candidate_id": candidate_base["candidate_id"], "news_event_id": news_event_id,
            "canonical_event_identity": news_event_id, "dedupe_key": news_event_id,
            "related_symbols": attribution.get("related_ticker_metadata") or [],
        }
        candidates.append(normalized)
        candidate_records.append({
            **candidate_base, "entity_attribution": attribution, "news_event_id": news_event_id,
            "canonical_event_identity": news_event_id, "source_tier": 3,
            "source_quality": "recognized_financial_media", "event_type": content_type.lower(),
            "materiality": "medium", "relevance": "medium", "freshness": "fresh",
            "admission_status": "ADMITTED", "rejection_reason": None,
        })
    unique: dict[str, dict[str, Any]] = {}
    for item in candidates:
        key = str(item["dedupe_key"])
        if key in unique:
            reject("DUPLICATE")
            primary = unique[key]
            primary.setdefault("duplicate_sources", []).append({"publisher": item.get("publisher"), "source_reference": item.get("source_url")})
            for record in candidate_records:
                if record.get("candidate_id") == item.get("candidate_id"):
                    record.update({"admission_status": "REJECTED", "rejection_reason": "DUPLICATE", "duplicate_group": key})
                    break
        else:
            item["duplicate_sources"] = []
            unique[key] = item
    admitted = list(unique.values())
    counts["DEDUPLICATED"] = counts["ADMITTED"] = len(admitted)
    if retrieval_error and not admitted:
        reject("RETRIEVAL_FAILED")
        absence = "NEWS_RETRIEVAL_FAILED"
    elif admitted:
        absence = "NEWS_ADMITTED_NOT_SELECTED"
    elif reasons.get("STALE") and not any(code != "STALE" for code in reasons):
        absence = "STALE_ONLY"
    elif raw:
        absence = "NEWS_DISCOVERED_BUT_FILTERED"
    else:
        absence = "NO_RELEVANT_NEWS_DISCOVERED"
    diagnostic = {
        "schema_version": NEWS_FUNNEL_SCHEMA, "count_semantics": "EXACT",
        "market": "US", "symbol": symbol.upper(), "stages": counts,
        "rejection_reasons": dict(sorted(reasons.items())),
        "absence_state": absence,
        "source_preference": ["official", "SEC", "company_ir", "company_newsroom", "recognized_financial_media"],
        "retrieval": {"status": "PARTIAL" if retrieval_error and admitted else "FAILED" if retrieval_error else "SUCCESS", "reason_code": "PARTIAL_PROVIDER_FAILURE" if retrieval_error and admitted else "RETRIEVAL_FAILED" if retrieval_error else None},
        "candidate_records": candidate_records[:MAX_LEDGER_CANDIDATES_PER_SYMBOL_WINDOW],
        "candidate_retention": {"limit": MAX_LEDGER_CANDIDATES_PER_SYMBOL_WINDOW, "content": "metadata_only_no_article_body", "truncated": len(candidate_records) > MAX_LEDGER_CANDIDATES_PER_SYMBOL_WINDOW},
    }
    return admitted, diagnostic


def validate_funnel(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    stages = value.get("stages") if isinstance(value.get("stages"), dict) else {}
    if value.get("schema_version") != NEWS_FUNNEL_SCHEMA:
        errors.append("schema")
    if value.get("count_semantics") != "EXACT":
        errors.append("count_semantics")
    if any(not isinstance(stages.get(stage), int) or stages.get(stage, -1) < 0 for stage in NEWS_STAGES):
        errors.append("counts")
    if stages.get("RENDERED", 0) > stages.get("RRE_USED", 0) or stages.get("RRE_USED", 0) > stages.get("ADMITTED", 0):
        errors.append("downstream_order")
    return errors


def with_downstream_counts(value: dict[str, Any], *, rre_used: int, rendered: int) -> dict[str, Any]:
    """Finalize selection/render accounting without mutating provider telemetry."""
    output = {**value, "stages": dict(value.get("stages") or {}),
              "rejection_reasons": dict(value.get("rejection_reasons") or {})}
    admitted = int(output["stages"].get("ADMITTED") or 0)
    used = max(0, min(int(rre_used), admitted))
    visible = max(0, min(int(rendered), used))
    output["stages"]["RRE_USED"] = used
    output["stages"]["RENDERED"] = visible
    if admitted > used:
        output["rejection_reasons"]["RRE_NOT_SELECTED"] = admitted - used
    if used > visible:
        output["rejection_reasons"]["RENDERER_NOT_SELECTED"] = used - visible
    if visible:
        output["absence_state"] = "NEWS_SELECTED_AND_RENDERED"
    elif used:
        output["absence_state"] = "NEWS_SELECTED_NOT_RENDERED"
    elif admitted:
        output["absence_state"] = "NEWS_ADMITTED_NOT_SELECTED"
    output["rejection_reasons"] = dict(sorted(output["rejection_reasons"].items()))
    return output
