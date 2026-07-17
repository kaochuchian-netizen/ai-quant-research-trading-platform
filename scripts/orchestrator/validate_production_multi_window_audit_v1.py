#!/usr/bin/env python3
"""Validate completeness and safety of the AI-DEV-182 audit outputs."""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "audit" / "ai_dev_182"
NAMES = {
    "executive_summary.json", "production_readiness_scorecard.json", "seven_window_matrix.json",
    "three_day_longitudinal_matrix.json", "channel_consistency.json", "batch_delivery_evidence.json",
    "tw_1305_root_cause.json", "data_coverage_matrix.json", "data_freshness_matrix.json", "source_audit.json",
    "decision_quality.json", "cross_window_continuity.json", "repeated_content.json", "public_page_findings.json",
    "email_findings.json", "line_findings.json", "issue_register.json", "improvement_roadmap.json",
    "production_audit_report.md",
}

def load(name): return json.loads((OUT / name).read_text())

def main():
    p = argparse.ArgumentParser(); p.add_argument("--pretty", action="store_true"); a = p.parse_args()
    errors = [f"missing {n}" for n in sorted(NAMES) if not (OUT / n).is_file()]
    if not errors:
        executive = load("executive_summary.json"); matrix = load("seven_window_matrix.json")
        longitudinal = load("three_day_longitudinal_matrix.json"); public = load("public_page_findings.json")
        issues = load("issue_register.json"); root = load("tw_1305_root_cause.json")
        if len(matrix) != 7: errors.append(f"seven_window_matrix has {len(matrix)} rows")
        if len(longitudinal) != 7: errors.append(f"longitudinal matrix has {len(longitudinal)} rows")
        if len(public.get("pages", [])) != 17: errors.append("public inventory must contain Landing, TW/US, and 14 archive routes")
        if root.get("root_cause_category") != "pipeline_failure": errors.append("TW 13:05 root cause is not classified")
        if not all(any(i.get("severity") == level for i in issues) for level in ("P0", "P1", "P2")): errors.append("P0/P1/P2 issue register incomplete")
        safety = executive.get("safety", {})
        if any(safety.values()): errors.append("one or more audit safety mutation flags are true")
        if executive.get("coverage", {}).get("archive_routes") != "14/14": errors.append("archive route coverage incomplete")
    result = {"ok": not errors, "errors": errors, "output_dir": str(OUT.relative_to(ROOT))}
    print(json.dumps(result, indent=2 if a.pretty else None, sort_keys=True))
    return 0 if not errors else 1

if __name__ == "__main__": sys.exit(main())
