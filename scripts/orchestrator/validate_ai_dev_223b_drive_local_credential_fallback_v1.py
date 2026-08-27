#!/usr/bin/env python3
"""AI-DEV-223B protected local OAuth credential and precedence gate."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime.google_drive_batch_audit import (  # noqa: E402
    CredentialContractError,
    FakeDriveBackend,
    GcpSecretManagerOAuthProvider,
    GoogleDriveBackend,
    LocalProtectedOAuthProvider,
    process_outbox_non_blocking,
    upload_bundle,
)

SCHEMA = "ai_dev_223b_drive_local_credential_fallback_v1"
SENSITIVE = ("client-id-sentinel", "client-secret-sentinel", "refresh-token-sentinel")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def envelope() -> dict[str, str]:
    return {
        "client_id": SENSITIVE[0],
        "client_secret": SENSITIVE[1],
        "refresh_token": SENSITIVE[2],
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def write_credential(path: Path, value: object, mode: int = 0o600) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(mode)


def expect_reason(provider: LocalProtectedOAuthProvider, reason: str) -> str:
    try:
        provider.credentials()
    except CredentialContractError as exc:
        require(exc.reason_code == reason, f"expected {reason}, got {exc.reason_code}")
        return str(exc)
    raise AssertionError(f"expected {reason}")


def minimal_bundle(root: Path) -> tuple[Path, Path]:
    source = root / "immutable-source.html"
    source.write_text("source-preserved", encoding="utf-8")
    bundle = root / "bundle"
    (bundle / "notifications").mkdir(parents=True)
    (bundle / "report.html").write_text("audit", encoding="utf-8")
    (bundle / "notifications" / "email_preview.pdf").write_bytes(b"%PDF-valid")
    (bundle / "manifest.json").write_text(json.dumps({
        "schema_version": "batch_audit_bundle_manifest_v1",
        "drive_relative_path": "2026-08-27/TW/pre_open_0700/revision-0001",
    }), encoding="utf-8")
    return bundle, source


def fake_google_api_modules(build: Mock) -> dict[str, ModuleType]:
    package = ModuleType("googleapiclient")
    discovery = ModuleType("googleapiclient.discovery")
    discovery.build = build  # type: ignore[attr-defined]
    package.discovery = discovery  # type: ignore[attr-defined]
    return {"googleapiclient": package, "googleapiclient.discovery": discovery}


def main() -> int:
    cases: list[str] = []
    captured = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="ai-dev-223b-") as raw, contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        base = Path(raw)
        valid = base / "oauth.json"
        write_credential(valid, envelope())
        credentials = LocalProtectedOAuthProvider(valid).credentials()
        require(credentials.refresh_token == SENSITIVE[2], "valid local credential not loaded")
        require(credentials.scopes == ["https://www.googleapis.com/auth/drive.file"], "scope drift")
        cases += ["valid_local_credential", "drive_file_scope"]

        reasons = []
        reasons.append(expect_reason(LocalProtectedOAuthProvider(base / "missing.json"), "OAUTH_CREDENTIAL_FILE_UNAVAILABLE"))
        malformed = base / "malformed.json"; malformed.write_text("{", encoding="utf-8"); malformed.chmod(0o600)
        reasons.append(expect_reason(LocalProtectedOAuthProvider(malformed), "OAUTH_CREDENTIAL_FILE_MALFORMED"))
        incomplete = base / "incomplete.json"; write_credential(incomplete, {"client_id": "present"})
        reasons.append(expect_reason(LocalProtectedOAuthProvider(incomplete), "OAUTH_CREDENTIAL_CONTRACT_INCOMPLETE"))
        bad_uri = base / "bad-uri.json"; bad = envelope(); bad["token_uri"] = "http://example.invalid/token"; write_credential(bad_uri, bad)
        reasons.append(expect_reason(LocalProtectedOAuthProvider(bad_uri), "OAUTH_TOKEN_URI_INVALID"))
        insecure = base / "insecure.json"; write_credential(insecure, envelope(), 0o644)
        reasons.append(expect_reason(LocalProtectedOAuthProvider(insecure), "OAUTH_CREDENTIAL_FILE_PERMISSIONS_UNSAFE"))
        symlink = base / "oauth-link.json"; symlink.symlink_to(valid)
        reasons.append(expect_reason(LocalProtectedOAuthProvider(symlink), "OAUTH_CREDENTIAL_FILE_SYMLINK_REJECTED"))
        cases += ["missing_file", "malformed_json", "missing_field", "invalid_token_uri", "permission_gate", "symlink_gate"]

        with patch.dict(os.environ, {"STOCK_AI_BATCH_AUDIT_ENABLED": "0"}, clear=False):
            disabled = process_outbox_non_blocking(credential_provider=LocalProtectedOAuthProvider(base / "absent.json"))
        require(disabled["status"] == "DISABLED", "disabled mode touched explicit credential")
        cases.append("default_disabled")

        no_network_build = Mock(return_value=object())
        with patch.dict(os.environ, {"STOCK_AI_BATCH_AUDIT_ENABLED": "1"}, clear=False), \
                patch.dict(sys.modules, fake_google_api_modules(no_network_build)), \
                patch.object(GcpSecretManagerOAuthProvider, "credentials", side_effect=AssertionError("fallback-used")):
            explicit_failure = process_outbox_non_blocking(
                outbox_root=base / "empty-outbox",
                credential_provider=LocalProtectedOAuthProvider(base / "absent.json"),
            )
        require(explicit_failure["reason_code"] == "OAUTH_CREDENTIAL_FILE_UNAVAILABLE", "explicit source fell back")
        cases.append("explicit_invalid_no_fallback")

        fake_service = object(); build = Mock(return_value=fake_service)
        with patch.dict(sys.modules, fake_google_api_modules(build)):
            backend = GoogleDriveBackend(LocalProtectedOAuthProvider(valid))
        require(backend.service is fake_service and build.call_count == 1, "Drive client construction path")
        cases.append("drive_client_construction_no_network")

        response = SimpleNamespace(payload=SimpleNamespace(data=json.dumps(envelope()).encode("utf-8")))
        fake_client = SimpleNamespace(access_secret_version=lambda **_: response)
        import google  # type: ignore
        cloud_module = ModuleType("google.cloud")
        secret_module = ModuleType("google.cloud.secretmanager")
        secret_module.SecretManagerServiceClient = Mock(return_value=fake_client)  # type: ignore[attr-defined]
        cloud_module.secretmanager = secret_module  # type: ignore[attr-defined]
        with patch.object(google, "cloud", cloud_module, create=True), patch.dict(sys.modules, {
            "google.cloud": cloud_module, "google.cloud.secretmanager": secret_module,
        }):
            secret_credentials = GcpSecretManagerOAuthProvider(
                "projects/trading-agent-493803/secrets/stock-ai-drive-oauth/versions/1"
            ).credentials()
        require(secret_credentials.client_id == SENSITIVE[0], "Secret Manager backend regression")
        cases.append("secret_manager_mock_retained")

        bundle, source = minimal_bundle(base)
        source_before = source.read_bytes()
        drive = FakeDriveBackend()
        first = upload_bundle(bundle, drive)
        second = upload_bundle(bundle, drive)
        require(first["status"] == "UPLOADED" and second.get("duplicate_suppressed") is True, "duplicate replay")
        require(source.read_bytes() == source_before, "source artifact mutated")
        cases += ["duplicate_replay", "source_preservation"]

        diagnostic_text = " ".join(reasons + [json.dumps(disabled), json.dumps(explicit_failure), captured.getvalue()])
        require(not any(secret in diagnostic_text for secret in SENSITIVE), "secret leaked to diagnostics")
        cases.append("secret_leakage_prevention")

    result = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "case_count": len(cases),
        "cases": cases,
        "network_used": False,
        "oauth_authorized": False,
        "production_credential_created": False,
        "drive_upload_executed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
