"""Fail-closed, privacy-preserving receipts for a single notification attempt.

The receipt records *transport acceptance*, never end-user inbox/device delivery.
It is deliberately content-addressed by the immutable snapshot and rendered
content, so a retry cannot silently send the same channel twice.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.dashboard.market_dashboard_alias import snapshot_parity_contract


SCHEMA_VERSION = "channel_delivery_receipt_v1"
TERMINAL_RESULTS = {"transport_accepted", "partial_failure", "failed", "timeout", "unknown"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def mask_recipient(value: str) -> str:
    """Return a stable non-plaintext audit token; never retain recipient text."""
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:20]


def delivery_identity(*, snapshot: dict[str, Any], channel: str, market: str, window: str, content: str) -> dict[str, Any]:
    parity = snapshot_parity_contract(snapshot)
    if channel not in {"line", "email"} or not parity:
        raise ValueError("invalid_channel_delivery_identity")
    return {
        "market": str(market).upper(),
        "window": str(window),
        "trading_date": str(snapshot.get("effective_trading_date") or ""),
        "snapshot_id": str(parity["snapshot_id"]),
        "revision": int(parity["revision"]),
        "payload_hash": str(parity["payload_hash"]),
        "channel": channel,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def receipt_path(root: Path, identity: dict[str, Any]) -> Path:
    return Path(root) / (hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest() + ".json")


def _valid_terminal_receipt(value: Any, identity: dict[str, Any]) -> bool:
    if not (isinstance(value, dict) and value.get("schema_version") == SCHEMA_VERSION
            and value.get("identity") == identity and value.get("channel") == identity.get("channel")
            and value.get("transport_result") in TERMINAL_RESULTS
            and isinstance(value.get("recipients"), list)):
        return False
    rows = value["recipients"]
    if not rows or any(not isinstance(r, dict) or not str(r.get("recipient_mask", "")).startswith("sha256:")
                       or r.get("status") not in {"accepted", "rejected", "timeout", "failed", "unknown"} for r in rows):
        return False
    if len({r["recipient_mask"] for r in rows}) != len(rows):
        return False
    accepted = sum(r["status"] == "accepted" for r in rows)
    return (type(value.get("recipient_count")) is int and value["recipient_count"] == len(rows)
            and type(value.get("accepted_recipient_count")) is int and value["accepted_recipient_count"] == accepted
            and (value["transport_result"] == "transport_accepted") == (accepted == len(rows))
            and value.get("final_recipient_delivery_confirmed") is False)


def build_transport_evidence(*, channel: str, recipients: list[dict[str, Any]], attempted_at: str | None = None) -> dict[str, Any]:
    """Normalize only masked recipient-level transport outcomes.

    ``accepted`` means the LINE API/SMTP relay accepted the request. It never
    asserts final device or mailbox delivery.
    """
    if channel not in {"line", "email"}:
        raise ValueError("unsupported_channel")
    safe: list[dict[str, Any]] = []
    for row in recipients:
        if not isinstance(row, dict) or not row.get("recipient"):
            raise ValueError("invalid_recipient_transport_evidence")
        status = str(row.get("status") or "unknown")
        if status not in {"accepted", "rejected", "timeout", "failed", "unknown"}:
            raise ValueError("invalid_recipient_transport_status")
        item = {"recipient_mask": mask_recipient(str(row["recipient"])), "status": status}
        if isinstance(row.get("status_code"), int):
            item["status_code"] = int(row["status_code"])
        if row.get("error_type"):
            item["error_type"] = str(row["error_type"])
        safe.append(item)
    # Multiple LINE chunks are one recipient outcome, not multiple recipients.
    merged: dict[str, dict[str, Any]] = {}
    priority = {"accepted":0, "unknown":1, "failed":2, "rejected":3, "timeout":4}
    for item in safe:
        previous = merged.get(item["recipient_mask"])
        if previous is None or priority[item["status"]] > priority[previous["status"]]:
            merged[item["recipient_mask"]] = item
    safe = list(merged.values())
    states = {item["status"] for item in safe}
    if not safe:
        result = "unknown"
    elif states == {"accepted"}:
        result = "transport_accepted"
    elif "timeout" in states:
        result = "timeout" if len(states) == 1 else "partial_failure"
    elif "accepted" in states:
        result = "partial_failure"
    elif states <= {"rejected", "failed"}:
        result = "failed"
    else:
        result = "unknown"
    return {
        "channel": channel,
        "transport_result": result,
        "recipient_count": len(safe),
        "accepted_recipient_count": sum(item["status"] == "accepted" for item in safe),
        "recipients": safe,
        "attempted_at": attempted_at or datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat(),
        "final_recipient_delivery_confirmed": False,
    }


def deliver_once(*, receipt_root: Path, identity: dict[str, Any], channel: str, sender: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Send at most once for an immutable identity and persist its terminal fact.

    A prior failed/partial/timeout receipt is intentionally not retried here:
    an operator must explicitly approve any later re-delivery plan.
    """
    if channel != identity.get("channel"):
        raise ValueError("receipt_channel_mismatch")
    path = receipt_path(Path(receipt_root), identity)
    if path.exists():
        try:
            retained = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"send_attempted": False, "send_status": "failed", "error_type": "InvalidDeliveryReceipt", "receipt_path": str(path)}
        if not _valid_terminal_receipt(retained, identity):
            return {"send_attempted": False, "send_status": "failed", "error_type": "InvalidDeliveryReceipt", "receipt_path": str(path)}
        status = "already_delivered" if retained["transport_result"] == "transport_accepted" else "suppressed_prior_delivery_attempt"
        return {"send_attempted": False, "send_status": status, "receipt_path": str(path), "receipt": retained}
    # Claim the snapshot/channel before transport. A crash leaves an explicit
    # uncertain attempt; neither concurrent callers nor changed content resend.
    path.parent.mkdir(parents=True, exist_ok=True)
    claim_identity = {k:v for k,v in identity.items() if k != "content_sha256"}
    claim = path.parent / (hashlib.sha256(_canonical(claim_identity).encode()).hexdigest() + ".attempt")
    try:
        fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return {"send_attempted":False, "send_status":"suppressed_prior_delivery_attempt",
                "error_type":"PriorOrInFlightAttempt", "receipt_path":str(path)}
    with os.fdopen(fd, "w") as handle:
        handle.write(_canonical({"identity":identity, "receipt_path":str(path)}))
        handle.flush()
        os.fsync(handle.fileno())
    try:
        raw = dict(sender())
        evidence = build_transport_evidence(
            channel=channel,
            recipients=list(raw.get("recipients") or []),
            attempted_at=raw.get("attempted_at"),
        )
        chunk = raw.get("chunk_delivery")
        if isinstance(chunk, dict) and chunk.get("completed_chunk_count") != chunk.get("chunk_count"):
            for row in evidence["recipients"]:
                if row["status"] == "accepted":
                    row["status"] = "unknown"
            evidence["accepted_recipient_count"] = 0
            evidence["transport_result"] = "unknown"
        if raw.get("chunk_delivery") is not None:
            evidence["chunk_delivery"] = raw["chunk_delivery"]
    except Exception as exc:
        evidence = build_transport_evidence(
            channel=channel,
            recipients=[{"recipient": "unresolved-transport", "status": "timeout" if isinstance(exc, TimeoutError) else "failed", "error_type": type(exc).__name__}],
        )
    receipt = {"schema_version": SCHEMA_VERSION, "identity": identity, **evidence}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    send_status = "sent" if evidence["transport_result"] == "transport_accepted" else "failed"
    return {
        "send_attempted": True,
        "send_status": send_status,
        "receipt_path": str(path),
        "receipt": receipt,
        "recipient_count": evidence["recipient_count"],
        "transport_result": evidence["transport_result"],
        "secret_values_printed": False,
    }
