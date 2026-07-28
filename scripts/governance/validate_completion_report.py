#!/usr/bin/env python3
"""Validate an AI-DEV Completion Report V2 and its honest final status."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from governance_common import COMPLETION_SECTIONS, FINAL_STATUSES, result_payload, validate_markdown_sections


def validate(path: Path) -> dict:
    errors = validate_markdown_sections(path, COMPLETION_SECTIONS)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    final_block = re.search(r"^##\s+Final Status\s*$\n(.*?)(?=^##\s+|\Z)", text, re.MULTILINE | re.DOTALL)
    status = next((value for value in FINAL_STATUSES if final_block and value in final_block.group(1)), None)
    if status is None:
        errors.append("final_status_missing_or_invalid")
    if status == "CLOSED" and re.search(r"natural verification.*(?:pending|待)", text, re.IGNORECASE):
        errors.append("closed_with_pending_natural_verification")
    return result_payload("validate_completion_report", errors, {
        "path": str(path), "final_status": status, "required_sections": list(COMPLETION_SECTIONS),
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
