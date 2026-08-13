"""Cross-market research/news funnel primitives.

Pure deterministic helpers.  Provider adapters own retrieval; this module owns
truthful stage accounting and never turns a headline into a trade direction.
"""
from __future__ import annotations

from datetime import datetime, timezone
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
}
KNOWN_US_ENTITIES = {
    "AAPL": ("aapl", "apple"), "AMD": ("amd", "advanced micro devices"),
    "GOOGL": ("googl", "goog", "google", "alphabet"), "META": ("meta", "facebook"),
    "NVDA": ("nvda", "nvidia"), "TSLA": ("tsla", "tesla"),
    "ABT": ("abt", "abbott", "abbott laboratories"), "TSM": ("tsm", "taiwan semiconductor"),
}


def _entity_attribution(item: dict[str, Any], *, symbol: str, title: str, summary: str) -> dict[str, Any]:
    """Require primary-subject evidence, not a weak body-text co-mention."""
    target = symbol.upper()
    aliases = US_ENTITY_ALIASES.get(target, (target.lower(),))
    title_lower, summary_lower = title.lower(), summary.lower()
    related = item.get("relatedTickers") or item.get("related_tickers") or item.get("symbols") or []
    if isinstance(related, str):
        related = [related]
    related = {str(value).upper() for value in related if value}
    title_matches = [alias for alias in aliases if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", title_lower)]
    summary_matches = [alias for alias in aliases if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", summary_lower)]
    competing = []
    for ticker, entity_aliases in KNOWN_US_ENTITIES.items():
        if ticker == target:
            continue
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", title_lower) for alias in entity_aliases):
            competing.append(ticker)
    if target in related:
        accepted, reason, method = True, "PROVIDER_RELATED_TICKER", "provider_relationship_metadata"
    elif title_matches and not competing:
        accepted, reason, method = True, "PRIMARY_SUBJECT_TITLE_MATCH", "explicit_title_entity_match"
    elif title_matches and competing:
        accepted, reason, method = False, "AMBIGUOUS_PRIMARY_SUBJECT", "competing_title_entities_without_relationship"
    elif summary_matches:
        accepted, reason, method = False, "WEAK_CONTEXTUAL_COMENTION", "summary_only_entity_match"
    else:
        accepted, reason, method = False, "SYMBOL_ATTRIBUTION_FAILED", "no_entity_evidence"
    return {
        "accepted": accepted, "reason_code": reason, "method": method,
        "target_symbol": target, "matched_aliases": sorted(set(title_matches + summary_matches)),
        "provider_related_tickers": sorted(related), "competing_primary_symbols": sorted(competing),
        "contract_version": "us_entity_attribution_v2",
    }


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

    def reject(code: str) -> None:
        reasons[code] = reasons.get(code, 0) + 1

    for value in raw:
        if not isinstance(value, dict):
            reject("PARSER_ERROR")
            continue
        item = _nested(value)
        title = str(item.get("title") or "").strip()
        provider_obj = item.get("provider") if isinstance(item.get("provider"), dict) else {}
        publisher = str(item.get("publisher") or provider_obj.get("displayName") or "").strip()
        published = item.get("pubDate") or item.get("providerPublishTime") or item.get("published_at")
        source_url = _url(item.get("canonicalUrl") or item.get("clickThroughUrl") or item.get("link") or item.get("url"))
        if not title or not publisher or not published or not source_url:
            reject("PARSER_ERROR")
            continue
        counts["NORMALIZED"] += 1
        summary = re.sub(r"<[^>]+>", " ", str(item.get("summary") or item.get("description") or ""))
        attribution = _entity_attribution(item, symbol=symbol, title=title, summary=summary)
        if not attribution["accepted"]:
            reject(str(attribution["reason_code"]))
            continue
        counts["SYMBOL_ATTRIBUTED"] += 1
        # Yahoo Finance is contextual Tier 3. Official/IR evidence remains a
        # separate higher-priority adapter and is never impersonated here.
        counts["QUALITY_QUALIFIED"] += 1
        published_at = parse_time(published)
        if published_at is None:
            reject("PARSER_ERROR")
            continue
        age_hours = (reference - published_at).total_seconds() / 3600
        if age_hours < 0:
            reject("OUTSIDE_WINDOW")
            continue
        if age_hours > 72:
            reject("STALE")
            continue
        counts["FRESH"] += 1
        counts["RELEVANT"] += 1
        content_type = str(item.get("contentType") or "STORY").upper()
        if content_type not in {"STORY", "PRESS_RELEASE", "VIDEO"}:
            reject("LOW_MATERIALITY")
            continue
        counts["MATERIAL"] += 1
        candidates.append({
            "source": publisher, "publisher": publisher,
            "published_at": published_at.isoformat().replace("+00:00", "Z"),
            "source_url": source_url, "english_headline": title,
            "chinese_translation": "英文標題摘要：" + title,
            "english_excerpt": None,
            "chinese_summary": "依可取得標題整理，未複製完整文章。",
            "investment_reading": "新聞供事件脈絡參考，不單獨決定評等。",
            "source_quality": "recognized_financial_media",
            "source_tier": 3, "official_source": False,
            "symbol_attributed": True, "relevance": "medium",
            "materiality": "medium", "freshness": "fresh",
            "direction": "unavailable", "direction_status": "NOT_EVALUATED",
            "entity_attribution": attribution,
            "dedupe_key": source_url,
        })
    unique: dict[str, dict[str, Any]] = {}
    for item in candidates:
        key = str(item["dedupe_key"])
        if key in unique:
            reject("DUPLICATE")
        else:
            unique[key] = item
    admitted = list(unique.values())
    counts["DEDUPLICATED"] = counts["ADMITTED"] = len(admitted)
    if retrieval_error:
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
        "retrieval": {"status": "FAILED" if retrieval_error else "SUCCESS", "reason_code": "RETRIEVAL_FAILED" if retrieval_error else None},
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
