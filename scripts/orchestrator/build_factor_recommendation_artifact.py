#!/usr/bin/env python3
"""Build the AI-DEV-125 factor recommendation dry-run artifact."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.recommendation.recommendation_builder import build_artifact, offline_sample_input


def _load_payload(path: Path | None) -> dict:
    if path is None:
        return offline_sample_input()
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Optional factor recommendation input JSON.")
    parser.add_argument("--output", type=Path, help="Optional path to write artifact JSON.")
    parser.add_argument("--write-input-template", type=Path, help="Optional path to write the offline input template.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    if args.write_input_template:
        args.write_input_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_input_template.write_text(json.dumps(offline_sample_input(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = build_artifact(_load_payload(args.input))
    text = json.dumps(artifact, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
