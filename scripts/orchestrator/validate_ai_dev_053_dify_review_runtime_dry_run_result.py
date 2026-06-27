#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/ai_dev_053_dify_review_runtime_dry_run_result.md"
TPL = ROOT / "templates/ai_dev_053_dify_review_runtime_dry_run_result.example.json"
REQ = [
    "task_id", "runtime_dry_run", "fallback_used", "safe_mapping_used",
    "readiness_gap", "dify_runtime_attempted", "dify_runtime_called",
    "n8n_started", "n8n_stopped", "chatgpt_openai_api_secret_read",
    "notification_sent", "production_db_modified", "trading_executed",
    "no_secret_values", "secret_scan_summary", "runtime_handoff_outputs",
    "ai_dev_054_readiness", "ai_dev_054_executed"
]
PATTERNS = {
    "github_pat": re.compile(r"github_pat_[A-Za-z0-9_]+"),
    "ghp": re.compile(r"ghp_[A-Za-z0-9_]+"),
    "sk": re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    "bearer_value": re.compile(r"Bearer\\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
    "private_key": re.compile(r"BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    errors = []
    files = {str(DOC.relative_to(ROOT)): DOC.exists(), str(TPL.relative_to(ROOT)): TPL.exists()}
    for name, exists in files.items():
        if not exists:
            errors.append(f"missing {name}")
    data = {}
    if TPL.exists():
        try:
            data = json.loads(TPL.read_text())
        except Exception as exc:
            errors.append(f"json parse failed: {exc}")
    for key in REQ:
        if key not in data:
            errors.append(f"missing key {key}")
    if not (data.get("runtime_dry_run") is True or data.get("fallback_used") is True):
        errors.append("runtime_dry_run=true or fallback_used=true required")
    if data.get("dify_runtime_called") is True and data.get("safe_mapping_used") is not True:
        errors.append("dify_runtime_called requires safe_mapping_used")
    for key in ["chatgpt_openai_api_secret_read", "notification_sent", "production_db_modified", "trading_executed", "ai_dev_054_executed"]:
        if data.get(key) is not False:
            errors.append(f"{key} must be false")
    if data.get("no_secret_values") is not True:
        errors.append("no_secret_values must be true")
    scan = data.get("secret_scan_summary", {})
    if not isinstance(scan, dict) or scan.get("values_included") is not False:
        errors.append("secret_scan_summary without values required")
    if not data.get("runtime_handoff_outputs"):
        errors.append("runtime_handoff_outputs required")
    if not data.get("ai_dev_054_readiness"):
        errors.append("ai_dev_054_readiness required")
    text = "\n".join(path.read_text(errors="replace") for path in [DOC, TPL] if path.exists())
    hits = {name: len(pattern.findall(text)) for name, pattern in PATTERNS.items()}
    for name, count in hits.items():
        if count:
            errors.append(f"forbidden secret-like pattern {name} ({count})")
    result = {
        "ok": not errors,
        "passed": not errors,
        "file_checks": files,
        "task_id": data.get("task_id"),
        "runtime_state": {
            "fallback_used": data.get("fallback_used"),
            "safe_mapping_used": data.get("safe_mapping_used"),
            "dify_runtime_attempted": data.get("dify_runtime_attempted"),
            "dify_runtime_called": data.get("dify_runtime_called"),
            "n8n_started": data.get("n8n_started"),
            "n8n_stopped": data.get("n8n_stopped"),
            "ai_dev_054_executed": data.get("ai_dev_054_executed"),
        },
        "secret_scan_summary": scan,
        "secret_value_pattern_hits": hits,
        "errors": errors,
        "side_effects": {
            "files_modified": False,
            "n8n_started": False,
            "dify_called": False,
            "notification_sent": False,
            "runtime_queue_modified": False,
            "production_db_modified": False,
            "trading_execution_run": False,
        },
    }
    print(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0 if result["ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
