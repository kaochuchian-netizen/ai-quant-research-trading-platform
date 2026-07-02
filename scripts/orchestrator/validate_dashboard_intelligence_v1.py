#!/usr/bin/env python3
"""Validate Dashboard Intelligence V1 package."""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from app.dashboard.diagnostics_policy import contains_raw_traceback
from app.dashboard.intelligence_builder import build_artifact
from app.dashboard.intelligence_schema import REQUIRED_SECTION_IDS

REQUIRED_FILES = [
    "app/dashboard/intelligence_schema.py", "app/dashboard/intelligence_builder.py", "app/dashboard/section_builder.py", "app/dashboard/card_builder.py", "app/dashboard/diagnostics_policy.py", "app/dashboard/mobile_layout_policy.py", "app/dashboard/preview_renderer.py",
    "scripts/orchestrator/build_dashboard_intelligence_artifact.py", "scripts/orchestrator/render_dashboard_intelligence_preview.py", "scripts/orchestrator/validate_dashboard_intelligence_v1.py",
    "templates/dashboard_intelligence_input.example.json", "templates/dashboard_intelligence_artifact.example.json", "templates/dashboard_intelligence_preview.example.html", "docs/ai_dev_126_dashboard_intelligence_v1.md",
]
SECRET_PATTERNS = [re.compile(p, re.I) for p in [r"ghp_[A-Za-z0-9]+", r"github_pat_[A-Za-z0-9_]+", r"sk-[A-Za-z0-9]+", r"BEGIN (RSA|OPENSSH) PRIVATE KEY", r"api[_-]?key\s*[:=]", r"access[_-]?token\s*[:=]", r"password\s*[:=]"]]

def read_json(path: str) -> dict:
    return json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))

def validate() -> dict:
    errors, warnings = [], []
    for rel in REQUIRED_FILES:
        if not (REPO_ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}
    input_template = read_json("templates/dashboard_intelligence_input.example.json")
    artifact = read_json("templates/dashboard_intelligence_artifact.example.json")
    rebuilt = build_artifact(input_template)
    for rel in REQUIRED_FILES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        hits = [p.pattern for p in SECRET_PATTERNS if p.search(text)]
        if hits:
            errors.append(f"secret-like pattern in {rel}: {hits}")
    sections = artifact.get("sections", [])
    section_ids = {section.get("section_id") for section in sections}
    missing_sections = sorted(set(REQUIRED_SECTION_IDS) - section_ids)
    if missing_sections:
        errors.append(f"missing required sections: {missing_sections}")
    if not artifact.get("stock_cards"):
        errors.append("stock cards are required")
    today = next((section for section in sections if section.get("section_id") == "today_overview"), {})
    if contains_raw_traceback(str(today)):
        errors.append("raw traceback must be suppressed from Today Overview")
    diagnostics = artifact.get("diagnostics", {})
    if diagnostics.get("raw_traceback_suppressed") is not True:
        errors.append("diagnostics must record raw_traceback_suppressed=true")
    safety = artifact.get("safety_summary", {})
    for key, expected in {"advisory_only": True, "production_publish_allowed": False, "production_mutation_allowed": False, "trading_disabled": True, "no_line_email_delivery": True, "no_production_db_write": True, "no_confidence_mutation": True, "no_forecast_weight_change": True, "no_rating_action_mutation": True, "no_var_www_write": True}.items():
        if safety.get(key) is not expected:
            errors.append(f"safety flag mismatch: {key}")
    if artifact.get("production_publish_allowed") is not False or artifact.get("production_mutation_allowed") is not False or artifact.get("advisory_only") is not True:
        errors.append("artifact top-level safety flags invalid")
    source = artifact.get("source_coverage_summary", {})
    if "supporting" not in source.get("finmind_yfinance_policy_note", "").lower():
        errors.append("FinMind/yfinance must be supporting context, not primary authority")
    if not any("news-only" in reason for reason in source.get("confidence_cap_reasons", [])):
        errors.append("news-only evidence authority cap must be visible")
    recs = artifact.get("factor_recommendation_summary", {}).get("recommendations", [])
    if not recs or any(rec.get("production_mutation_allowed") is not False or rec.get("requires_human_review") is not True for rec in recs):
        errors.append("factor recommendations must remain advisory-only with human review")
    if not any(card.get("dashboard_priority") == "watch" for card in artifact.get("stock_cards", [])):
        errors.append("insufficient sample watch example is required")
    preview = (REPO_ROOT / "templates/dashboard_intelligence_preview.example.html").read_text(encoding="utf-8")
    for phrase in ["Today Overview", "Stock Intelligence Cards", "Advisory only", "Not production published"]:
        if phrase not in preview:
            errors.append(f"preview missing phrase: {phrase}")
    doc = (REPO_ROOT / "docs/ai_dev_126_dashboard_intelligence_v1.md").read_text(encoding="utf-8")
    for phrase in ["No production trading", "No simulation order", "No production dashboard publish", "No write to /var/www/stock-ai-dashboard", "No raw traceback in user-facing main dashboard sections", "AI-DEV-127"]:
        if phrase not in doc:
            errors.append(f"doc missing required phrase: {phrase}")
    proc = subprocess.run([str(REPO_ROOT / "venv/bin/python"), "scripts/orchestrator/build_dashboard_intelligence_artifact.py", "--pretty"], cwd=REPO_ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        errors.append(f"artifact builder failed: {proc.stderr}")
    else:
        json.loads(proc.stdout)
    proc = subprocess.run([str(REPO_ROOT / "venv/bin/python"), "scripts/orchestrator/render_dashboard_intelligence_preview.py", "--pretty"], cwd=REPO_ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        errors.append(f"preview renderer failed: {proc.stderr}")
    else:
        json.loads(proc.stdout)
    return {"ok": not errors, "task_id": "AI-DEV-126", "errors": errors, "warnings": warnings, "summary": {"section_count": len(sections), "stock_card_count": len(artifact.get("stock_cards", [])), "dashboard_status": artifact.get("dashboard_status"), "production_publish_allowed": artifact.get("production_publish_allowed"), "advisory_only": artifact.get("advisory_only"), "secret_pattern_hits": 0 if not errors else "see_errors"}}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("ok") else 1
if __name__ == "__main__":
    raise SystemExit(main())
