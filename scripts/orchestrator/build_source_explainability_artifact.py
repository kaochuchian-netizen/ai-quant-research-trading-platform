#!/usr/bin/env python3
"""Build deterministic AI-DEV-123 multi-source explainability artifact."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from app.explainability.feature_attribution import build_feature_attribution
from app.explainability.explanation_builder import build_stock_explanation
from app.explainability.schemas import EXPLANATION_ARTIFACT_SCHEMA_VERSION, ExplanationArtifact
from app.sources.endpoint_registry import build_endpoint_registry
from app.sources.evidence_normalizer import missing_evidence
from app.sources.finmind_connector import FinMindConnector
from app.sources.schemas import SourceFetchRequest
from app.sources.tdcc_connector import TdccConnector
from app.sources.tpex_openapi_connector import TpexOpenApiConnector
from app.sources.twse_openapi_connector import TwseOpenApiConnector
from app.sources.yfinance_market_context import YfinanceMarketContextConnector
GENERATED_AT = "2026-07-02T00:00:00Z"

def safety_summary() -> dict[str, bool]:
    return {"broker_login": False, "simulation_order": False, "production_order": False, "line_send": False, "email_send": False, "scheduler_change": False, "production_db_write": False, "secrets_read": False, "production_forecast_weight_change": False, "large_ai_or_gemini_batch_call": False, "dashboard_production_publish": False, "nginx_systemd_cron_mutation": False}

def future_integration() -> dict[str, Any]:
    return {"status": "artifact_ready_runtime_not_integrated", "consumers": ["AI-DEV-124 Confidence Calibration", "AI-DEV-125 Adaptive Weight Recommendation", "AI-DEV-126 Dashboard Intelligence", "future backtesting.py strategy signal use"], "runtime_integration": "not_in_scope"}

def _collect(stock_id: str, stock_name: str, offline_sample: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    health: list[dict[str, Any]] = []; evidence: list[dict[str, Any]] = []; missing: list[str] = []
    connectors = [TwseOpenApiConnector("twse_monthly_revenue"), TwseOpenApiConnector("twse_material_information"), TwseOpenApiConnector("twse_financial_statement_readiness"), TpexOpenApiConnector(), TdccConnector(), YfinanceMarketContextConnector(), FinMindConnector("finmind_taiwan_stock_price"), FinMindConnector("finmind_monthly_revenue"), FinMindConnector("finmind_financial_statement"), FinMindConnector("finmind_institutional_investors_buy_sell"), FinMindConnector("finmind_cash_flows")]
    for connector in connectors:
        req = SourceFetchRequest(connector.source_id, stock_id, stock_name, offline_sample, False, None)
        result = connector.fetch(req).to_dict(); health.append(result["health"]); evidence.extend(result["evidence_batch"]["evidence"]); missing.extend(result["evidence_batch"].get("missing_reasons", []))
    etf_gap = missing_evidence("etf_holdings_nav_distribution", "00878", "ETF Example", "ETF holdings/NAV/distribution unavailable in offline sample; ETF-specific source gap.").to_dict()
    evidence.append(etf_gap); missing.append("etf_specific_source_gap")
    return health, evidence, sorted(set(missing))

def build_artifact(stock_id: str = "2330", stock_name: str = "TSMC", offline_sample: bool = True) -> dict[str, Any]:
    health, evidence, missing = _collect(stock_id, stock_name, offline_sample)
    attribution = build_feature_attribution("ai-dev-123-example-001", stock_id, stock_name, evidence).to_dict()
    explanation = build_stock_explanation("ai-dev-123-example-001", stock_id, stock_name, attribution, evidence).to_dict()
    source_coverage_summary = {"stock_id": stock_id, "readiness": explanation["source_coverage_summary"]["readiness"], "confidence_cap_reason": explanation["confidence_cap_reason"], "finmind_monthly_revenue_with_missing_official_statement": "partial_not_ready", "official_source_authoritative_on_conflict": True}
    missing_summary = {"missing_reasons": missing, "finmind_unavailable": "finmind_unavailable" in missing, "missing_primary_source_can_cap_confidence": True, "failed_connector_non_fatal": True}
    artifact = ExplanationArtifact(EXPLANATION_ARTIFACT_SCHEMA_VERSION, GENERATED_AT, health, evidence, [attribution], [explanation], source_coverage_summary, missing_summary, safety_summary(), future_integration())
    return artifact.to_dict()

def main() -> int:
    parser = argparse.ArgumentParser(description="Build source explainability artifact JSON."); parser.add_argument("--pretty", action="store_true"); parser.add_argument("--stock-id", default="2330"); parser.add_argument("--output"); parser.add_argument("--offline-sample", action="store_true", default=True); args = parser.parse_args()
    artifact = build_artifact(args.stock_id, "TSMC" if args.stock_id == "2330" else "Sample Stock", args.offline_sample)
    text = json.dumps(artifact, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        path = Path(args.output); path = path if path.is_absolute() else ROOT / path; path.write_text(text + "\n", encoding="utf-8")
    else: sys.stdout.write(text + "\n")
    return 0
if __name__ == "__main__": raise SystemExit(main())
