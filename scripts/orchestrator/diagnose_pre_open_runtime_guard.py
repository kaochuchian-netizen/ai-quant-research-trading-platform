#!/usr/bin/env python3
"""Read-only pre-open runtime guard diagnostics."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.runtime.runtime_diagnostics import build_runtime_diagnostics
from app.runtime.timeout_policy import timeout_policy_from_env

def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose pre_open runtime guard state without side effects.")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--window", default="pre_open_0700")
    args = parser.parse_args()
    payload = build_runtime_diagnostics(args.window, ROOT, timeout_policy_from_env())
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
