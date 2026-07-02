"""Optional read-only FinMind connector for offline artifacts.

Token/network support is intentionally disabled by default. Validation uses
sample records only and never reads secrets.
"""
from __future__ import annotations
from urllib import request as urllib_request
from urllib.parse import urlencode
from app.sources.evidence_normalizer import missing_evidence, normalize_evidence
from app.sources.schemas import SourceFetchRequest, SourceFetchResult
from app.sources.source_client import result

FINMIND_SOURCE_IDS = {"finmind_taiwan_stock_price", "finmind_monthly_revenue", "finmind_financial_statement", "finmind_balance_sheet", "finmind_cash_flows", "finmind_institutional_investors_buy_sell", "finmind_margin_purchase_short_sale", "finmind_holding_shares_per"}

class FinMindConnector:
    def __init__(self, source_id: str): self.source_id = source_id
    def fetch(self, request: SourceFetchRequest) -> SourceFetchResult:
        if self.source_id not in FINMIND_SOURCE_IDS:
            evidence = missing_evidence(self.source_id, request.stock_id, request.stock_name, "unknown FinMind source id").to_dict()
            return result(request, "error", [evidence], ["finmind_unknown_source"])
        if not request.allow_network:
            return self._offline(request)
        return self._network_unavailable(request)
    def _network_unavailable(self, request: SourceFetchRequest) -> SourceFetchResult:
        evidence = missing_evidence(self.source_id, request.stock_id, request.stock_name, "FinMind network access disabled or unavailable; artifact remains valid.").to_dict()
        return result(request, "unavailable", [evidence], ["finmind_unavailable"])
    def _offline(self, request: SourceFetchRequest) -> SourceFetchResult:
        mapping = {
            "finmind_taiwan_stock_price": ("market_price", "technical", "FinMind stock price sample is available as market-price cross-check."),
            "finmind_monthly_revenue": ("monthly_revenue", "fundamental", "FinMind aggregated monthly revenue is available, but official TWSE/MOPS confirmation remains authoritative."),
            "finmind_financial_statement": ("financial_statement", "fundamental", "FinMind financial statement sample can make readiness partial when official source is missing."),
            "finmind_balance_sheet": ("financial_statement", "fundamental", "FinMind balance sheet sample is normalized as financial statement evidence."),
            "finmind_cash_flows": ("financial_statement", "fundamental", "FinMind cash flow sample is normalized as financial statement evidence."),
            "finmind_institutional_investors_buy_sell": ("institutional_flow", "chip", "FinMind institutional flow can contribute chip explanation but cannot override official source."),
            "finmind_margin_purchase_short_sale": ("margin_short", "chip", "FinMind margin/short data can contribute chip risk context."),
            "finmind_holding_shares_per": ("chip_structure", "chip", "FinMind holding shares data can cross-check chip structure."),
        }
        evidence_type, feature_group, summary = mapping[self.source_id]
        raw = {"evidence_id": f"{self.source_id}:{request.stock_id}:offline", "event_date": "2026-07-02", "title": f"{self.source_id} offline sample", "summary": summary, "evidence_type": evidence_type, "quality_score": 0.62, "noise_risk": "medium", "normalized_fields": {"feature_group": feature_group, "aggregated_source": True, "primary_source": False, "readiness_effect": "partial_not_ready", "must_not_replace_primary_source": True, "must_not_independently_raise_rating": True}}
        if self.source_id == "finmind_monthly_revenue":
            raw["source_conflict"] = {"official_source_id": "twse_monthly_revenue", "conflict_field": "monthly_revenue", "official_source_wins": True}
        return result(request, "available", [normalize_evidence(self.source_id, request.stock_id, request.stock_name, raw).to_dict()])

def build_finmind_url(dataset: str, stock_id: str, start_date: str, token: str | None = None) -> str:
    params = {"dataset": dataset, "data_id": stock_id, "start_date": start_date}
    if token: params["token"] = token
    return "https://api.finmindtrade.com/api/v4/data?" + urlencode(params)
