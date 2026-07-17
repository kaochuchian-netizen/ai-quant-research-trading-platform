#!/usr/bin/env python3
"""Refresh and report AI-DEV-182 public DOM evidence without publishing."""
import argparse, json
from production_multi_window_audit_v1 import OUT, run_audit

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--pretty", action="store_true"); a = p.parse_args()
    result = run_audit(); pages = json.loads((OUT / "public_page_findings.json").read_text())
    print(json.dumps({"ok": result["ok"], "pages": len(pages["pages"]), "screenshots": pages["screenshot_evidence"]["result"]}, indent=2 if a.pretty else None))
