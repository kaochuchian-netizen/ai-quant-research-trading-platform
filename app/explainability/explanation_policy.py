"""Deterministic explanation policy rules."""
from __future__ import annotations
from typing import Any
NEWS_NO_RAISE_POLICY = "news-only evidence cannot independently raise rating"
YFINANCE_NO_RAISE_POLICY = "yfinance external context cannot raise rating independently"
FINMIND_NO_RAISE_POLICY = "FinMind aggregated data cannot raise rating independently or replace official primary sources"

def official_source_wins(evidence: dict[str, Any]) -> bool:
    conflict = evidence.get("normalized_fields", {}).get("source_conflict")
    return isinstance(conflict, dict) and conflict.get("official_source_wins") is True

def readiness_from_sources(has_official: bool, has_finmind: bool, missing_primary: bool) -> str:
    if has_official and not missing_primary: return "ready"
    if has_finmind: return "partial"
    return "insufficient" if missing_primary else "partial"

def confidence_cap_reason(readiness: str, missing_sources: list[str]) -> str | None:
    if readiness == "ready": return None
    if readiness == "partial": return "partial source coverage: aggregated or fallback evidence exists but primary confirmation is missing"
    return "limited by missing primary sources: " + ", ".join(missing_sources)

def policy_notes() -> list[str]:
    return [NEWS_NO_RAISE_POLICY, YFINANCE_NO_RAISE_POLICY, FINMIND_NO_RAISE_POLICY, "official source wins when FinMind conflicts with official source", "connector unavailable is non-fatal"]
