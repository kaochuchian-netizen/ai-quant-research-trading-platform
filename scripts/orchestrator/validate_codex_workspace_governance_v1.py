#!/usr/bin/env python3
"""Validate AI-DEV-135 Codex workspace governance artifacts."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs/ai_dev_135_codex_workspace_governance_v1.md"
TEMPLATE_PATH = REPO_ROOT / "templates/codex_workspace_governance.example.json"
SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"ghp_[A-Za-z0-9]+",
        r"github_pat_[A-Za-z0-9_]+",
        r"sk-[A-Za-z0-9]+",
        r"BEGIN (RSA|OPENSSH) PRIVATE KEY",
        r"api[_-]?key\s*[:=]",
        r"access[_-]?token\s*[:=]",
        r"password\s*[:=]",
    ]
]


def _secret_hits(text: str) -> list[str]:
    return [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]


def validate() -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    for path in [DOC_PATH, TEMPLATE_PATH]:
        if not path.exists():
            errors.append(f"missing required file: {path.relative_to(REPO_ROOT)}")
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}

    doc = DOC_PATH.read_text(encoding="utf-8")
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = json.loads(template_text)

    required_doc_phrases = [
        "GitHub is the only source of truth",
        "GCP VM repository",
        "stock-ai-gcp",
        "cd ~/stock-ai",
        "Codex App's `stock-ai` workspace",
        "wimac` workspace is retained only for historical chats",
        "Do not modify MacBook / iPhone local workspaces",
        "No external APIs",
        "No secrets",
        "No LINE/Email",
        "No production logic",
    ]
    for phrase in required_doc_phrases:
        if phrase not in doc:
            errors.append(f"doc missing required phrase: {phrase}")

    if payload.get("schema_version") != "codex_workspace_governance_v1":
        errors.append("schema_version mismatch")
    if payload.get("task_id") != "AI-DEV-135":
        errors.append("task_id mismatch")
    if payload.get("source_of_truth", {}).get("system") != "github":
        errors.append("GitHub must be source of truth")
    exec_ws = payload.get("formal_execution_workspace", {})
    if exec_ws.get("host_alias") != "stock-ai-gcp" or exec_ws.get("repo_path") != "~/stock-ai":
        errors.append("formal execution workspace must be stock-ai-gcp ~/stock-ai")
    app_ws = payload.get("codex_app_workspace", {})
    if app_ws.get("workspace_name") != "stock-ai" or app_ws.get("repo_mutation_allowed_locally") is not False:
        errors.append("Codex App stock-ai workspace policy invalid")
    historical = payload.get("historical_workspace", {})
    if historical.get("workspace_name") != "wimac" or historical.get("new_ai_dev_repo_mutation_allowed") is not False:
        errors.append("wimac historical workspace policy invalid")
    rule = payload.get("future_task_opening_rule", {})
    for key in ["must_ssh_to_gcp", "must_cd_to_gcp_repo", "must_not_modify_macbook_workspace", "must_not_modify_iphone_workspace", "github_is_merge_gate_source_of_truth"]:
        if rule.get(key) is not True:
            errors.append(f"future task rule must be true: {key}")
    safety = payload.get("safety_summary", {})
    for key in ["external_api_called", "secrets_read", "scheduler_modified", "line_email_sent", "dashboard_published", "db_written", "broker_order_trading", "production_logic_changed"]:
        if safety.get(key) is not False:
            errors.append(f"safety flag must be false: {key}")
    for label, text in [("doc", doc), ("template", template_text)]:
        hits = _secret_hits(text)
        if hits:
            errors.append(f"secret-like pattern in {label}: {hits}")

    return {
        "ok": not errors,
        "task_id": "AI-DEV-135",
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "source_of_truth": payload.get("source_of_truth", {}).get("system"),
            "formal_execution_workspace": exec_ws.get("host_alias"),
            "repo_path": exec_ws.get("repo_path"),
            "historical_workspace": historical.get("workspace_name"),
            "secret_pattern_hits": 0 if not errors else "see_errors",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
