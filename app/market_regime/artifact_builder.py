from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from app.market_regime.classifier import classify_market_regime
from app.market_regime.schemas import MarketRegimeArtifact, SCHEMA_VERSION, safety_summary

def build_market_regime_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    result = classify_market_regime(payload).to_dict()
    sample_size = int(payload.get("sample_size") or 0)
    artifact = MarketRegimeArtifact(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        input_summary={
            "schema_version": payload.get("schema_version"),
            "as_of_date": payload.get("as_of_date"),
            "market": payload.get("market"),
            "source_kind": payload.get("source_kind", "offline_sample"),
            "sample_size": sample_size,
            "sample_mode": payload.get("source_kind", "offline_sample") == "offline_sample",
        },
        regime_result=result,
        regime_history_readiness={
            "minimum_sample_size": 10,
            "sample_size": sample_size,
            "status": "ready" if sample_size >= 20 and result["regime"] != "insufficient_data" else "insufficient" if result["regime"] == "insufficient_data" else "partial",
        },
        integration_notes={
            "prediction_confidence": "future advisory input only; no production confidence mutation",
            "factor_effectiveness": "future grouping dimension for rolling evaluation",
            "adaptive_recommendation": "future research input only; production_mutation_allowed=false",
            "dashboard": "future display candidate; production_publish_allowed=false",
        },
        safety_summary=safety_summary(),
        advisory_only=True,
    )
    return artifact.to_dict()
