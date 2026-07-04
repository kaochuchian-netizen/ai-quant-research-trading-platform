#!/usr/bin/env python3
"""Validate AI-DEV-134 TWSE/yfinance report integration foundation."""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from app.reports.twse_yfinance_report_schema import REPORT_SECTION_IDS, SCHEMA_VERSION

REQUIRED_FILES = [
    "app/reports/twse_yfinance_report_schema.py",
    "app/reports/twse_yfinance_report_builder.py",
    "scripts/orchestrator/build_twse_yfinance_report_integration_artifact.py",
    "scripts/orchestrator/validate_twse_yfinance_report_integration_v1.py",
    "templates/twse_yfinance_report_integration_input.example.json",
    "templates/twse_yfinance_report_integration_artifact.example.json",
    "docs/ai_dev_134_twse_yfinance_formal_report_integration_foundation_v1.md",
]
SECRET_PATTERNS = [re.compile(p, re.I) for p in [r"ghp_[A-Za-z0-9]+", r"github_pat_[A-Za-z0-9_]+", r"sk-[A-Za-z0-9]+", r"BEGIN (RSA|OPENSSH) PRIVATE KEY", r"api[_-]?key\s*[:=]", r"access[_-]?token\s*[:=]", r"password\s*[:=]"]]

def read_json(rel: str) -> dict:
    return json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))

def validate() -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    for rel in REQUIRED_FILES:
        if not (REPO_ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}
    for rel in REQUIRED_FILES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        hits = [p.pattern for p in SECRET_PATTERNS if p.search(text)]
        if hits:
            errors.append(f"secret-like pattern in {rel}: {hits}")
    input_payload = read_json("templates/twse_yfinance_report_integration_input.example.json")
    artifact = read_json("templates/twse_yfinance_report_integration_artifact.example.json")
    if input_payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("input schema_version mismatch")
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("artifact schema_version mismatch")
    if artifact.get("input_summary", {}).get("external_api_called") is not False:
        errors.append("artifact must prove no external API call")
    sections = artifact.get("report_sections", [])
    section_ids = {section.get("section_id") for section in sections}
    missing_sections = sorted(set(REPORT_SECTION_IDS) - section_ids)
    if missing_sections:
        errors.append(f"missing report sections: {missing_sections}")
    policies = {policy.get("source_id"): policy for policy in artifact.get("source_policies", [])}
    for source_id in ["twse_openapi", "yfinance_yahoo"]:
        if source_id not in policies:
            errors.append(f"missing source policy: {source_id}")
    yf = policies.get("yfinance_yahoo", {})
    if yf.get("official_source_replacement_allowed") is not False:
        errors.append("yfinance official_source_replacement_allowed must be false")
    if yf.get("direct_rating_action_confidence_impact") is not False:
        errors.append("yfinance direct_rating_action_confidence_impact must be false")
    if "external" not in yf.get("source_role", "") or "proxy" not in yf.get("source_role", ""):
        errors.append("yfinance source role must be external reference/proxy")
    twse = policies.get("twse_openapi", {})
    if "official" not in twse.get("source_role", ""):
        errors.append("TWSE must be official market/chip source")
    for section in sections:
        if section.get("direct_rating_action_confidence_impact") is not False:
            errors.append(f"section direct impact must be false: {section.get('section_id')}")
    freshness = artifact.get("freshness_policy", {})
    if "twse_openapi" not in freshness or "yfinance_yahoo" not in freshness:
        errors.append("freshness_policy must cover both sources")
    if not artifact.get("explainability_notes"):
        errors.append("explainability notes required")
    safety = artifact.get("safety_summary", {})
    for key in ["read_only", "offline_sample_only"]:
        if safety.get(key) is not True:
            errors.append(f"safety flag must be true: {key}")
    for key in ["external_api_called", "secrets_read", "production_db_write", "scheduler_modified", "line_email_sent", "dashboard_published", "broker_or_order_execution", "production_rating_action_confidence_weight_mutation"]:
        if safety.get(key) is not False:
            errors.append(f"safety flag must be false: {key}")
    doc = (REPO_ROOT / "docs/ai_dev_134_twse_yfinance_formal_report_integration_foundation_v1.md").read_text(encoding="utf-8")
    for phrase in ["TWSE is the official market/chip source", "yfinance is an external reference/proxy", "must not directly change rating/action/confidence", "No external API calls", "No secrets", "daily report", "prediction context"]:
        if phrase not in doc:
            errors.append(f"doc missing required phrase: {phrase}")
    proc = subprocess.run([str(REPO_ROOT / "venv/bin/python"), "scripts/orchestrator/build_twse_yfinance_report_integration_artifact.py", "--pretty"], cwd=REPO_ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        errors.append(f"builder failed: {proc.stderr}")
    else:
        json.loads(proc.stdout)
    return {"ok": not errors, "task_id": "AI-DEV-134", "errors": errors, "warnings": warnings, "summary": {"section_count": len(sections), "source_policy_count": len(policies), "twse_role": twse.get("source_role"), "yfinance_role": yf.get("source_role"), "direct_rating_action_confidence_impact": False, "secret_pattern_hits": 0 if not errors else "see_errors"}}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("ok") else 1
if __name__ == "__main__":
    raise SystemExit(main())
