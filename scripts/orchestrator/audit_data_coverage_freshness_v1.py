#!/usr/bin/env python3
"""Refresh and report AI-DEV-182 data coverage/freshness evidence."""
import argparse, json
from production_multi_window_audit_v1 import OUT, run_audit

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--pretty", action="store_true"); a = p.parse_args()
    result = run_audit(); coverage = json.loads((OUT / "data_coverage_matrix.json").read_text())
    print(json.dumps({"ok": result["ok"], "coverage_rows": len(coverage), "artifact": "artifacts/audit/ai_dev_182/data_freshness_matrix.json"}, indent=2 if a.pretty else None))
