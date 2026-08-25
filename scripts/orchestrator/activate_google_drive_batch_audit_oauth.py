#!/usr/bin/env python3
"""One-time interactive OAuth helper for the AI-DEV-222 production hard gate.

This command is intentionally never called by validators or batch runners. It
prints no token. The operator supplies an OAuth Desktop client JSON and an
approved Secret Manager resource; the resulting refresh-token envelope is sent
to Secret Manager over stdin and is not written to the repository.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/drive.file"


def main() -> int:  # pragma: no cover - requires PM interactive authorization
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oauth-client-json", type=Path, required=True)
    parser.add_argument("--secret-resource", required=True, help="projects/.../secrets/... (existing approved secret)")
    args = parser.parse_args()
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    except ImportError as exc:
        raise SystemExit("google-auth-oauthlib is required for controlled activation") from exc
    flow = InstalledAppFlow.from_client_secrets_file(str(args.oauth_client_json), scopes=[SCOPE])
    credentials = flow.run_local_server(open_browser=False, access_type="offline", prompt="consent")
    envelope = {
        "client_id": credentials.client_id, "client_secret": credentials.client_secret,
        "refresh_token": credentials.refresh_token, "token_uri": credentials.token_uri,
        "scope": SCOPE, "credential_type": "oauth2_user_refresh_token",
    }
    if not envelope["refresh_token"]:
        raise SystemExit("OAuth provider did not issue a refresh token; activation aborted")
    secret_name = args.secret_resource.split("/secrets/", 1)[-1]
    project = args.secret_resource.split("/projects/", 1)[-1].split("/", 1)[0]
    completed = subprocess.run(
        ["gcloud", "secrets", "versions", "add", secret_name, "--project", project, "--data-file=-"],
        input=json.dumps(envelope, separators=(",", ":")), text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    envelope = {}; credentials = None
    if completed.returncode != 0:
        raise SystemExit("Secret Manager write failed; no credential value was printed")
    print(json.dumps({"status": "OAUTH_ACTIVATED", "scope": "drive.file", "secret_resource": args.secret_resource,
                      "secret_values_printed": False, "service_account_used": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
