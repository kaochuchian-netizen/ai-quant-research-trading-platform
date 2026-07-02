"""Read-only TPEx readiness connector."""
from __future__ import annotations
from app.sources.evidence_normalizer import missing_evidence
from app.sources.schemas import SourceFetchRequest, SourceFetchResult
from app.sources.source_client import result

class TpexOpenApiConnector:
    source_id = "tpex_openapi_readiness"
    def fetch(self, request: SourceFetchRequest) -> SourceFetchResult:
        evidence = missing_evidence(self.source_id, request.stock_id, request.stock_name, "TPEx source represented but not required for listed 2330 offline sample.").to_dict()
        return result(request, "skipped", [evidence], ["tpex_not_applicable_for_sample"])
