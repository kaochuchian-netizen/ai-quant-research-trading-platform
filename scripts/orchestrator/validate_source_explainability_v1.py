#!/usr/bin/env python3
"""Validate AI-DEV-123 multi-source explainability V1."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from app.explainability.schemas import DIRECTIONS, EXPLANATION_ARTIFACT_SCHEMA_VERSION, FEATURE_GROUPS
from app.sources.endpoint_registry import build_endpoint_registry
from app.sources.finmind_connector import FINMIND_SOURCE_IDS, FinMindConnector
from app.sources.schemas import SourceFetchRequest, SourceEvidence
REQUIRED_FILES = ["app/sources/__init__.py", "app/sources/schemas.py", "app/sources/source_client.py", "app/sources/endpoint_registry.py", "app/sources/twse_openapi_connector.py", "app/sources/tpex_openapi_connector.py", "app/sources/tdcc_connector.py", "app/sources/yfinance_market_context.py", "app/sources/finmind_connector.py", "app/sources/evidence_normalizer.py", "app/explainability/__init__.py", "app/explainability/schemas.py", "app/explainability/feature_attribution.py", "app/explainability/explanation_builder.py", "app/explainability/explanation_policy.py", "scripts/orchestrator/build_source_explainability_artifact.py", "scripts/orchestrator/validate_source_explainability_v1.py", "templates/source_evidence.example.json", "templates/feature_attribution.example.json", "templates/source_explainability_artifact.example.json", "docs/ai_dev_123_multi_source_connector_explainability_v1.md"]
FORBIDDEN_FALSE = {"broker_login", "simulation_order", "production_order", "line_send", "email_send", "scheduler_change", "production_db_write", "secrets_read", "production_forecast_weight_change", "large_ai_or_gemini_batch_call", "dashboard_production_publish", "nginx_systemd_cron_mutation"}
def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict): raise ValueError(f"JSON root must be object: {path}")
    return data
def run_builder() -> tuple[dict[str, Any] | None, str | None]:
    proc = subprocess.run([sys.executable, "scripts/orchestrator/build_source_explainability_artifact.py"], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0: return None, proc.stderr.strip() or proc.stdout.strip()
    try: data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc: return None, str(exc)
    return data if isinstance(data, dict) else None, None if isinstance(data, dict) else "builder output root must be object"
def validate_registry(reasons: list[str]) -> None:
    endpoints = {item.source_id: item for item in build_endpoint_registry()}
    for source_id in ["twse_monthly_revenue", "twse_material_information", "twse_financial_statement_readiness", "tpex_openapi_readiness", "tdcc_shareholding_distribution", "yfinance_external_market_context"]:
        if source_id not in endpoints: reasons.append(f"registry missing {source_id}")
    yf = endpoints.get("yfinance_external_market_context")
    if yf and (yf.provider != "yfinance / Yahoo Finance" or yf.priority != "C_market_or_industry" or "must_not_independently_raise_rating" not in yf.usage_policy): reasons.append("yfinance policy invalid")
    for source_id in sorted(FINMIND_SOURCE_IDS):
        ep = endpoints.get(source_id)
        if not ep: reasons.append(f"FinMind registry missing {source_id}"); continue
        if ep.priority == "A_primary": reasons.append(f"FinMind priority must not be A_primary: {source_id}")
        for policy in ["must_not_replace_primary_source", "must_not_independently_raise_rating", "no production score mutation"]:
            if policy not in ep.usage_policy: reasons.append(f"FinMind {source_id} missing policy {policy}")
def validate_artifact(artifact: dict[str, Any], reasons: list[str]) -> None:
    if artifact.get("schema_version") != EXPLANATION_ARTIFACT_SCHEMA_VERSION: reasons.append("artifact schema_version invalid")
    for field in ["source_connector_health", "source_evidence", "feature_attributions", "stock_explanations", "source_coverage_summary", "missing_data_summary", "safety_summary", "future_integration"]:
        if field not in artifact: reasons.append(f"artifact missing {field}")
    safety = artifact.get("safety_summary", {})
    for key in FORBIDDEN_FALSE:
        if safety.get(key) is not False: reasons.append(f"safety_summary must confirm {key}=false")
    evidence = artifact.get("source_evidence", [])
    if isinstance(evidence, list):
        if not any(item.get("source_id") == "finmind_monthly_revenue" for item in evidence): reasons.append("FinMind monthly revenue evidence missing")
        if not any(item.get("source_id") == "twse_monthly_revenue" for item in evidence): reasons.append("TWSE monthly revenue evidence missing")
        if not any(item.get("source_id") == "twse_material_information" and item.get("evidence_type") == "missing_source_notice" for item in evidence): reasons.append("material information unavailable marker missing")
        if not any(item.get("normalized_fields", {}).get("source_conflict", {}).get("official_source_wins") is True for item in evidence): reasons.append("official-source-wins conflict marker missing")
        for item in evidence:
            try: reasons.extend(["source evidence invalid: " + r for r in SourceEvidence(**item).validate()])
            except Exception as exc: reasons.append(f"source evidence cannot load: {exc}")
    health = artifact.get("source_connector_health", [])
    if isinstance(health, list):
        if not any(item.get("source_id") == "tdcc_shareholding_distribution" and item.get("status") == "unavailable" for item in health): reasons.append("missing connector unavailable non-fatal case")
    attrs = artifact.get("feature_attributions", [])
    if isinstance(attrs, list) and attrs:
        contribs = attrs[0].get("contributions", [])
        directions = {item.get("direction") for item in contribs}; groups = {item.get("feature_group") for item in contribs}
        for needed in ["positive", "neutral", "not_available"]:
            if needed not in directions: reasons.append(f"missing contribution direction {needed}")
        if "missing_data" not in groups: reasons.append("missing missing-data factor")
        if not any("FinMind" in item.get("explanation_text", "") for item in contribs): reasons.append("FinMind sample evidence not attached to FeatureContribution")
        if not any("cannot raise rating" in str(item.get("risk_note", "")) for item in contribs): reasons.append("news/yfinance/FinMind cannot-raise-rating policy missing in attribution")
    explanations = artifact.get("stock_explanations", [])
    if isinstance(explanations, list) and explanations:
        exp = explanations[0]
        if not exp.get("top_positive_factors"): reasons.append("explanation missing positive factors")
        if not exp.get("neutral_factors"): reasons.append("explanation missing neutral factors")
        if not exp.get("missing_data_factors"): reasons.append("explanation missing missing-data factors")
        if exp.get("source_coverage_summary", {}).get("readiness") == "ready" and artifact.get("source_coverage_summary", {}).get("finmind_monthly_revenue_with_missing_official_statement") == "partial_not_ready": reasons.append("FinMind with missing official source must be partial, not ready")
    missing = artifact.get("missing_data_summary", {})
    if missing.get("failed_connector_non_fatal") is not True: reasons.append("failed connector non-fatal flag missing")
def validate_templates(reasons: list[str]) -> None:
    evidence_template = load_json(ROOT / "templates/source_evidence.example.json"); attr_template = load_json(ROOT / "templates/feature_attribution.example.json"); artifact_template = load_json(ROOT / "templates/source_explainability_artifact.example.json")
    if "source_evidence" not in evidence_template: reasons.append("source_evidence.example missing source_evidence")
    if "feature_attribution" not in attr_template: reasons.append("feature_attribution.example missing feature_attribution")
    validate_artifact(artifact_template, reasons)
def validate_finmind_offline(reasons: list[str]) -> None:
    req = SourceFetchRequest("finmind_monthly_revenue", "2330", "TSMC", True, False, None); res = FinMindConnector("finmind_monthly_revenue").fetch(req).to_dict()
    if res["health"]["status"] != "available": reasons.append("FinMind offline sample should be available")
    ev = res["evidence_batch"]["evidence"][0]
    if ev.get("priority") == "A_primary": reasons.append("FinMind sample priority must not be A_primary")
    if ev.get("normalized_fields", {}).get("readiness_effect") != "partial_not_ready": reasons.append("FinMind monthly revenue readiness effect must be partial_not_ready")
    req2 = SourceFetchRequest("finmind_cash_flows", "2330", "TSMC", True, True, None); res2 = FinMindConnector("finmind_cash_flows")._network_unavailable(req2).to_dict()
    if res2["health"]["status"] != "unavailable": reasons.append("FinMind unavailable must be health unavailable")
def validate_docs(reasons: list[str]) -> None:
    text = (ROOT / "docs/ai_dev_123_multi_source_connector_explainability_v1.md").read_text(encoding="utf-8")
    for phrase in ["No production trading", "No simulation order", "No production order", "No scheduler mutation", "No LINE/Email delivery", "No production DB write", "No production forecast weight mutation", "No production dashboard publish", "No AI-generated investment advice", "No automatic change to rating/action weights", "FinMind", "coverage accelerator", "fallback / cross-check", "does not replace official primary sources", "AI-DEV-124 Confidence Calibration", "AI-DEV-125 Adaptive Weight Recommendation", "AI-DEV-126 Dashboard Intelligence"]:
        if phrase not in text: reasons.append(f"doc missing phrase: {phrase}")
def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-123 source explainability V1."); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args(); reasons: list[str] = []
    for path in REQUIRED_FILES:
        if not (ROOT / path).exists(): reasons.append(f"required file missing: {path}")
    for func in [validate_registry, validate_templates, validate_finmind_offline, validate_docs]:
        try: func(reasons)
        except Exception as exc: reasons.append(f"{func.__name__} failed: {exc}")
    artifact, error = run_builder()
    if error: reasons.append(f"artifact builder output invalid: {error}")
    elif artifact: validate_artifact(artifact, reasons)
    output = {"ok": True, "passed": not reasons, "required_file_count": len(REQUIRED_FILES), "feature_groups": sorted(FEATURE_GROUPS), "directions": sorted(DIRECTIONS), "finmind_sources": sorted(FINMIND_SOURCE_IDS), "reasons": reasons, "side_effects": {"files_modified": False, "runtime_queue_modified": False, "database_modified": False, "production_data_modified": False, "external_api_called": False, "notification_sent": False, "trading_execution_run": False, "production_pipeline_run": False, "scheduler_modified": False, "secrets_read_or_modified": False}}
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True); sys.stdout.write("\n")
    return 0 if output["passed"] else 2
if __name__ == "__main__": raise SystemExit(main())
