#!/usr/bin/env python3
"""Deterministic AI-DEV-222 fixed-loopback OAuth activation validator."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

from activate_google_drive_batch_audit_oauth import (
    ActivationError,
    DEFAULT_CALLBACK_PORT,
    LOOPBACK_HOST,
    SCOPE,
    require_loopback_port_available,
    request_credentials,
    store_credentials,
)

ROOT = Path(__file__).resolve().parents[2]


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


class FakeFlow:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.kwargs: dict[str, object] = {}

    def run_local_server(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def main() -> int:
    cases: dict[str, str] = {}
    credentials = SimpleNamespace(client_id="client-id", client_secret="client-secret",
                                  refresh_token="refresh-token", token_uri="https://oauth2.googleapis.com/token")
    with tempfile.TemporaryDirectory(prefix="ai-dev-222-oauth-") as raw:
        oauth_json = Path(raw) / "oauth-client.json"
        oauth_json.write_text("{}", encoding="utf-8")
        flow = FakeFlow(credentials)
        callback_port = 18765
        returned = request_credentials(oauth_json, callback_port, 17,
                                       flow_factory=lambda *_args, **_kwargs: flow,
                                       port_checker=lambda _port: None)
        require(returned is credentials, "credentials not returned")
        require(DEFAULT_CALLBACK_PORT == 8765 and flow.kwargs["host"] == "127.0.0.1"
                and flow.kwargs["port"] == callback_port,
                "fixed loopback callback absent")
        require(flow.kwargs["open_browser"] is False and flow.kwargs["timeout_seconds"] == 17,
                "interactive/timeout contract")
        require("{url}" in str(flow.kwargs["authorization_prompt_message"]), "authorization URL hidden")
        require(flow.kwargs["access_type"] == "offline" and flow.kwargs["prompt"] == "consent",
                "refresh-token consent contract")
        cases["fixed_loopback_url_and_timeout"] = "PASS"

        class OccupiedSocket:
            def bind(self, _address: object) -> None:
                raise OSError("occupied")
            def close(self) -> None:
                pass
        try:
            require_loopback_port_available(8765, socket_factory=lambda *_args: OccupiedSocket())
        except ActivationError as exc:
            require(str(exc) == "callback_port_occupied", "occupied port not fail closed")
        else:
            raise AssertionError("occupied port accepted")
        cases["callback_port_occupied"] = "PASS"

        for failure, reason in ((KeyboardInterrupt(), "oauth_activation_cancelled"),
                                (TimeoutError(), "oauth_callback_timeout"),
                                (RuntimeError("token=must-not-leak"), "oauth_authorization_failed")):
            broken = FakeFlow(failure)
            try:
                request_credentials(oauth_json, 18766, 1,
                                    flow_factory=lambda *_args, _broken=broken, **_kwargs: _broken,
                                    port_checker=lambda _port: None)
            except ActivationError as exc:
                require(str(exc) == reason and "token" not in str(exc), f"unsafe failure: {reason}")
            else:
                raise AssertionError(f"failure accepted: {reason}")
        cases["cancel_timeout_and_authorization_failure"] = "PASS"

        captured: dict[str, object] = {}
        def runner(command: list[str], **kwargs: object) -> object:
            captured.update(command=command, kwargs=kwargs)
            return SimpleNamespace(returncode=1)
        try:
            store_credentials(credentials, "projects/trading-agent-493803/secrets/stock-ai-drive-oauth", runner=runner)
        except ActivationError as exc:
            require(str(exc) == "secret_manager_write_failed", "Secret Manager failure not closed")
        else:
            raise AssertionError("Secret Manager failure accepted")
        options = captured["kwargs"]
        require(isinstance(options, dict) and options["stdout"] is subprocess.DEVNULL
                and options["stderr"] is subprocess.DEVNULL, "credential command output exposed")
        require("refresh-token" in str(options["input"]), "credential envelope not sent via stdin")
        cases["secret_manager_stdin_and_failure"] = "PASS"

    helper = (ROOT / "scripts/orchestrator/activate_google_drive_batch_audit_oauth.py").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/runbooks/google_drive_batch_audit_transport_v1.md").read_text(encoding="utf-8")
    require('LOOPBACK_HOST = "127.0.0.1"' in helper and '"0.0.0.0"' not in helper,
            "non-loopback bind present")
    require("ssh -L 8765:127.0.0.1:8765" in runbook and "--callback-port 8765" in runbook,
            "Mac tunnel runbook absent")
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    require(not any("oauth-client.json" in path or "client_secret" in path.lower() for path in tracked),
            "OAuth client JSON tracked")
    require("STOCK_AI_BATCH_AUDIT_ENABLED=1" not in helper, "helper enabled uploader")
    cases["source_secret_and_disabled_guards"] = "PASS"

    print(json.dumps({"schema_version": "ai_dev_222_oauth_loopback_hard_gate_v1",
                      "status": "PASS", "case_count": len(cases), "cases": cases,
                      "oauth_activated": False, "drive_network_used": False,
                      "secret_values_printed": False, "production_mutation": False},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"schema_version": "ai_dev_222_oauth_loopback_hard_gate_v1",
                          "status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(2)
