#!/usr/bin/env python3
"""Validate the required structure of an AI-DEV Task Package V2."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from governance_common import TASK_SECTIONS, result_payload, validate_markdown_sections


def validate(path: Path) -> dict:
    errors = validate_markdown_sections(path, TASK_SECTIONS)
    return result_payload("validate_ai_dev_task_package_v2", errors, {
        "path": str(path), "required_sections": list(TASK_SECTIONS), "section_count": len(TASK_SECTIONS),
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate(Path(args.input))
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
