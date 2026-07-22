"""Non-sensitive notification delivery provenance artifacts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def source_payload_hash(snapshot: dict[str, Any]) -> str | None:
    metadata = snapshot.get("metadata") if isinstance(snapshot.get("metadata"), dict) else snapshot
    retained = metadata.get("payload_hash") or metadata.get("source_payload_hash")
    if retained:
        return str(retained)
    payload = snapshot.get("payload")
    if not isinstance(payload, dict):
        return None
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_delivery_provenance(*, market: str, window: str, trading_date: str, snapshot: dict[str, Any], canonical_url: str, channel: str, content: str, delivery_result: str, delivery_attempted: bool, recipient_count: int = 0, delivery_time: str | None = None, public_sync: dict[str, Any] | None = None) -> dict[str, Any]:
    if channel not in {"email", "line"}:
        raise ValueError("unsupported_delivery_channel")
    if delivery_result not in {"sent", "failed", "suppressed", "dry_run_not_sent", "not_attempted"}:
        raise ValueError("unsupported_delivery_result")
    metadata = snapshot.get("metadata") if isinstance(snapshot.get("metadata"), dict) else snapshot
    sync = public_sync if isinstance(public_sync, dict) else {}
    return {
        "schema_version": "notification_delivery_provenance_v1",
        "market": market.upper(), "window": window, "trading_date": trading_date,
        "snapshot_id": metadata.get("snapshot_id"), "revision": metadata.get("revision"),
        "source_payload_hash": source_payload_hash(snapshot),
        "presentation_content_hash": content_hash(content), "canonical_url": canonical_url,
        "formatted_at": datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat(),
        "delivery_channel": channel, "delivery_attempted": bool(delivery_attempted),
        "delivery_result": delivery_result, "delivery_time": delivery_time,
        "recipient_count": max(0, int(recipient_count)), "message_length": len(content),
        "public_parity_status": sync.get("status") or "not_attempted",
        "public_expected_identity": (sync.get("public_archive_verification") or {}).get("expected_identity"),
        "public_observed_identity": (sync.get("public_archive_verification") or {}).get("observed_identity"),
    }


def write_delivery_provenance(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
