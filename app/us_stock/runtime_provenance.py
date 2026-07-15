"""Runtime provenance classification shared by US persistence and readers."""
from __future__ import annotations

from enum import Enum
from typing import Any


class RuntimeProvenance(str, Enum):
    SCHEDULED_PRODUCTION = "scheduled_production"
    MANUAL_RERUN = "manual_rerun"
    CONTROLLED_NO_SEND = "controlled_no_send"
    PREVIEW = "preview"
    FIXTURE = "fixture"
    VALIDATOR = "validator"
    DRY_RUN = "dry_run"
    UNCLASSIFIED = "unclassified"


ADMITTED_PROVENANCE = frozenset({
    RuntimeProvenance.SCHEDULED_PRODUCTION.value,
    RuntimeProvenance.MANUAL_RERUN.value,
})


def classify_runtime_provenance(payload: dict[str, Any] | None, *, run_kind: str | None = None) -> str:
    """Classify explicit metadata first, then narrowly recognize legacy production."""
    data = payload if isinstance(payload, dict) else {}
    mode = " ".join(str(data.get(key) or "") for key in (
        "artifact_type", "artifact_mode", "runtime_mode", "data_source_mode", "run_kind", "source_mode",
    )).lower()
    if data.get("fixture") is True or data.get("is_fixture") is True or "fixture" in mode:
        return RuntimeProvenance.FIXTURE.value
    if data.get("validator") is True or "validator" in mode or "validation_artifact" in mode:
        return RuntimeProvenance.VALIDATOR.value
    if data.get("preview") is True or "preview" in mode:
        return RuntimeProvenance.PREVIEW.value
    if data.get("dry_run") is True or "dry_run" in mode:
        return RuntimeProvenance.DRY_RUN.value
    if "controlled_no_send" in mode or "live_no_send" in mode:
        return RuntimeProvenance.CONTROLLED_NO_SEND.value
    if data.get("validation_only") is True:
        return RuntimeProvenance.VALIDATOR.value

    explicit = str(data.get("runtime_provenance") or "").strip().lower()
    if explicit in {item.value for item in RuntimeProvenance}:
        return explicit
    if run_kind == RuntimeProvenance.MANUAL_RERUN.value:
        return RuntimeProvenance.MANUAL_RERUN.value

    # Backward-compatible only for the complete legacy production tuple.
    if (
        data.get("artifact_kind") == "us_stock_runtime"
        and data.get("artifact_mode") == "production_runtime"
        and data.get("data_source_mode") == "live"
        and data.get("fixture") is False
        and data.get("validation_only") is False
    ):
        return RuntimeProvenance.SCHEDULED_PRODUCTION.value
    if run_kind == "scheduled":
        return RuntimeProvenance.SCHEDULED_PRODUCTION.value
    return RuntimeProvenance.UNCLASSIFIED.value


def provenance_admission(payload: dict[str, Any] | None, *, run_kind: str | None = None) -> dict[str, Any]:
    provenance = classify_runtime_provenance(payload, run_kind=run_kind)
    admitted = provenance in ADMITTED_PROVENANCE
    return {
        "runtime_provenance": provenance,
        "admitted": admitted,
        "admission_reason": f"{provenance}_{'admitted' if admitted else 'rejected'}",
    }


def is_dashboard_eligible(payload: dict[str, Any] | None) -> bool:
    data = payload if isinstance(payload, dict) else {}
    provenance = classify_runtime_provenance(data)
    return (
        provenance in ADMITTED_PROVENANCE
        and data.get("market") == "US"
        and data.get("artifact_kind") == "us_stock_runtime"
        and data.get("data_source_mode") == "live"
        and data.get("fixture") is False
        and data.get("artifact_mode") == "production_runtime"
        and data.get("validation_only") is False
    )
