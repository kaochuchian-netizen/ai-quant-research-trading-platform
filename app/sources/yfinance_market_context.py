"""Read-only yfinance external market context fixture."""
from __future__ import annotations
from app.sources.evidence_normalizer import normalize_evidence
from app.sources.schemas import SourceFetchRequest, SourceFetchResult
from app.sources.source_client import result

class YfinanceMarketContextConnector:
    source_id = "yfinance_external_market_context"
    def fetch(self, request: SourceFetchRequest) -> SourceFetchResult:
        evidence = normalize_evidence(self.source_id, request.stock_id, request.stock_name, {"evidence_id": f"yfinance_context:{request.stock_id}:2026-07-02", "event_date": "2026-07-02", "title": "External market context", "summary": "TSM ADR, NASDAQ, S&P 500, SOXX/SMH, VIX proxy, US yield, and USD proxy are represented as confirmation-only context.", "quality_score": 0.56, "noise_risk": "medium", "normalized_fields": {"feature_group": "macro", "adr_proxy": "TSM", "market_context_only": True, "must_not_independently_raise_rating": True}}).to_dict()
        return result(request, "available", [evidence])
