#!/usr/bin/env python3
"""One-time fixed-loopback OAuth activation for the AI-DEV-222 hard gate."""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

SCOPE = "https://www.googleapis.com/auth/drive.file"
LOOPBACK_HOST = "127.0.0.1"
DEFAULT_CALLBACK_PORT = 8765
DEFAULT_TIMEOUT_SECONDS = 300


class ActivationError(RuntimeError):
    """Sanitized operator-facing activation failure."""


def validate_secret_resource(value: str) -> tuple[str, str]:
    if not value.startswith("projects/") or "/secrets/" not in value:
        raise ActivationError("invalid_secret_resource")
    project, secret_name = value[len("projects/"):].split("/secrets/", 1)
    if not project or not secret_name or "/" in secret_name:
        raise ActivationError("invalid_secret_resource")
    return project, secret_name


def require_loopback_port_available(port: int, *, socket_factory: Callable[..., Any] = socket.socket) -> None:
    if not 1024 <= port <= 65535:
        raise ActivationError("invalid_callback_port")
    probe = socket_factory(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((LOOPBACK_HOST, port))
    except OSError as exc:
        raise ActivationError("callback_port_occupied") from exc
    finally:
        probe.close()


def request_credentials(
    oauth_client_json: Path,
    callback_port: int,
    timeout_seconds: int,
    *,
    flow_factory: Callable[..., Any] | None = None,
    port_checker: Callable[[int], None] = require_loopback_port_available,
) -> Any:
    port_checker(callback_port)
    if not oauth_client_json.is_file():
        raise ActivationError("oauth_client_json_not_found")
    if flow_factory is None:
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
        except ImportError as exc:
            raise ActivationError("google_auth_oauthlib_not_installed") from exc
        flow_factory = InstalledAppFlow.from_client_secrets_file
    flow = flow_factory(str(oauth_client_json), scopes=[SCOPE])
    try:
        return flow.run_local_server(
            host=LOOPBACK_HOST,
            port=callback_port,
            open_browser=False,
            access_type="offline",
            prompt="consent",
            timeout_seconds=timeout_seconds,
            authorization_prompt_message="Open this authorization URL in the tunneled Mac browser:\n{url}",
            success_message="Authorization received. Return to the terminal; no credential value was displayed.",
        )
    except KeyboardInterrupt as exc:
        raise ActivationError("oauth_activation_cancelled") from exc
    except TimeoutError as exc:
        raise ActivationError("oauth_callback_timeout") from exc
    except OSError as exc:
        raise ActivationError("oauth_loopback_server_failed") from exc
    except Exception as exc:
        raise ActivationError("oauth_authorization_failed") from exc


def store_credentials(credentials: Any, secret_resource: str, *, runner: Callable[..., Any] = subprocess.run) -> None:
    if not getattr(credentials, "refresh_token", None):
        raise ActivationError("oauth_refresh_token_missing")
    project, secret_name = validate_secret_resource(secret_resource)
    envelope = {
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "scope": SCOPE,
        "credential_type": "oauth2_user_refresh_token",
    }
    try:
        completed = runner(
            ["gcloud", "secrets", "versions", "add", secret_name, "--project", project, "--data-file=-"],
            input=json.dumps(envelope, separators=(",", ":")), text=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    finally:
        envelope.clear()
    if completed.returncode != 0:
        raise ActivationError("secret_manager_write_failed")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--oauth-client-json", type=Path, required=True)
    result.add_argument("--secret-resource", required=True, help="projects/.../secrets/... (existing approved secret)")
    result.add_argument("--callback-port", type=int, default=DEFAULT_CALLBACK_PORT)
    result.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return result


def main() -> int:  # pragma: no cover - interactive production hard gate
    args = parser().parse_args()
    try:
        credentials = request_credentials(args.oauth_client_json, args.callback_port, args.timeout_seconds)
        store_credentials(credentials, args.secret_resource)
        credentials = None
    except ActivationError as exc:
        print(json.dumps({"status": "OAUTH_ACTIVATION_FAILED", "reason_code": str(exc),
                          "secret_values_printed": False}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"status": "OAUTH_ACTIVATED", "scope": "drive.file",
                      "secret_resource": args.secret_resource, "callback_host": LOOPBACK_HOST,
                      "callback_port": args.callback_port, "secret_values_printed": False,
                      "service_account_used": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
