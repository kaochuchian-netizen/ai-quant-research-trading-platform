"""Canonical evidence normalization for the Research Reasoning Engine."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable

EVIDENCE_CLASSES = {
    "market", "macro", "technical", "fundamental", "news", "etf", "adr",
    "chip", "sector", "corporate", "event",
}
DIRECTIONS = {"bullish", "bearish", "neutral", "unavailable"}
COVERAGE = {"AVAILABLE", "PARTIAL", "STALE", "MISSING", "NOT_APPLICABLE"}


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _timestamp(value: Any, field: str) -> str:
    if not value:
        raise ValueError(f"{field} is required")
    text = str(value).replace("Z", "+00:00")
    # Official filings often provide date precision only. Preserve that truthfully
    # as UTC midnight instead of rejecting or inventing an exchange-local clock.
    if len(text) == 10:
        text += "T00:00:00+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.isoformat()


def normalize_evidence(item: dict[str, Any], *, market: str | None = None) -> dict[str, Any]:
    """Normalize existing TW/US evidence without changing its meaning."""
    actual_market = str(item.get("market") or market or "").upper()
    if actual_market not in {"TW", "US"}:
        raise ValueError("market must be TW or US")
    if market and actual_market != market.upper():
        raise ValueError("cross-market evidence is forbidden")
    evidence_class = str(item.get("evidence_class") or item.get("event_type") or "event").lower()
    aliases = {"market_context": "market", "filing": "corporate", "earnings": "fundamental",
               "guidance": "corporate", "regulation": "event", "supply_chain": "sector"}
    evidence_class = aliases.get(evidence_class, evidence_class)
    if evidence_class not in EVIDENCE_CLASSES:
        evidence_class = "event"
    source = str(item.get("source_name") or item.get("provider") or "").strip()
    if not source:
        raise ValueError("source_name is required")
    observed_at = _timestamp(item.get("observed_at"), "observed_at")
    published_at = item.get("published_at")
    if published_at:
        published_at = _timestamp(published_at, "published_at")
    reliability = float(item.get("reliability", item.get("quality_score", 0) / 100))
    confidence = float(item.get("confidence", 0))
    if not 0 <= reliability <= 1 or not 0 <= confidence <= 1:
        raise ValueError("reliability and confidence must be within 0..1")
    direction = str(item.get("direction") or "unavailable").lower()
    if direction not in DIRECTIONS:
        direction = "unavailable"
    coverage = str(item.get("coverage_status") or ("STALE" if item.get("freshness") == "stale" else "AVAILABLE")).upper()
    if coverage not in COVERAGE:
        raise ValueError("invalid coverage_status")
    symbol = str(item.get("symbol_or_scope") or item.get("symbol") or "MARKET").upper()
    normalized = {
        "market": actual_market, "symbol_or_scope": symbol, "evidence_class": evidence_class,
        "source_name": source, "source_type": str(item.get("source_type") or item.get("provider_tier") or "unknown"),
        "source_reference": item.get("source_reference") or item.get("source_url"),
        "published_at": published_at, "observed_at": observed_at,
        "freshness": str(item.get("freshness") or "unknown"), "reliability": round(reliability, 4),
        "confidence": round(confidence, 4), "coverage_status": coverage,
        "summary": str(item.get("summary") or item.get("headline") or "").strip(),
        "direction": direction, "materiality": str(item.get("materiality") or "medium").lower(),
        "duplicate_of": item.get("duplicate_of"),
        "research_role": str(item.get("research_role") or "substantive").lower(),
    }
    if normalized["research_role"] not in {"substantive", "contextual"}:
        raise ValueError("research_role must be substantive or contextual")
    if not normalized["summary"]:
        raise ValueError("summary is required")
    normalized["evidence_id"] = str(item.get("evidence_id") or "rre_" + _hash(normalized)[:20])
    normalized["event_cluster_id"] = str(item.get("event_cluster_id") or "cluster_" + _hash([
        actual_market, symbol, evidence_class, normalized["summary"].lower(), str(published_at)[:10]
    ])[:16])
    return normalized


def normalize_many(items: Iterable[dict[str, Any]], *, market: str) -> list[dict[str, Any]]:
    rows = [normalize_evidence(item, market=market) for item in items]
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["event_cluster_id"]
        incumbent = best.get(key)
        if incumbent is None or (row["reliability"], row["confidence"]) > (incumbent["reliability"], incumbent["confidence"]):
            best[key] = row
    output = []
    for row in rows:
        primary = best[row["event_cluster_id"]]
        copy = dict(row)
        copy["duplicate_of"] = None if copy["evidence_id"] == primary["evidence_id"] else primary["evidence_id"]
        copy["counted_in_reasoning"] = copy["duplicate_of"] is None
        output.append(copy)
    return sorted(output, key=lambda x: (x["symbol_or_scope"], x["event_cluster_id"], x["evidence_id"]))
