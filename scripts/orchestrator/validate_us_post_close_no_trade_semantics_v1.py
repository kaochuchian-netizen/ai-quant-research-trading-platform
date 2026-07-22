#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.orchestrator.seven_window_presentation_validation import validate_group

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    result = validate_group("us_no_trade")
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
