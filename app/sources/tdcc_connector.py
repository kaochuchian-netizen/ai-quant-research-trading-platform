"""Read-only TDCC connector readiness fixture."""
from __future__ import annotations
from app.sources.evidence_normalizer import missing_evidence
from app.sources.schemas import SourceFetchRequest, SourceFetchResult
from app.sources.source_client import result

class TdccConnector:
    source_id = "tdcc_shareholding_distribution"
    def fetch(self, request: SourceFetchRequest) -> SourceFetchResult:
        evidence = missing_evidence(self.source_id, request.stock_id, request.stock_name, "TDCC shareholding distribution unavailable in offline sample; chip structure gap is non-fatal.").to_dict()
        return result(request, "unavailable", [evidence], ["tdcc_unavailable"])
