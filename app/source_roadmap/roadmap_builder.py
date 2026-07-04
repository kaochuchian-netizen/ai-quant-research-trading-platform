from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
from app.source_roadmap.policy import build_priority_policy
from app.source_roadmap.schemas import ExternalSourceConnectorRoadmapArtifact, SCHEMA_VERSION, safety_summary

DEFAULT_AUDIT_PATH = Path("templates/external_source_coverage_audit.example.json")

def load_audit_artifact(repo_root: Path, audit_path: str | None = None) -> dict[str, Any]:
    path = Path(audit_path) if audit_path else repo_root / DEFAULT_AUDIT_PATH
    if not path.is_absolute():
        path = repo_root / path
    return json.loads(path.read_text(encoding="utf-8"))

def _ids(policy_rows: list[dict[str, Any]], predicate) -> list[str]:
    return sorted(row["source_id"] for row in policy_rows if predicate(row))

def build_external_source_connector_roadmap(repo_root: Path, audit_path: str | None = None) -> dict[str, Any]:
    audit = load_audit_artifact(repo_root, audit_path)
    records = audit.get("source_records", [])
    policies = [build_priority_policy(record) for record in records]
    roadmap = {
        "immediate_candidates": _ids(policies, lambda r: r["prediction_context_candidate"] and r["recommended_phase"] in {"phase_0_maintain", "phase_1_prediction_context"}),
        "report_integration_candidates": _ids(policies, lambda r: r["recommended_phase"] == "phase_2_formal_report"),
        "connector_build_candidates": _ids(policies, lambda r: r["recommended_phase"] == "phase_3_connector_build"),
        "defer_or_metadata_only": _ids(policies, lambda r: r["recommended_phase"] == "phase_4_defer_metadata_only"),
        "blocked_or_requires_manual_review": _ids(policies, lambda r: r["recommended_phase"] == "manual_review_required"),
        "prediction_context_first": _ids(policies, lambda r: r["prediction_context_candidate"]),
        "formal_report_first": _ids(policies, lambda r: r["formal_report_candidate"]),
        "must_not_affect_rating_action_confidence": _ids(policies, lambda r: not r["rating_action_confidence_allowed"]),
    }
    phase_counts = Counter(row["recommended_phase"] for row in policies)
    artifact = ExternalSourceConnectorRoadmapArtifact(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        input_summary={
            "audit_schema_version": audit.get("schema_version"),
            "audit_source_count": len(records),
            "audit_status_counts": audit.get("coverage_summary", {}).get("status_counts", {}),
        },
        priority_policy=policies,
        roadmap=roadmap,
        phase_summary={"phase_counts": dict(phase_counts), "total_sources": len(policies)},
        safety_summary=safety_summary(),
        future_integration={
            "prediction_context": "use phase_1/phase_3 official sources after deterministic artifacts exist",
            "formal_report": "promote phase_2 connectors before new runtime activation",
            "dashboard": "display roadmap only in future advisory dashboard task",
            "production_logic": "no rating/action/confidence/weight mutation in AI-DEV-132",
        },
        advisory_only=True,
    )
    return artifact.to_dict()
