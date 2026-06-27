#!/usr/bin/env python3
"""Validate the Dify/n8n daily report draft dry-run integration package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DOC_PATH = Path("docs/dify_n8n_daily_report_draft_dry_run_integration.md")
ROADMAP_PATH = Path("docs/daily_report_forecast_roadmap.md")
DRY_RUN_OUTPUT_PATH = Path("templates/daily_report_forecast_dry_run_output.example.json")
DIFY_INPUT_PATH = Path("templates/dify_daily_report_draft_input.example.json")
DIFY_OUTPUT_PATH = Path("templates/dify_daily_report_draft_output.example.json")
N8N_WORKFLOW_PATH = Path("templates/n8n_daily_report_draft_dry_run_workflow.sanitized.example.json")
CHATGPT_PACKAGE_PATH = Path("templates/chatgpt_daily_report_review_package.example.json")

JSON_FILES = [
    DRY_RUN_OUTPUT_PATH,
    DIFY_INPUT_PATH,
    DIFY_OUTPUT_PATH,
    N8N_WORKFLOW_PATH,
    CHATGPT_PACKAGE_PATH,
]

REQUIRED_DRY_RUN_KEYS = [
    "schema_version",
    "report_date",
    "market",
    "report_window",
    "generated_at",
    "dry_run",
    "stock_universe",
    "forecast_horizons",
    "per_stock_forecasts",
    "confidence",
    "interval_bounds",
    "evidence_sources",
    "risk_flags",
    "output_channels",
    "review_required",
    "no_trading_instruction",
    "no_order_execution",
    "research_only",
]

REQUIRED_HORIZONS = [
    "same_day_high_low",
    "next_day_high_low",
    "one_month_trend",
    "three_month_trend",
]

SAFETY_FLAGS = [
    "dry_run",
    "research_only",
    "no_trading_instruction",
    "no_order_execution",
    "review_required",
]

DOC_REQUIRED_PHRASES = [
    "does not start n8n",
    "call Dify runtime",
    "AI-DEV-047",
    "LINE reminder text as short reminder only",
    "no trading",
    "no order",
    "No production database",
    "No LINE",
]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

FORBIDDEN_WORKFLOW_TERMS = [
    "send_line_report",
    "LINE push API send call",
    "smtp",
    "send email",
    "sqlite write",
    "cron",
    "activate workflow",
]

FORBIDDEN_ORDER_PATTERNS = [
    re.compile(r"\b(buy|sell|short|long)\s+(now|today|at market|at open|at close)\b", re.IGNORECASE),
    re.compile(r"\b(place|submit|route|execute)\s+(an?\s+)?order\b", re.IGNORECASE),
]

ALLOWED_SECRET_PLACEHOLDERS = [
    "DIFY_API_KEY_STORED_IN_N8N_ONLY_DO_NOT_COMMIT_REAL_SECRET",
    "DIFY_WORKFLOW_API_CREDENTIAL_PLACEHOLDER",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(read_text(path)), None
    except Exception as exc:
        return None, str(exc)


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(iter_strings(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(iter_strings(item))
        return result
    return []


def scrub_allowed_placeholders(text: str) -> str:
    scrubbed = text
    for placeholder in ALLOWED_SECRET_PLACEHOLDERS:
        scrubbed = scrubbed.replace(placeholder, "")
    return scrubbed


def has_secret_pattern(text: str) -> bool:
    scrubbed = scrub_allowed_placeholders(text)
    return any(pattern.search(scrubbed) for pattern in SECRET_PATTERNS)


def validate_required_flags(payload: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    for flag in SAFETY_FLAGS:
        if payload.get(flag) is not True:
            errors.append(f"{prefix}.{flag} must be true")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Dify/n8n daily report draft dry-run package.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    required_files = [DOC_PATH, ROADMAP_PATH, *JSON_FILES]
    file_checks = {str(path): (repo_root / path).is_file() for path in required_files}
    for rel_path, exists in file_checks.items():
        if not exists:
            errors.append(f"required file missing: {rel_path}")

    loaded: dict[str, Any] = {}
    for path in JSON_FILES:
        if not file_checks.get(str(path)):
            continue
        data, error = load_json(repo_root / path)
        if error:
            errors.append(f"JSON parse failed for {path}: {error}")
        else:
            loaded[str(path)] = data
            if has_secret_pattern(json.dumps(data, ensure_ascii=False, sort_keys=True)):
                errors.append(f"secret-like pattern found in {path}")

    dry_payload = loaded.get(str(DRY_RUN_OUTPUT_PATH))
    dify_input = loaded.get(str(DIFY_INPUT_PATH))
    dify_output = loaded.get(str(DIFY_OUTPUT_PATH))
    workflow = loaded.get(str(N8N_WORKFLOW_PATH))
    review_package = loaded.get(str(CHATGPT_PACKAGE_PATH))

    if isinstance(dry_payload, dict):
        missing = [key for key in REQUIRED_DRY_RUN_KEYS if key not in dry_payload]
        errors.extend(f"AI-DEV-045 dry-run output missing key: {key}" for key in missing)
    else:
        errors.append("AI-DEV-045 dry-run output root must be object")

    if isinstance(dify_input, dict):
        input_required = dify_input.get("required_input_keys")
        if not isinstance(input_required, list):
            errors.append("dify input required_input_keys must be a list")
            input_required = []
        for key in REQUIRED_DRY_RUN_KEYS:
            if key not in input_required:
                errors.append(f"dify input contract does not align to dry-run key: {key}")
        for horizon in REQUIRED_HORIZONS:
            if horizon not in dify_input.get("forecast_horizons", []):
                errors.append(f"dify input missing horizon: {horizon}")
        errors.extend(validate_required_flags(dify_input, "dify_input"))
    else:
        errors.append("dify input root must be object")

    if isinstance(dify_output, dict):
        for key in [
            "report_summary",
            "per_stock_summary",
            "forecast_explanation",
            "risk_summary",
            "evidence_summary",
            "confidence_disclaimer",
            "dashboard_detail_text",
            "email_detail_text",
            "line_reminder_text",
            "safety_flags",
        ]:
            if key not in dify_output:
                errors.append(f"dify output missing key: {key}")
        safety_flags = dify_output.get("safety_flags")
        if not isinstance(safety_flags, dict):
            errors.append("dify output safety_flags must be object")
        else:
            errors.extend(validate_required_flags(safety_flags, "dify_output.safety_flags"))
            if safety_flags.get("line_reminder_only") is not True:
                errors.append("dify output safety_flags.line_reminder_only must be true")
        line_text = dify_output.get("line_reminder_text")
        if not isinstance(line_text, str) or len(line_text) > 140:
            errors.append("line_reminder_text must be a short summary under 140 characters")
        if isinstance(line_text, str) and any(marker in line_text.lower() for marker in ["full report", "complete report"]):
            errors.append("line_reminder_text must not claim to carry the full report")
    else:
        errors.append("dify output root must be object")

    if isinstance(workflow, dict):
        if workflow.get("active") is not False:
            errors.append("n8n workflow template must be inactive")
        meta = workflow.get("meta")
        if not isinstance(meta, dict):
            errors.append("n8n workflow meta must be object")
            meta = {}
        for key in ["dry_run", "workflow_not_active", "workflow_not_published", "no_notification_nodes", "no_production_write_nodes", "no_real_credentials"]:
            if meta.get(key) is not True:
                errors.append(f"n8n workflow meta.{key} must be true")
        workflow_text = json.dumps(workflow, ensure_ascii=False, sort_keys=True).lower()
        for term in FORBIDDEN_WORKFLOW_TERMS:
            if term in workflow_text:
                errors.append(f"forbidden workflow term found: {term}")
        if "manualtrigger" not in workflow_text.lower():
            errors.append("n8n workflow must include a manual trigger concept")
        if "httpRequest" not in json.dumps(workflow, ensure_ascii=False):
            errors.append("n8n workflow must include a Dify HTTP placeholder node")
    else:
        errors.append("n8n workflow root must be object")

    if isinstance(review_package, dict):
        for key in ["input_contract_summary", "dify_draft_summary", "safety_checklist", "validation_checklist", "open_questions", "next_step_recommendation"]:
            if key not in review_package:
                errors.append(f"ChatGPT review package missing key: {key}")
        checklist = review_package.get("safety_checklist")
        if isinstance(checklist, dict):
            errors.extend(validate_required_flags(checklist, "chatgpt_review.safety_checklist"))
    else:
        errors.append("ChatGPT review package root must be object")

    doc_summary = {"required_phrases_present": False}
    if file_checks.get(str(DOC_PATH)):
        doc_text = read_text(repo_root / DOC_PATH)
        missing_phrases = [phrase for phrase in DOC_REQUIRED_PHRASES if phrase not in doc_text]
        errors.extend(f"doc missing required phrase: {phrase}" for phrase in missing_phrases)
        if has_secret_pattern(doc_text):
            errors.append("secret-like pattern found in integration doc")
        doc_summary = {"required_phrases_present": not missing_phrases}

    combined_text = "\n".join(
        read_text(repo_root / path) for path in required_files if (repo_root / path).is_file()
    )
    if has_secret_pattern(combined_text):
        errors.append("secret-like pattern found across AI-DEV-046 package")
    for pattern in FORBIDDEN_ORDER_PATTERNS:
        if pattern.search(combined_text):
            errors.append(f"possible trading or order instruction found: {pattern.pattern}")

    report = {
        "ok": not errors,
        "file_checks": file_checks,
        "dify_input_contract": {
            "aligned_to_ai_dev_045_keys": not any("dify input contract does not align" in error for error in errors),
            "required_horizons": REQUIRED_HORIZONS,
        },
        "dify_output_contract": {
            "dashboard_email_line_split_present": isinstance(dify_output, dict) and all(
                key in dify_output for key in ["dashboard_detail_text", "email_detail_text", "line_reminder_text"]
            ),
            "line_reminder_short": isinstance(dify_output, dict) and isinstance(dify_output.get("line_reminder_text"), str) and len(dify_output["line_reminder_text"]) <= 140,
        },
        "n8n_workflow_template": {
            "sanitized_example": isinstance(workflow, dict) and workflow.get("meta", {}).get("no_real_credentials") is True,
            "manual_trigger_only_entry": isinstance(workflow, dict) and workflow.get("active") is False,
            "notification_nodes_absent": isinstance(workflow, dict) and workflow.get("meta", {}).get("no_notification_nodes") is True,
        },
        "docs": doc_summary,
        "warnings": warnings,
        "errors": errors,
        "side_effects": {
            "n8n_started": False,
            "dify_runtime_called": False,
            "api_key_used": False,
            "notification_sent": False,
            "production_db_modified": False,
            "runtime_queue_modified": False,
            "production_pipeline_changed": False,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
