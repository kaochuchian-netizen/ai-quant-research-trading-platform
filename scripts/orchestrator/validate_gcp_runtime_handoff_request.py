#!/usr/bin/env python3
"""Validate a GCP runtime handoff request.

The request is a repo-side contract for a GCP resident runner or n8n relay. This
validator is read-only and never contacts GCP, n8n, Dify, or external services.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = [
    "schema_version",
    "request_id",
    "ai_dev_id",
    "created_at",
    "created_by",
    "repo_ref",
    "runtime_target",
    "request_type",
    "allowed_runtime_actions",
    "forbidden_runtime_actions",
    "expected_inputs",
    "expected_outputs",
    "local_only_paths_allowed",
    "local_only_paths_forbidden",
    "safety_gates",
    "result_collection",
    "blocked_policy",
    "notes",
]

REQUIRED_FORBIDDEN_ACTIONS = {
    "order_execution",
    "secret_read_or_print",
    "line_email_delivery",
    "production_db_mutation",
}

SECRET_PATTERNS = [
    "API_KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PRIVATE_KEY",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    ".env",
]

SECRET_VALUE_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"xoxb-[A-Za-z0-9-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,}]+"),
]

REQUEST_ID_RE = re.compile(r"^gcp-runtime-handoff-[a-z0-9-]+$")
AI_DEV_RE = re.compile(r"^AI-DEV-\d{3}$")


def load_request(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"failed to parse JSON request: {exc}"]
    if not isinstance(data, dict):
        return None, ["request root must be a JSON object"]
    return data, []


def flatten_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def listify(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def validate_request(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    for field in missing:
        errors.append(f"missing required field: {field}")

    request_id = str(data.get("request_id", ""))
    ai_dev_id = str(data.get("ai_dev_id", ""))
    if not REQUEST_ID_RE.match(request_id):
        errors.append("request_id must match gcp-runtime-handoff-<lowercase-token>")
    if not AI_DEV_RE.match(ai_dev_id):
        errors.append("ai_dev_id must match AI-DEV-###")

    forbidden_actions = set(str(item) for item in listify(data.get("forbidden_runtime_actions")))
    missing_forbidden = sorted(REQUIRED_FORBIDDEN_ACTIONS - forbidden_actions)
    for action in missing_forbidden:
        errors.append(f"missing required forbidden runtime action: {action}")

    allowed_actions = [str(item).lower() for item in listify(data.get("allowed_runtime_actions"))]
    connection_text = " ".join(allowed_actions + [str(item).lower() for item in listify(data.get("notes"))])
    if "ssh" in connection_text:
        errors.append("request must not require SSH from Codex App")
    if any("notification" in item or "email" in item or "line" in item for item in allowed_actions):
        errors.append("allowed runtime actions must not include external delivery")
    if any("order" in item or "trade" in item or "trading" in item for item in allowed_actions):
        errors.append("allowed runtime actions must not include trading or order execution")
    if any("production_db" in item or "production-db" in item for item in allowed_actions):
        errors.append("allowed runtime actions must not include production DB mutation")

    text = flatten_text(data)
    secret_pattern_hits = [pattern for pattern in SECRET_PATTERNS if pattern in text]
    value_hits: list[str] = []
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(text):
            value_hits.append(pattern.pattern)
    if secret_pattern_hits:
        errors.append("request contains forbidden secret marker text")
    if value_hits:
        errors.append("request appears to include sensitive values")

    result_collection = data.get("result_collection", {})
    if not isinstance(result_collection, dict):
        errors.append("result_collection must be an object")
    else:
        if not result_collection.get("sanitized_result_required", False):
            errors.append("result_collection.sanitized_result_required must be true")
        if result_collection.get("raw_runtime_output_repo_allowed", True):
            errors.append("result_collection.raw_runtime_output_repo_allowed must be false")

    safety_gates = data.get("safety_gates", {})
    if not isinstance(safety_gates, dict):
        errors.append("safety_gates must be an object")
    else:
        for key in [
            "no_order_execution",
            "no_secret_values",
            "no_external_delivery",
            "no_production_db_mutation",
            "no_codex_app_direct_connection",
        ]:
            if safety_gates.get(key) is not True:
                errors.append(f"safety_gates.{key} must be true")

    return {
        "ok": not errors,
        "request_id": request_id or None,
        "ai_dev_id": ai_dev_id or None,
        "errors": errors,
        "warnings": warnings,
        "secret_pattern_hits": secret_pattern_hits,
        "values_included_or_printed": bool(value_hits),
        "value_hit_patterns": value_hits,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a GCP runtime handoff request JSON file.")
    parser.add_argument("--request", default="templates/gcp_runtime_handoff_request.example.json")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request_path = Path(args.request)
    data, load_errors = load_request(request_path)
    if data is None:
        result = {
            "ok": False,
            "request_id": None,
            "ai_dev_id": None,
            "errors": load_errors,
            "warnings": [],
            "secret_pattern_hits": [],
            "values_included_or_printed": False,
        }
    else:
        result = validate_request(data)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
