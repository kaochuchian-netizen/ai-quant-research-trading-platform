#!/usr/bin/env python3
"""Build deterministic TWSE/yfinance report integration artifact."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from app.reports.twse_yfinance_report_builder import build_artifact, offline_sample_input

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write-input-template", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.write_input_template:
        args.write_input_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_input_template.write_text(json.dumps(offline_sample_input(), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    payload = json.loads(args.input.read_text(encoding="utf-8")) if args.input else offline_sample_input()
    artifact = build_artifact(payload)
    text = json.dumps(artifact, indent=2 if args.pretty else None, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
