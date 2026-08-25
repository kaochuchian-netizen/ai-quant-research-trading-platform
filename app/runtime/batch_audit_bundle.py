"""Immutable, non-sensitive seven-window batch audit bundle builder.

The builder consumes already-admitted snapshot, visual and notification evidence.
It never renders notifications again, creates a snapshot revision, or controls
production success.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, admission_errors

SCHEMA_VERSION = "batch_audit_bundle_manifest_v1"
DEFAULT_OUTBOX_ROOT = Path(os.environ.get(
    "STOCK_AI_BATCH_AUDIT_OUTBOX",
    Path(__file__).resolve().parents[2] / "artifacts/runtime/chatgpt_batch_audit_outbox",
))
ALLOWED_VISUAL_FILES = {
    "rendered_page.html": "report.html",
    "dashboard_full.pdf": "report.pdf",
    "screenshot_full.png": "screenshot.png",
}
SECRET_KEY = re.compile(r"(token|secret|password|credential|authorization|cookie|private[_-]?key)", re.I)
SECRET_TEXT = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:token|password|secret)\s*[=:]\s*\S+)"
)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize_text(value: str) -> str:
    return SECRET_TEXT.sub("[REDACTED]", str(value or ""))


def sanitize_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SECRET_KEY.search(str(key)) else sanitize_mapping(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_mapping(item) for item in value]
    return sanitize_text(value) if isinstance(value, str) else value


def contains_secret(value: Any) -> bool:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    return bool(SECRET_TEXT.search(encoded))


def drive_revision_path(snapshot: dict[str, Any]) -> str:
    return "/".join((
        str(snapshot["effective_trading_date"]), str(snapshot["market"]), str(snapshot["window"]),
        f"revision-{int(snapshot['revision']):04d}",
    ))


def idempotency_key(snapshot: dict[str, Any], file_hash: str) -> str:
    raw = "|".join((str(snapshot.get(key) or "") for key in (
        "market", "window", "effective_trading_date", "revision", "snapshot_id",
    ))) + "|" + file_hash
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "market": snapshot.get("market"), "window": snapshot.get("window"),
        "effective_trading_date": snapshot.get("effective_trading_date"),
        "revision": snapshot.get("revision"), "snapshot_id": snapshot.get("snapshot_id"),
        "payload_hash": snapshot.get("payload_hash") or snapshot.get("source_payload_hash"),
    }


def eligibility_errors(snapshot: dict[str, Any], visual_manifest: dict[str, Any]) -> list[str]:
    errors = list(admission_errors(snapshot))
    identity = _identity(snapshot)
    if any(value in (None, "", 0) for value in identity.values()):
        errors.append("incomplete_identity")
    if snapshot.get("market") not in MARKET_WINDOWS or snapshot.get("window") not in MARKET_WINDOWS.get(snapshot.get("market"), ()):
        errors.append("unknown_market_window")
    if snapshot.get("run_kind") in {"fixture", "validator", "test", "failed", "incomplete"}:
        errors.append("ineligible_run_kind")
    for key, value in identity.items():
        manifest_value = visual_manifest.get("payload_hash" if key == "payload_hash" else key)
        if manifest_value != value:
            errors.append(f"visual_identity_{key}")
    if visual_manifest.get("capture", {}).get("status") not in {"SUCCESS", "DEGRADED"}:
        errors.append("visual_not_available")
    return sorted(set(errors))


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + f".tmp-{os.getpid()}")
    shutil.copyfile(source, temporary)
    temporary.replace(destination)


def _delivery_status(snapshot: dict[str, Any], line: dict[str, Any], email: dict[str, Any],
                     dashboard_url: str, duplicate_suppressed: bool) -> dict[str, Any]:
    return sanitize_mapping({
        "schema_version": "batch_audit_delivery_status_v1", **_identity(snapshot),
        "line_attempted": bool(line.get("delivery_attempted")),
        "line_succeeded": line.get("delivery_result") == "sent",
        "email_attempted": bool(email.get("delivery_attempted")),
        "email_succeeded": email.get("delivery_result") == "sent",
        "duplicate_delivery_suppressed": bool(duplicate_suppressed),
        "sent_at": line.get("delivery_time") or email.get("delivery_time"),
        "finished_at": datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat(),
        "presentation_content_hash": {
            "line": line.get("presentation_content_hash"), "email": email.get("presentation_content_hash"),
        },
        "delivery_provenance_identity": {
            "line_snapshot_id": line.get("snapshot_id"), "email_snapshot_id": email.get("snapshot_id"),
        },
        "dashboard_url": dashboard_url,
        "sanitized_error_type": line.get("error_type") or email.get("error_type"),
        "sanitized_error_message": sanitize_text(line.get("error_message") or email.get("error_message") or ""),
    })


def build_batch_audit_bundle(
    *, snapshot: dict[str, Any], visual_manifest_path: Path,
    line_message: str, email_subject: str, email_body: str,
    line_provenance: dict[str, Any], email_provenance: dict[str, Any],
    dashboard_url: str, public_parity_status: str,
    duplicate_delivery_suppressed: bool = False,
    outbox_root: Path = DEFAULT_OUTBOX_ROOT,
) -> dict[str, Any]:
    """Create one durable immutable outbox item from already-rendered evidence."""
    try:
        visual_manifest = json.loads(visual_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "SKIPPED", "reason_code": "VISUAL_MANIFEST_UNAVAILABLE", "production_batch_continues": True}
    errors = eligibility_errors(snapshot, visual_manifest)
    if errors:
        return {"status": "SKIPPED", "reason_code": "BUNDLE_NOT_ELIGIBLE", "errors": errors, "production_batch_continues": True}
    expected_snapshot = snapshot.get("snapshot_id")
    if any(item.get("snapshot_id") != expected_snapshot for item in (line_provenance, email_provenance)):
        return {"status": "SKIPPED", "reason_code": "NOTIFICATION_IDENTITY_MISMATCH", "production_batch_continues": True}
    if contains_secret(line_message) or contains_secret(email_subject) or contains_secret(email_body):
        return {"status": "SKIPPED", "reason_code": "SECRET_PATTERN_DETECTED", "production_batch_continues": True}

    relative = Path(drive_revision_path(snapshot))
    target = outbox_root / relative
    if target.exists():
        existing = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        if existing.get("snapshot_id") == expected_snapshot:
            return {"status": "ENQUEUED", "duplicate_suppressed": True, "outbox_path": str(target),
                    "manifest_path": str(target / "manifest.json"), "production_batch_continues": True}
        return {"status": "CONFLICT", "reason_code": "IMMUTABLE_OUTBOX_CONFLICT", "production_batch_continues": True}

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=str(target.parent)))
    missing: list[dict[str, str]] = []
    try:
        source_root = visual_manifest_path.parent
        for source_name, target_name in ALLOWED_VISUAL_FILES.items():
            source = source_root / source_name
            if source.is_file() and not source.is_symlink():
                _atomic_copy(source, temporary / target_name)
            else:
                missing.append({"file": target_name, "reason": "SOURCE_NOT_AVAILABLE"})
        (temporary / "snapshot.json").write_text(stable_json(sanitize_mapping(snapshot)), encoding="utf-8")
        notifications = temporary / "notifications"; notifications.mkdir()
        (notifications / "line_message.txt").write_text(sanitize_text(line_message), encoding="utf-8")
        (notifications / "email_subject.txt").write_text(sanitize_text(email_subject), encoding="utf-8")
        (notifications / "email_body.html").write_text(sanitize_text(email_body), encoding="utf-8")
        delivery = _delivery_status(snapshot, line_provenance, email_provenance, dashboard_url, duplicate_delivery_suppressed)
        (notifications / "delivery_status.json").write_text(stable_json(delivery), encoding="utf-8")
        missing.append({"file": "notifications/email_preview.pdf", "reason": "ASYNC_RENDER_PENDING"})
        files: dict[str, Any] = {}
        for path in sorted(item for item in temporary.rglob("*") if item.is_file()):
            name = path.relative_to(temporary).as_posix()
            files[name] = {"sha256": sha256(path), "size_bytes": path.stat().st_size,
                           "retention_class": "visual_90_days" if path.suffix in {".pdf", ".png"} else "long_term"}
        manifest = {
            "schema_version": SCHEMA_VERSION, **_identity(snapshot),
            "runtime_provenance": snapshot.get("runtime_provenance"),
            "admission_status": "ADMITTED", "source_file_hashes": (visual_manifest.get("files") or {}),
            "bundle_file_hashes": files, "created_at": snapshot.get("generated_at"), "uploaded_at": None,
            "drive_folder_id": None, "drive_file_ids": {}, "upload_status": "OUTBOX_PENDING",
            "retry_count": 0, "missing_file_reasons": missing,
            "notification_evidence_summary": delivery, "public_parity_status": public_parity_status,
            "cross_market_evidence_count": 0, "secrets_exposed": False,
            "trading_or_order_executed": False, "total_bundle_size": sum(item["size_bytes"] for item in files.values()),
            "retention_class": "mixed_long_term_and_visual_90_days", "drive_relative_path": relative.as_posix(),
        }
        (temporary / "manifest.json").write_text(stable_json(manifest), encoding="utf-8")
        (temporary / "failure.json").write_text(stable_json({
            "schema_version": "batch_audit_failure_v1", "status": "DEGRADED",
            "reason_codes": ["EMAIL_PREVIEW_RENDER_PENDING"] + (["VISUAL_FILE_MISSING"] if missing[:-1] else []),
            "production_batch_continues": True, "secrets_exposed": False,
        }), encoding="utf-8")
        temporary.replace(target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        return {"status": "FAILED_NON_BLOCKING", "reason_code": "BUNDLE_BUILD_FAILED", "production_batch_continues": True}
    return {"status": "ENQUEUED", "duplicate_suppressed": False, "outbox_path": str(target),
            "manifest_path": str(target / "manifest.json"), "production_batch_continues": True}


def enqueue_batch_audit_non_blocking(**kwargs: Any) -> dict[str, Any]:
    if os.environ.get("STOCK_AI_BATCH_AUDIT_ENABLED") != "1":
        return {"status": "DISABLED", "reason_code": "TRANSPORT_NOT_ACTIVATED", "production_batch_continues": True}
    try:
        return build_batch_audit_bundle(**kwargs)
    except Exception:
        return {"status": "FAILED_NON_BLOCKING", "reason_code": "AUDIT_ENQUEUE_FAILED", "production_batch_continues": True}
