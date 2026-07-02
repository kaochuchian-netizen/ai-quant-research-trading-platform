"""Normalize connector records into SourceEvidence."""
from __future__ import annotations
from typing import Any
from app.sources.endpoint_registry import endpoint_by_id
from app.sources.schemas import SOURCE_EVIDENCE_SCHEMA_VERSION, SourceEvidence

RETRIEVED_AT = "2026-07-02T00:00:00Z"

def normalize_evidence(source_id: str, stock_id: str, stock_name: str, raw: dict[str, Any]) -> SourceEvidence:
    endpoint = endpoint_by_id()[source_id]
    evidence_type = str(raw.get("evidence_type") or endpoint.evidence_type)
    evidence_id = str(raw.get("evidence_id") or f"{source_id}:{stock_id}:{raw.get('event_date', 'unknown')}")
    source_conflict = raw.get("source_conflict")
    normalized = dict(raw.get("normalized_fields") or {})
    if source_conflict:
        normalized["source_conflict"] = source_conflict
        normalized["authoritative_source"] = "official_primary_source"
    return SourceEvidence(
        SOURCE_EVIDENCE_SCHEMA_VERSION,
        evidence_id,
        source_id,
        endpoint.provider,
        endpoint.category,
        endpoint.priority,
        str(stock_id),
        str(stock_name),
        str(raw.get("event_date", "2026-07-02")),
        str(raw.get("retrieved_at", RETRIEVED_AT)),
        str(raw.get("title", endpoint.endpoint_name)),
        str(raw.get("summary", endpoint.notes)),
        dict(raw.get("raw_fields") or raw),
        normalized,
        raw.get("source_url") or endpoint.url,
        evidence_type,
        float(raw.get("quality_score", 0.7)),
        str(raw.get("noise_risk", "medium")),
        dict(raw.get("lineage") or {"connector": source_id, "offline_sample": True}),
        list(raw.get("usage_policy") or endpoint.usage_policy),
    )

def missing_evidence(source_id: str, stock_id: str, stock_name: str, reason: str) -> SourceEvidence:
    return normalize_evidence(source_id, stock_id, stock_name, {"evidence_id": f"{source_id}:{stock_id}:missing", "event_date": "2026-07-02", "title": f"{source_id} unavailable", "summary": reason, "evidence_type": "missing_source_notice", "quality_score": 0.0, "noise_risk": "medium", "normalized_fields": {"missing_reason": reason, "available": False}})
