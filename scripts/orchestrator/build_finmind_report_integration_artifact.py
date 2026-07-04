#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.finmind_report.artifact_builder import build_finmind_report_integration_artifact
from app.finmind_report.sample_data import offline_sample_input

def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic FinMind report integration artifact")
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else offline_sample_input()
    artifact = build_finmind_report_integration_artifact(payload)
    text = json.dumps(artifact, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        out = Path(args.output)
        if str(out).startswith("/var/www/stock-ai-dashboard"):
            raise SystemExit("refusing dashboard production path")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
