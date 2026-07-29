#!/usr/bin/env python3
"""Inspect seven-window production completeness without mutating runtime."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime.window_batch_health import TAIPEI, inspect_repository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--now")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    now = datetime.fromisoformat(args.now).astimezone(TAIPEI) if args.now else None
    result = inspect_repository(Path(args.root), now)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
