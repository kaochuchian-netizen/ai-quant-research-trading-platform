#!/usr/bin/env python3
"""Build deterministic Prediction Context artifact from offline sample input."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.prediction_context.builder import build_prediction_context_artifact
from app.prediction_context.sample_data import offline_sample_input


def load_payload(path: Path | None) -> dict:
    if path is None:
        return offline_sample_input()
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Optional Prediction Context input JSON.")
    parser.add_argument("--output", type=Path, help="Optional output path for artifact JSON.")
    parser.add_argument("--write-input-template", type=Path, help="Optional path to write offline input template.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.write_input_template:
        args.write_input_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_input_template.write_text(json.dumps(offline_sample_input(), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    artifact = build_prediction_context_artifact(load_payload(args.input))
    text = json.dumps(artifact, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    if args.output:
        if str(args.output).startswith("/var/www/stock-ai-dashboard"):
            raise SystemExit("refusing dashboard production path")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
