"""Connector-ready, fail-closed handoff for allowlisted Visual Evidence.

The outbox is an internal boundary contract, not direct ChatGPT connectivity.
No network endpoint, credential, public URL, or production dependency is created.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from app.dashboard.visual_evidence_archive import DEFAULT_VISUAL_ROOT
from app.dashboard.visual_evidence_export import (
    DEFAULT_EXPORT_ROOT,
    TRANSPORT_STATUS,
    export_visual_evidence,
)

TRANSPORT_SCHEMA = "chatgpt_artifact_transport_envelope_v1"
TRANSPORT_METHOD = "AUTHENTICATED_CONNECTOR_OUTBOX_PENDING"
OUTBOX_STATUS = "READY_FOR_EXTERNAL_CONNECTOR"
DEFAULT_OUTBOX_ROOT = Path(os.environ.get(
    "STOCK_AI_CHATGPT_TRANSPORT_OUTBOX",
    Path(__file__).resolve().parents[2] / "artifacts/runtime/chatgpt_artifact_transport_outbox",
))


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _failure(reason: str, *, production_batch_continues: bool = True, **values: Any) -> dict[str, Any]:
    return {
        "schema_version": TRANSPORT_SCHEMA,
        "status": "FAILED",
        "reason_code": reason,
        "transport_status": TRANSPORT_STATUS,
        "transport_method": TRANSPORT_METHOD,
        "production_batch_continues": production_batch_continues,
        **values,
    }


def prepare_chatgpt_transport(
    *,
    effective_date: str,
    artifact: str,
    market: str | None = None,
    window: str | None = None,
    revision: str | int = "latest_valid",
    visual_root: Path = DEFAULT_VISUAL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    outbox_root: Path = DEFAULT_OUTBOX_ROOT,
) -> dict[str, Any]:
    """Resolve a canonical selector and create one immutable opaque outbox item."""
    try:
        exported = export_visual_evidence(
            effective_date=effective_date,
            market=market,
            window=window,
            revision=revision,
            artifact=artifact,
            visual_root=visual_root,
            export_root=export_root,
        )
    except Exception:
        return _failure("TRANSPORT_UNAVAILABLE", effective_date=effective_date, market=market, window=window)
    if exported.get("status") != "SUCCESS":
        reason_map = {
            "EVIDENCE_NOT_FOUND": "ARTIFACT_NOT_FOUND",
            "PDF_NOT_CAPTURED": "ARTIFACT_NOT_FOUND",
            "HASH_OR_SIZE_MISMATCH": "ARTIFACT_HASH_MISMATCH",
            "IDENTITY_MISMATCH": "SELECTOR_IDENTITY_MISMATCH",
            "SYMLINK_OR_PATH_ESCAPE": "TRANSPORT_FORBIDDEN",
            "ARTIFACT_NOT_ALLOWLISTED": "TRANSPORT_FORBIDDEN",
            "MANIFEST_NOT_ALLOWLISTED": "TRANSPORT_FORBIDDEN",
            "INVALID_SELECTOR": "TRANSPORT_FORBIDDEN",
        }
        return _failure(
            reason_map.get(str(exported.get("reason_code")), str(exported.get("reason_code") or "TRANSPORT_FORBIDDEN")),
            effective_date=effective_date, market=market, window=window, revision=revision,
            artifact_type=artifact,
        )
    source = Path(str(exported.get("safe_export_location") or ""))
    try:
        source = source.resolve(strict=True)
        source.relative_to(export_root.resolve(strict=True))
    except (OSError, ValueError):
        return _failure("TRANSPORT_FORBIDDEN", effective_date=effective_date, market=market, window=window)
    if source.is_symlink() or _sha256(source) != exported.get("sha256"):
        return _failure("ARTIFACT_HASH_MISMATCH", effective_date=effective_date, market=market, window=window)
    request_identity = {
        "effective_date": exported.get("effective_date"),
        "market": exported.get("market"),
        "window": exported.get("window"),
        "revision": exported.get("revision"),
        "visual_evidence_id": exported.get("visual_evidence_id"),
        "snapshot_id": exported.get("snapshot_id"),
        "artifact_type": exported.get("artifact_type"),
        "artifact_sha256": exported.get("sha256"),
    }
    request_id = hashlib.sha256(json.dumps(request_identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    target = outbox_root / request_id
    artifact_name = source.name
    artifact_path = target / artifact_name
    envelope_path = target / "transport_envelope.json"
    envelope = {
        "schema_version": TRANSPORT_SCHEMA,
        "request_id": request_id,
        "request_identity": request_identity,
        "effective_date": exported.get("effective_date"),
        "market": exported.get("market"),
        "window": exported.get("window"),
        "revision": exported.get("revision"),
        "visual_evidence_id": exported.get("visual_evidence_id"),
        "source_snapshot_id": exported.get("snapshot_id"),
        "artifact_type": exported.get("artifact_type"),
        "filename": artifact_name,
        "media_type": exported.get("media_type"),
        "size": exported.get("size"),
        "sha256": exported.get("sha256"),
        "source_manifest": exported.get("source_manifest"),
        "batch_provenance": exported.get("batch_provenance"),
        "transport_status": TRANSPORT_STATUS,
        "outbox_status": OUTBOX_STATUS,
        "transport_method": TRANSPORT_METHOD,
        "safe_retrieval_reference": f"artifact-transport://{request_id}/{artifact_name}",
        "created_at_method": "SOURCE_MANIFEST_IDENTITY_DETERMINISTIC",
        "expires_at": None,
        "external_connector_required": True,
        "production_batch_continues": True,
    }
    target.mkdir(parents=True, exist_ok=True)
    if artifact_path.exists() and _sha256(artifact_path) != exported.get("sha256"):
        return _failure("ARTIFACT_HASH_MISMATCH", request_id=request_id)
    if not artifact_path.exists():
        temporary = artifact_path.with_suffix(artifact_path.suffix + f".tmp-{os.getpid()}")
        shutil.copyfile(source, temporary)
        temporary.replace(artifact_path)
    serialized = _stable(envelope)
    if envelope_path.exists() and envelope_path.read_text(encoding="utf-8") != serialized:
        return _failure("SELECTOR_IDENTITY_MISMATCH", request_id=request_id)
    if not envelope_path.exists():
        temporary = envelope_path.with_suffix(f".tmp-{os.getpid()}")
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(envelope_path)
    return {
        **envelope,
        "status": OUTBOX_STATUS,
        "reason_code": "TRANSPORT_NOT_CONFIGURED",
        "outbox_reference": request_id,
        "outbox_location": str(target),
        "envelope_sha256": _sha256(envelope_path),
    }


def prepare_transport_non_blocking(**kwargs: Any) -> dict[str, Any]:
    """Production-safe wrapper: a transport result never controls batch success."""
    result = prepare_chatgpt_transport(**kwargs)
    result["production_batch_continues"] = True
    return result
