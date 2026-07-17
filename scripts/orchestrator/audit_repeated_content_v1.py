#!/usr/bin/env python3
"""Refresh and report deterministic content-noise measurements."""
import argparse, json
from production_multi_window_audit_v1 import OUT, run_audit

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--pretty", action="store_true"); a = p.parse_args()
    result = run_audit(); rows = json.loads((OUT / "repeated_content.json").read_text())
    print(json.dumps({"ok": result["ok"], "windows": len(rows), "artifact": "artifacts/audit/ai_dev_182/repeated_content.json"}, indent=2 if a.pretty else None))
