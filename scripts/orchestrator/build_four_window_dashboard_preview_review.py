#!/usr/bin/env python3
"""Build deterministic AI-DEV-143 four-window dashboard preview review artifact."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard_review.four_window_preview_review import build_input, build_review_artifact, write_json

DEFAULT_INPUT = ROOT / "templates/four_window_dashboard_preview_review_input.example.json"
DEFAULT_OUTPUT = ROOT / "templates/four_window_dashboard_preview_review_artifact.example.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-input-template", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8")) if args.input else build_input()
    artifact = build_review_artifact(payload, ROOT)
    write_json(args.output, artifact)
    if args.write_input_template:
        write_json(DEFAULT_INPUT, build_input())
    summary = {
        "ok": True,
        "task_id": artifact["task_id"],
        "schema_version": artifact["schema_version"],
        "window_review_count": len(artifact["windows_review"]),
        "readability_status": artifact["readability_review"]["status"],
        "mobile_readability_status": artifact["mobile_readability_review"]["status"],
        "production_publish_executed": artifact["production_integration_plan"]["production_publish_executed"],
        "output": str(args.output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
