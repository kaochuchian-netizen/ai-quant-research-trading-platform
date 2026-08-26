#!/usr/bin/env python3
"""Deterministic AI-DEV-222 Secret Manager access hard-gate validator."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime.google_drive_batch_audit import (  # noqa: E402
    GcpSecretManagerOAuthProvider,
    credential_discovery_contract,
    normalize_secret_version_resource,
    secret_manager_failure_reason,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class ScopeFailure(Exception):
    reason = "ACCESS_TOKEN_SCOPE_INSUFFICIENT"


class PermissionFailure(Exception):
    reason = "PERMISSION_DENIED"


def main() -> dict[str, object]:
    cases: list[str] = []
    base = "projects/trading-agent-493803/secrets/stock-ai-drive-oauth"
    require(normalize_secret_version_resource(base) == base + "/versions/latest", "base secret not normalized")
    require(normalize_secret_version_resource(base + "/versions/latest") == base + "/versions/latest", "latest changed")
    require(normalize_secret_version_resource(base + "/versions/7") == base + "/versions/7", "numeric rollback version changed")
    cases += ["base_to_latest", "explicit_latest", "numeric_rollback_version"]

    for invalid in ("", base + "/versions/0", base + "/versions/previous", "projects/p/secrets/s/extra"):
        try:
            normalize_secret_version_resource(invalid)
        except RuntimeError as exc:
            require(str(exc) == "OAUTH_SECRET_RESOURCE_INVALID", "invalid resource leaked details")
        else:
            raise AssertionError("invalid secret resource accepted")
    cases.append("invalid_alias_fail_closed")

    provider = GcpSecretManagerOAuthProvider(base)
    require(provider.secret_resource.endswith("/versions/latest"), "provider bypassed normalization")
    require(secret_manager_failure_reason(ScopeFailure("token text must not escape")) == "SECRET_ACCESS_TOKEN_SCOPE_INSUFFICIENT", "scope reason missing")
    require(secret_manager_failure_reason(PermissionFailure("policy detail must not escape")) == "SECRET_ACCESS_PERMISSION_DENIED", "permission reason missing")
    cases += ["provider_normalization", "sanitized_scope_reason", "sanitized_permission_reason"]

    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    pins = (
        "google-cloud-secret-manager==2.29.0",
        "protobuf==5.29.6",
        "grpc-google-iam-v1==0.14.4",
        "grpcio-status==1.71.2",
    )
    require(all(pin in requirements.splitlines() for pin in pins), "compatible dependency pin set incomplete")
    cases.append("dependency_compatibility_pins")

    old = os.environ.pop("STOCK_AI_BATCH_AUDIT_ENABLED", None)
    try:
        contract = credential_discovery_contract()
    finally:
        if old is not None:
            os.environ["STOCK_AI_BATCH_AUDIT_ENABLED"] = old
    require(contract["enabled"] is False and contract["activation_required"] is True, "uploader not disabled by default")
    require(contract["service_account_supported"] is False and contract["impersonation_supported"] is False, "prohibited identity path enabled")
    cases += ["uploader_default_disabled", "service_account_and_impersonation_prohibited"]

    runbook = (ROOT / "docs/runbooks/google_drive_batch_audit_transport_v1.md").read_text(encoding="utf-8")
    audit = (ROOT / "docs/governance/ai_dev_222_secret_access_infrastructure_hard_gate_v1.md").read_text(encoding="utf-8")
    require("/versions/latest" in runbook and "/versions/7" in runbook, "latest/numeric rollback contract undocumented")
    require("ACCESS_TOKEN_SCOPE_INSUFFICIENT" in audit, "confirmed infrastructure evidence absent")
    for forbidden in ("service-account JSON key", "human ADC on the VM", "plaintext refresh token"):
        require(forbidden in audit, f"prohibition missing: {forbidden}")
    cases += ["runbook_version_contract", "infrastructure_evidence_and_prohibitions"]

    return {"schema_version": "ai_dev_222_secret_access_hard_gate_v1", "ok": True, "status": "PASS", "case_count": len(cases), "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        result = main()
    except Exception as exc:
        result = {"schema_version": "ai_dev_222_secret_access_hard_gate_v1", "ok": False, "status": "FAIL", "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
