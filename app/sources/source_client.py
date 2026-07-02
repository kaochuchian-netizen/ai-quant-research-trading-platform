"""Generic read-only source connector client."""
from __future__ import annotations
from typing import Protocol
from app.sources.evidence_normalizer import RETRIEVED_AT
from app.sources.endpoint_registry import endpoint_by_id
from app.sources.schemas import CONNECTOR_HEALTH_SCHEMA_VERSION, FETCH_RESULT_SCHEMA_VERSION, SourceConnectorHealth, SourceEvidenceBatch, SourceFetchRequest, SourceFetchResult

class ReadOnlySourceConnector(Protocol):
    source_id: str
    def fetch(self, request: SourceFetchRequest) -> SourceFetchResult: ...

def health(source_id: str, status: str, evidence_count: int, missing_reason: str | None = None, error_message: str | None = None) -> SourceConnectorHealth:
    endpoint = endpoint_by_id()[source_id]
    return SourceConnectorHealth(CONNECTOR_HEALTH_SCHEMA_VERSION, source_id, endpoint.provider, status, True, RETRIEVED_AT, missing_reason, error_message, evidence_count, endpoint.usage_policy)

def result(request: SourceFetchRequest, status: str, evidence: list[dict], missing_reasons: list[str] | None = None, error_message: str | None = None) -> SourceFetchResult:
    h = health(request.source_id, status, len(evidence), (missing_reasons or [None])[0], error_message)
    batch = SourceEvidenceBatch("source_evidence_batch_v1", request.source_id, evidence, list(missing_reasons or []))
    return SourceFetchResult(FETCH_RESULT_SCHEMA_VERSION, request.to_dict(), h.to_dict(), batch.to_dict())
