"""Build deterministic Unified Decision Context artifacts."""
from __future__ import annotations
from typing import Any
from .sample_data import offline_sample_input
from .schemas import ARTIFACT_TYPE, FORMAL_REPORT_INTEGRATION_IDS, SCHEMA_VERSION, TASK_ID, safety_policy


def _source_summary(source_inputs: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return {category: sorted(list(items), key=lambda row: row.get("source_id", "")) for category, items in sorted(source_inputs.items())}


def _credibility_rows(source_summary: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category, entries in source_summary.items():
        for entry in entries:
            source_id = entry["source_id"]
            metadata_only = category == "low_priority_metadata"
            is_ai = category == "ai_generated_analysis"
            rows.append(
                {
                    "source_id": source_id,
                    "provider": entry["provider"],
                    "source_category": category,
                    "source_priority": entry["source_priority"],
                    "credibility_level": entry["credibility_level"],
                    "decision_value": entry["decision_value"],
                    "report_allowed": not is_ai,
                    "prediction_context_allowed": True,
                    "metadata_only": metadata_only,
                    "official_source_replacement_allowed": category in {"official_primary_source", "official_market_source"},
                    "direct_rating_action_confidence_impact": False,
                }
            )
    return sorted(rows, key=lambda row: row["source_id"])


def _exclusions(credibility_rows: list[dict[str, Any]]) -> dict[str, Any]:
    metadata_only = [row["source_id"] for row in credibility_rows if row.get("metadata_only")]
    no_direct_impact = [row["source_id"] for row in credibility_rows if row.get("direct_rating_action_confidence_impact") is False]
    cannot_replace_official = [row["source_id"] for row in credibility_rows if row.get("official_source_replacement_allowed") is False]
    return {
        "metadata_only_sources": metadata_only,
        "no_direct_rating_action_confidence_impact_sources": no_direct_impact,
        "official_source_replacement_disallowed_sources": cannot_replace_official,
        "production_mutation_disallowed": True,
        "notes": [
            "Prediction Context is an attributed context artifact, not a production decision engine.",
            "External proxies and low-priority metadata cannot directly alter rating/action/confidence.",
            "Official source governance wins conflicts with normalized or external reference providers.",
        ],
    }


def build_prediction_context_artifact(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or offline_sample_input()
    source_summary = _source_summary(payload["source_inputs"])
    credibility_rows = _credibility_rows(source_summary)
    formal_report_integrations = {key: payload["formal_report_integrations"][key] for key in FORMAL_REPORT_INTEGRATION_IDS}
    warnings = [
        "Deterministic offline sample only; no external runtime fetch performed.",
        "Context may inform future explainability/report/dashboard layers but does not change production rating/action/confidence.",
    ]
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "artifact_type": ARTIFACT_TYPE,
        "generated_at": payload["generated_at"],
        "symbol": payload["symbol"],
        "market": payload["market"],
        "context_window": payload["context_window"],
        "source_summary": source_summary,
        "source_credibility_summary": credibility_rows,
        "formal_report_integrations": formal_report_integrations,
        "technical_context": payload["technical_context"],
        "chip_context": payload["chip_context"],
        "adr_context": payload["adr_context"],
        "news_context": payload["news_context"],
        "finmind_context": payload["finmind_context"],
        "twse_context": payload["twse_context"],
        "yfinance_context": payload["yfinance_context"],
        "historical_context": payload["historical_context"],
        "rolling_evaluation_context": payload["rolling_evaluation_context"],
        "market_regime_context": payload["market_regime_context"],
        "confidence_calibration_context": payload["confidence_calibration_context"],
        "factor_effectiveness_context": payload["factor_effectiveness_context"],
        "explainability_context": payload["explainability_context"],
        "warnings": warnings,
        "exclusions": _exclusions(credibility_rows),
        "safety_policy": safety_policy(),
        "future_integration": {
            "ai_dev_137_explainability": "consume Prediction Context for source/evidence explanation",
            "ai_dev_138_traceability": "attach source and artifact references to every downstream decision context field",
            "ai_dev_139_report_assembly": "assemble daily report sections from this context without delivery side effects",
            "ai_dev_140_dashboard_drill_down": "render drill-down views from context artifacts only",
        },
    }
    return artifact
