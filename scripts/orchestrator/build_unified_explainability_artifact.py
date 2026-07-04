#!/usr/bin/env python3
"""Build deterministic Unified Explainability & Evidence Trace artifact."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.explainability.unified_trace_builder import build_unified_explainability_artifact

DEFAULT_CONTEXT = ROOT / "templates/prediction_context_artifact.example.json"


def load_payload(path: Path | None) -> dict:
    context_path = path or DEFAULT_CONTEXT
    return {"prediction_context_path": str(context_path.relative_to(ROOT)), "prediction_context": json.loads(context_path.read_text(encoding="utf-8"))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Optional unified explainability input JSON.")
    parser.add_argument("--context", type=Path, help="Optional prediction context artifact JSON.")
    parser.add_argument("--output", type=Path, help="Optional output path.")
    parser.add_argument("--write-input-template", type=Path, help="Optional path to write deterministic input template.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.input:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    else:
        payload = load_payload(args.context)
    if args.write_input_template:
        args.write_input_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_input_template.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    artifact = build_unified_explainability_artifact(payload["prediction_context"])
    text = json.dumps(artifact, indent=2 if args.pretty else None, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        if str(args.output).startswith("/var/www/stock-ai-dashboard"):
            raise SystemExit("refusing dashboard production path")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
