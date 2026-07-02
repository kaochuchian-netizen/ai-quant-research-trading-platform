"""Read-only TWSE OpenAPI connector fixtures for explainability V1."""
from __future__ import annotations
from app.sources.evidence_normalizer import missing_evidence, normalize_evidence
from app.sources.schemas import SourceFetchRequest, SourceFetchResult
from app.sources.source_client import result

class TwseOpenApiConnector:
    def __init__(self, source_id: str): self.source_id = source_id
    def fetch(self, request: SourceFetchRequest) -> SourceFetchResult:
        if self.source_id == "twse_monthly_revenue":
            evidence = normalize_evidence(self.source_id, request.stock_id, request.stock_name, {"evidence_id": f"twse_monthly_revenue:{request.stock_id}:2026-05", "event_date": "2026-06-10", "title": "TWSE monthly revenue available", "summary": "Official monthly revenue evidence is available for the sample stock.", "quality_score": 0.88, "noise_risk": "low", "normalized_fields": {"feature_group": "fundamental", "available": True, "primary_source": True}}).to_dict()
            return result(request, "available", [evidence])
        if self.source_id == "twse_material_information":
            evidence = missing_evidence(self.source_id, request.stock_id, request.stock_name, "No material information fixture for offline sample; non-fatal disclosure gap.").to_dict()
            return result(request, "unavailable", [evidence], ["twse_material_information_unavailable"])
        evidence = normalize_evidence(self.source_id, request.stock_id, request.stock_name, {"evidence_id": f"{self.source_id}:{request.stock_id}:readiness", "event_date": "2026-07-02", "title": "TWSE financial statement readiness", "summary": "Official financial statement endpoint represented as readiness marker.", "evidence_type": "financial_statement", "quality_score": 0.7, "noise_risk": "low", "normalized_fields": {"feature_group": "fundamental", "readiness": "represented"}}).to_dict()
        return result(request, "available", [evidence])
