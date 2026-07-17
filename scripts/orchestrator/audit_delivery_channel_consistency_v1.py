#!/usr/bin/env python3
"""Refresh and report the AI-DEV-182 delivery/channel evidence."""
import argparse, json
from pathlib import Path
from production_multi_window_audit_v1 import OUT, run_audit

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--pretty", action="store_true"); a = p.parse_args()
    result = run_audit(); evidence = json.loads((OUT / "batch_delivery_evidence.json").read_text())
    print(json.dumps({"ok": result["ok"], "windows": len(evidence), "artifact": str((OUT / "channel_consistency.json").relative_to(Path.cwd()))}, indent=2 if a.pretty else None))
