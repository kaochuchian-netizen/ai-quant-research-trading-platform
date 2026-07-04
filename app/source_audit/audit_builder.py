from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.source_audit.repo_scanner import evidence_exists, scan_repo_files
from app.source_audit.schemas import ExternalSourceAuditRecord, ExternalSourceCoverageAuditArtifact, SCHEMA_VERSION, safety_summary
from app.source_audit.source_catalog import KNOWN_SOURCE_DEFINITIONS

PRODUCTION_USED = {"google_sheet", "shioaji_sinopac", "sqlite_historical_csv"}
CONNECTOR_EXISTS = {"twse_openapi", "yfinance_yahoo"}
ARTIFACT_USED = {"google_sheet", "shioaji_sinopac", "twse_openapi", "google_news_rss", "yfinance_yahoo", "gemini_google_generative_ai", "sqlite_historical_csv"}
PREDICTION_USED = {"google_sheet", "shioaji_sinopac", "twse_openapi", "sqlite_historical_csv", "yfinance_yahoo"}
EVALUATION_USED = {"sqlite_historical_csv", "shioaji_sinopac"}
REPORT_USED = {"google_sheet", "shioaji_sinopac", "sqlite_historical_csv"}
DASHBOARD_USED = {"sqlite_historical_csv"}
LOW_PRIORITY = {"google_news_rss", "gemini_google_generative_ai", "management_interviews", "analyst_target_broker_opinion"}
INVENTORY_ONLY = {"mops_public_information_observatory", "company_announcements", "financial_statements", "investor_conference", "industry_supply_chain", "etf_index_sector_proxy"}
NEEDS_CONNECTOR = {"analyst_target_broker_opinion"}

def _status(source_id: str, found: list[str]) -> str:
    if source_id in NEEDS_CONNECTOR:
        return "needs_connector"
    if source_id in LOW_PRIORITY:
        return "low_priority_metadata_only"
    if source_id in PRODUCTION_USED:
        return "production_used"
    if source_id in CONNECTOR_EXISTS and found:
        return "connector_exists_not_in_formal_report"
    if source_id in INVENTORY_ONLY and found:
        return "inventory_only_not_connectorized"
    return "needs_connector"

def _readiness(status: str, source_id: str) -> str:
    if status == "production_used":
        return "production_ready"
    if status == "connector_exists_not_in_formal_report":
        return "shadow_ready"
    if status == "low_priority_metadata_only":
        return "not_recommended_primary"
    if status == "inventory_only_not_connectorized":
        return "research_only"
    return "not_ready"

def _gaps(status: str, source_id: str) -> list[str]:
    gaps: list[str] = []
    if status == "production_used":
        gaps.append("none")
    if status == "connector_exists_not_in_formal_report":
        gaps.extend(["report_integration_gap", "dashboard_integration_gap", "evaluation_gap"])
    if status == "inventory_only_not_connectorized":
        gaps.extend(["connector_gap", "prediction_context_gap", "evaluation_gap"])
    if status == "needs_connector":
        gaps.extend(["connector_gap", "prediction_context_gap", "evaluation_gap"])
    if status == "low_priority_metadata_only":
        gaps.extend(["quality_priority_gap", "prediction_context_gap"])
    if source_id in {"google_sheet", "shioaji_sinopac", "gemini_google_generative_ai", "analyst_target_broker_opinion"}:
        gaps.append("credential_policy_gap")
    return sorted(dict.fromkeys(gaps))

def _next_action(status: str, source_id: str) -> str:
    if status == "production_used":
        return "maintain current production usage; add monitoring/completeness only"
    if status == "connector_exists_not_in_formal_report":
        return "add shadow artifact/report integration after source quality validation"
    if status == "inventory_only_not_connectorized":
        return "build deterministic connector contract and sample artifacts before runtime activation"
    if status == "low_priority_metadata_only":
        return "keep as low-priority metadata; do not use as primary prediction evidence"
    return "evaluate feasibility and create connector only if source licensing/quality is acceptable"

def build_external_source_coverage_audit(repo_root: Path) -> dict[str, Any]:
    scan = scan_repo_files(repo_root)
    records: list[dict[str, Any]] = []
    for item in KNOWN_SOURCE_DEFINITIONS:
        source_id = item["source_id"]
        found = evidence_exists(repo_root, item.get("evidence", []))
        status = _status(source_id, found)
        gaps = _gaps(status, source_id)
        connector_exists = bool(found) and status != "inventory_only_not_connectorized" or source_id in PRODUCTION_USED or source_id in CONNECTOR_EXISTS
        record = ExternalSourceAuditRecord(
            source_id=source_id,
            source_name=item["source_name"],
            source_type=item["source_type"],
            provider=item["provider"],
            current_status=status,
            connector_exists=connector_exists,
            runtime_used=source_id in PRODUCTION_USED,
            artifact_used=source_id in ARTIFACT_USED,
            report_used=source_id in REPORT_USED,
            dashboard_used=source_id in DASHBOARD_USED,
            prediction_used=source_id in PREDICTION_USED,
            evaluation_used=source_id in EVALUATION_USED,
            credential_required=bool(item["credential_required"]),
            freshness_policy=item["freshness_policy"],
            failure_mode="missing_or_stale_artifact" if source_id not in PRODUCTION_USED else "runtime_unavailable_or_stale_artifact",
            source_priority=item["source_priority"],
            explainability_support="supported_with_evidence_ids" if source_id in ARTIFACT_USED else "not_yet_supported",
            production_readiness=_readiness(status, source_id),
            gaps=gaps,
            recommended_next_action=_next_action(status, source_id),
            evidence_files=found,
        ).to_dict()
        records.append(record)

    status_counts = Counter(r["current_status"] for r in records)
    readiness_counts = Counter(r["production_readiness"] for r in records)
    gap_counts = Counter(gap for r in records for gap in r["gaps"])
    recommendations = [
        {"priority":"high","target":"MOPS/company official filings","action":"connectorize official filing sources before using them in prediction context"},
        {"priority":"medium","target":"TWSE/yfinance connectors","action":"promote existing connectors into shadow artifacts and report/dashboard readiness after validation"},
        {"priority":"low","target":"news/LLM/interview/analyst opinion","action":"keep as metadata/noise; never primary evidence without official confirmation"},
    ]
    artifact = ExternalSourceCoverageAuditArtifact(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        audit_mode="offline_repo_scan_no_external_calls",
        repo_scan_summary=scan,
        source_records=records,
        coverage_summary={
            "total_sources": len(records),
            "status_counts": dict(status_counts),
            "readiness_counts": dict(readiness_counts),
            "production_used_count": status_counts.get("production_used", 0),
            "connector_exists_count": sum(1 for r in records if r["connector_exists"]),
            "prediction_used_count": sum(1 for r in records if r["prediction_used"]),
            "evaluation_used_count": sum(1 for r in records if r["evaluation_used"]),
        },
        gap_summary={"gap_counts": dict(gap_counts), "sources_with_gaps": [r["source_id"] for r in records if r["gaps"] != ["none"]]},
        roadmap_recommendations=recommendations,
        safety_summary=safety_summary(),
        advisory_only=True,
    )
    return artifact.to_dict()
