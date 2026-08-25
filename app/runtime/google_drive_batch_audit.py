"""Bounded, resumable Google Drive transport for batch-audit outbox items.

Production is disabled by default. My Drive transport uses an explicitly
authorized human user's OAuth refresh token from the approved GCP secret
mechanism. Service accounts and impersonation are intentionally unsupported.
Validators use FakeDriveBackend and never contact Google Drive.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any, Protocol

from app.runtime.batch_audit_bundle import DEFAULT_OUTBOX_ROOT, sha256, stable_json

REFERENCE_FOLDER_ID = "1JCCyIV5fRVepN5hOotxNjq6Xqko1n3hy"
APP_ROOT_NAME = "Stock-AI-Batch-Audit"
UPLOAD_SCHEMA = "google_drive_batch_audit_upload_state_v1"


class DriveBackend(Protocol):
    def root_folder_id(self) -> str: ...
    def ensure_folder(self, parent_id: str, name: str) -> str: ...
    def upload(self, parent_id: str, name: str, path: Path, checksum: str) -> str: ...


class ConflictError(RuntimeError):
    pass


class FakeDriveBackend:
    """Deterministic in-memory backend with immutable content semantics."""
    def __init__(self, *, fail_after: int | None = None) -> None:
        self.folders: dict[tuple[str, str], str] = {}
        self.files: dict[tuple[str, str], dict[str, str]] = {}
        self.calls = 0; self.fail_after = fail_after

    def root_folder_id(self) -> str:
        return "fake-app-owned-root"

    def ensure_folder(self, parent_id: str, name: str) -> str:
        key = (parent_id, name)
        self.folders.setdefault(key, "folder-" + hashlib.sha256("|".join(key).encode()).hexdigest()[:16])
        return self.folders[key]

    def upload(self, parent_id: str, name: str, path: Path, checksum: str) -> str:
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise TimeoutError("fake_drive_unavailable")
        key = (parent_id, name); existing = self.files.get(key)
        if existing and existing["sha256"] != checksum:
            raise ConflictError("content_conflict_no_overwrite")
        if not existing:
            self.files[key] = {"id": "file-" + hashlib.sha256((parent_id + name + checksum).encode()).hexdigest()[:16], "sha256": checksum}
        return self.files[key]["id"]


class GcpSecretManagerOAuthProvider:
    """Load one OAuth client/refresh-token envelope without logging its values."""
    def __init__(self, secret_resource: str | None = None) -> None:
        self.secret_resource = secret_resource or os.environ.get("STOCK_AI_DRIVE_OAUTH_SECRET_RESOURCE", "")

    def credentials(self) -> Any:  # pragma: no cover - production activation gate
        if not self.secret_resource:
            raise RuntimeError("OAUTH_SECRET_RESOURCE_NOT_CONFIGURED")
        try:
            from google.cloud import secretmanager  # type: ignore
            from google.oauth2.credentials import Credentials  # type: ignore
        except ImportError as exc:
            raise RuntimeError("GOOGLE_OAUTH_DEPENDENCY_NOT_INSTALLED") from exc
        response = secretmanager.SecretManagerServiceClient().access_secret_version(name=self.secret_resource)
        try:
            value = json.loads(bytes(response.payload.data).decode("utf-8"))
            required = ("client_id", "client_secret", "refresh_token", "token_uri")
            if any(not value.get(key) for key in required):
                raise RuntimeError("OAUTH_SECRET_CONTRACT_INCOMPLETE")
            return Credentials(
                token=None, refresh_token=value["refresh_token"], token_uri=value["token_uri"],
                client_id=value["client_id"], client_secret=value["client_secret"],
                scopes=["https://www.googleapis.com/auth/drive.file"],
            )
        finally:
            response = None


class GoogleDriveBackend:
    """My Drive adapter using user OAuth and app-owned drive.file content."""
    def __init__(self, provider: GcpSecretManagerOAuthProvider | None = None) -> None:
        try:
            from googleapiclient.discovery import build  # type: ignore
        except ImportError as exc:  # pragma: no cover - production dependency gate
            raise RuntimeError("GOOGLE_DRIVE_DEPENDENCY_NOT_INSTALLED") from exc
        credentials = (provider or GcpSecretManagerOAuthProvider()).credentials()
        self.service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._root_id: str | None = None

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def ensure_folder(self, parent_id: str, name: str) -> str:  # pragma: no cover - activation gate
        query = f"'{self._escape(parent_id)}' in parents and name='{self._escape(name)}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        found = self.service.files().list(q=query, fields="files(id,name)", pageSize=2).execute().get("files", [])
        if found:
            return str(found[0]["id"])
        created = self.service.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}, fields="id").execute()
        return str(created["id"])

    def root_folder_id(self) -> str:  # pragma: no cover - activation gate
        if self._root_id:
            return self._root_id
        query = f"name='{self._escape(APP_ROOT_NAME)}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        found = self.service.files().list(q=query, fields="files(id,name,appProperties)", pageSize=10).execute().get("files", [])
        owned = [item for item in found if (item.get("appProperties") or {}).get("stock_ai_audit_root") == "v1"]
        if owned:
            self._root_id = str(owned[0]["id"])
        else:
            created = self.service.files().create(body={
                "name": APP_ROOT_NAME, "mimeType": "application/vnd.google-apps.folder",
                "appProperties": {"stock_ai_audit_root": "v1"},
            }, fields="id").execute()
            self._root_id = str(created["id"])
        return self._root_id

    def upload(self, parent_id: str, name: str, path: Path, checksum: str) -> str:  # pragma: no cover - activation gate
        from googleapiclient.http import MediaFileUpload  # type: ignore
        app_property = {"stock_ai_sha256": checksum}
        query = f"'{self._escape(parent_id)}' in parents and name='{self._escape(name)}' and trashed=false"
        found = self.service.files().list(q=query, fields="files(id,appProperties)", pageSize=2).execute().get("files", [])
        if found:
            existing = (found[0].get("appProperties") or {}).get("stock_ai_sha256")
            if existing == checksum:
                return str(found[0]["id"])
            raise ConflictError("content_conflict_no_overwrite")
        media = MediaFileUpload(str(path), resumable=True)
        created = self.service.files().create(
            body={"name": name, "parents": [parent_id], "appProperties": app_property},
            media_body=media, fields="id",
        ).execute()
        return str(created["id"])


def credential_discovery_contract() -> dict[str, Any]:
    enabled = os.environ.get("STOCK_AI_BATCH_AUDIT_ENABLED") == "1"
    return {
        "enabled": enabled, "credential_method": "OAUTH2_USER_REFRESH_TOKEN_GCP_SECRET_MANAGER" if enabled else None,
        "reference_folder_id": REFERENCE_FOLDER_ID, "root_folder_strategy": "APP_OWNED_MY_DRIVE_FOLDER",
        "minimum_scope": "drive.file", "service_account_supported": False,
        "impersonation_supported": False, "secret_values_printed": False, "activation_required": not enabled,
    }


def _bounded(call: Any, timeout_seconds: float) -> Any:
    result: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)
    def invoke() -> None:
        try:
            result.put((True, call()), block=False)
        except Exception as exc:
            result.put((False, exc), block=False)
    worker = threading.Thread(target=invoke, name="drive-audit-bounded-call", daemon=True)
    worker.start()
    try:
        ok, value = result.get(timeout=max(0.01, timeout_seconds))
    except queue.Empty as exc:
        raise TimeoutError("drive_call_timeout") from exc
    if not ok:
        raise value
    return value


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def render_email_preview_pdf(bundle: Path, *, renderer: Any | None = None) -> dict[str, Any]:
    """Render the captured Email body asynchronously from the production batch."""
    source = bundle / "notifications/email_body.html"
    destination = bundle / "notifications/email_preview.pdf"
    if destination.is_file() and destination.stat().st_size > 4 and destination.read_bytes().startswith(b"%PDF"):
        return {"status": "SUCCESS", "duplicate_suppressed": True}
    if not source.is_file():
        return {"status": "DEGRADED", "reason_code": "EMAIL_BODY_NOT_AVAILABLE"}
    try:
        if renderer is not None:
            renderer(source, destination)
        else:  # pragma: no cover - real Chromium activation environment
            from playwright.sync_api import sync_playwright  # type: ignore
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_content(source.read_text(encoding="utf-8"), wait_until="load")
                page.pdf(path=str(destination), print_background=True, format="A4")
                browser.close()
        if not destination.is_file() or not destination.read_bytes().startswith(b"%PDF"):
            raise RuntimeError("PDF_WRITE_FAILED")
        manifest_path = bundle / "manifest.json"; manifest = _load(manifest_path)
        relative = "notifications/email_preview.pdf"
        manifest.setdefault("bundle_file_hashes", {})[relative] = {
            "sha256": sha256(destination), "size_bytes": destination.stat().st_size,
            "retention_class": "visual_90_days",
        }
        manifest["missing_file_reasons"] = [item for item in manifest.get("missing_file_reasons", []) if item.get("file") != relative]
        manifest["total_bundle_size"] = sum(int(item.get("size_bytes") or 0) for item in manifest["bundle_file_hashes"].values())
        manifest_path.write_text(stable_json(manifest), encoding="utf-8")
        failure_path = bundle / "failure.json"; failure = _load(failure_path)
        reasons = [reason for reason in failure.get("reason_codes", []) if reason != "EMAIL_PREVIEW_RENDER_PENDING"]
        if reasons:
            failure["reason_codes"] = reasons; failure_path.write_text(stable_json(failure), encoding="utf-8")
        else:
            failure_path.unlink(missing_ok=True)
        return {"status": "SUCCESS", "sha256": sha256(destination), "size_bytes": destination.stat().st_size}
    except Exception as exc:
        return {"status": "DEGRADED", "reason_code": type(exc).__name__.upper()[:80]}


def upload_bundle(bundle: Path, backend: DriveBackend, *, root_folder_id: str | None = None,
                  timeout_seconds: float = 20, max_retries: int = 3) -> dict[str, Any]:
    render_result = render_email_preview_pdf(bundle)
    manifest_path = bundle / "manifest.json"; manifest = _load(manifest_path)
    if manifest.get("schema_version") != "batch_audit_bundle_manifest_v1":
        return {"status": "REJECTED", "reason_code": "INVALID_MANIFEST", "production_batch_continues": True}
    state_path = bundle / "upload_state.json"; state = _load(state_path)
    if state.get("status") == "UPLOADED" and state.get("drive_folder_id"):
        return {"status": "UPLOADED", "drive_folder_id": state["drive_folder_id"],
                "uploaded_file_count": len(state.get("files") or {}),
                "retry_count": int(state.get("retry_count") or 0),
                "duplicate_suppressed": True, "production_batch_continues": True}
    state.setdefault("schema_version", UPLOAD_SCHEMA); state.setdefault("files", {})
    state.setdefault("retry_count", 0); state["status"] = "UPLOADING"
    folder_id = root_folder_id or _bounded(backend.root_folder_id, timeout_seconds)
    try:
        for part in Path(str(manifest["drive_relative_path"])).parts:
            folder_id = _bounded(lambda p=part, parent=folder_id: backend.ensure_folder(parent, p), timeout_seconds)
        paths = sorted(path for path in bundle.rglob("*") if path.is_file() and path.name not in {"upload_state.json", "manifest.json"})
        for path in paths:
            relative = path.relative_to(bundle).as_posix(); digest = sha256(path)
            existing = state["files"].get(relative)
            if existing and existing.get("sha256") == digest and existing.get("drive_file_id"):
                continue
            parent = folder_id
            for part in Path(relative).parts[:-1]:
                parent = _bounded(lambda p=part, base=parent: backend.ensure_folder(base, p), timeout_seconds)
            last_error: Exception | None = None
            for attempt in range(max_retries):
                try:
                    file_id = _bounded(lambda p=path, n=path.name, base=parent, d=digest: backend.upload(base, n, p, d), timeout_seconds)
                    state["files"][relative] = {"drive_file_id": file_id, "sha256": digest, "status": "UPLOADED"}
                    last_error = None; break
                except ConflictError:
                    raise
                except Exception as exc:
                    last_error = exc; state["retry_count"] += 1
                    if attempt + 1 < max_retries:
                        time.sleep(min(0.05 * (2 ** attempt), 0.2))
            if last_error:
                raise last_error
            state_path.write_text(stable_json(state), encoding="utf-8")
        if render_result.get("status") != "SUCCESS":
            state["status"] = "DEGRADED"
            state["reason_code"] = str(render_result.get("reason_code") or "EMAIL_PREVIEW_RENDER_FAILED")
            state["drive_folder_id"] = folder_id
            state_path.write_text(stable_json(state), encoding="utf-8")
            return {"status": "DEGRADED", "reason_code": state["reason_code"],
                    "uploaded_file_count": len(state["files"]), "retry_count": state["retry_count"],
                    "production_batch_continues": True}
        manifest["drive_folder_id"] = folder_id
        manifest["drive_file_ids"] = {key: value["drive_file_id"] for key, value in state["files"].items()}
        manifest["upload_status"] = "UPLOADED"; manifest["retry_count"] = state["retry_count"]
        manifest["uploaded_at"] = datetime_now()
        manifest_path.write_text(stable_json(manifest), encoding="utf-8")
        manifest_digest = sha256(manifest_path)
        manifest_id = _bounded(lambda: backend.upload(folder_id, "manifest.json", manifest_path, manifest_digest), timeout_seconds)
        state["files"]["manifest.json"] = {"drive_file_id": manifest_id, "sha256": manifest_digest, "status": "UPLOADED"}
        state["status"] = "UPLOADED"; state["drive_folder_id"] = folder_id
        state_path.write_text(stable_json(state), encoding="utf-8")
        return {"status": "UPLOADED", "drive_folder_id": folder_id, "uploaded_file_count": len(state["files"]),
                "retry_count": state["retry_count"], "production_batch_continues": True}
    except ConflictError:
        state["status"] = "CONFLICT"; state["reason_code"] = "CONTENT_CONFLICT_NO_OVERWRITE"
    except Exception as exc:
        state["status"] = "DEGRADED"; state["reason_code"] = type(exc).__name__.upper()[:80]
    state_path.write_text(stable_json(state), encoding="utf-8")
    return {"status": state["status"], "reason_code": state.get("reason_code"),
            "retry_count": state["retry_count"], "production_batch_continues": True}


def datetime_now() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat()


def process_outbox(backend: DriveBackend, *, outbox_root: Path = DEFAULT_OUTBOX_ROOT,
                   timeout_seconds: float = 20, max_retries: int = 3) -> dict[str, Any]:
    results = []
    for manifest in sorted(outbox_root.rglob("manifest.json")) if outbox_root.exists() else []:
        results.append(upload_bundle(manifest.parent, backend, timeout_seconds=timeout_seconds, max_retries=max_retries))
    return {"status": "PASS" if all(item["status"] == "UPLOADED" for item in results) else "DEGRADED",
            "bundle_count": len(results), "results": results, "production_batch_continues": True}


def process_outbox_non_blocking(*, outbox_root: Path = DEFAULT_OUTBOX_ROOT) -> dict[str, Any]:
    if os.environ.get("STOCK_AI_BATCH_AUDIT_ENABLED") != "1":
        return {"status": "DISABLED", "reason_code": "TRANSPORT_NOT_ACTIVATED", "production_batch_continues": True}
    try:
        return process_outbox(GoogleDriveBackend(), outbox_root=outbox_root)
    except Exception as exc:
        return {"status": "DEGRADED", "reason_code": type(exc).__name__.upper()[:80], "production_batch_continues": True}
