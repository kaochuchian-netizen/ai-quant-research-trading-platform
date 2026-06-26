#!/usr/bin/env python3
"""Sanitize an n8n workflow JSON export without printing secret values."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REDACTION = "DO_NOT_COMMIT_REAL_SECRET"
SECRET_KEY_RE = re.compile(
    r"(authorization|api[_-]?key|token|secret|credential|password|bearer)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{16,}"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sanitize an n8n workflow export JSON file."
    )
    parser.add_argument("--input", required=True, help="Input n8n workflow JSON path.")
    parser.add_argument("--output", required=True, help="Output sanitized JSON path.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting the output path. Default refuses overwrite.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print summary JSON.")
    return parser.parse_args()


def should_redact_key(key: str) -> bool:
    return bool(SECRET_KEY_RE.search(key))


def should_redact_string(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS)


def sanitize(value: Any, path: str = "$") -> tuple[Any, list[str]]:
    redacted_paths: list[str] = []

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if should_redact_key(key):
                sanitized[key] = REDACTION
                redacted_paths.append(child_path)
                continue
            sanitized_child, child_redactions = sanitize(child, child_path)
            sanitized[key] = sanitized_child
            redacted_paths.extend(child_redactions)
        return sanitized, redacted_paths

    if isinstance(value, list):
        sanitized_list = []
        for index, child in enumerate(value):
            sanitized_child, child_redactions = sanitize(child, f"{path}[{index}]")
            sanitized_list.append(sanitized_child)
            redacted_paths.extend(child_redactions)
        return sanitized_list, redacted_paths

    if isinstance(value, str) and should_redact_string(value):
        return REDACTION, [path]

    return value, redacted_paths


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not input_path.is_file():
        errors.append("input file does not exist")
    if output_path.exists() and not args.force:
        errors.append("output file already exists; use --force to overwrite")
    if input_path == output_path:
        errors.append("input and output paths must differ")

    if errors:
        summary = {
            "ok": False,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "written": False,
            "redaction_count": 0,
            "redacted_paths": [],
            "warnings": warnings,
            "errors": errors,
        }
        print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
        return 2

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception:
        summary = {
            "ok": False,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "written": False,
            "redaction_count": 0,
            "redacted_paths": [],
            "warnings": warnings,
            "errors": ["input file is not valid JSON"],
        }
        print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
        return 2

    sanitized_data, redacted_paths = sanitize(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(sanitized_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if not redacted_paths:
        warnings.append("no secret-like fields were redacted")

    summary = {
        "ok": True,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "written": True,
        "redaction_count": len(redacted_paths),
        "redacted_paths": redacted_paths,
        "warnings": warnings,
        "errors": [],
    }
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
