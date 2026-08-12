#!/usr/bin/env python3
"""Build a deterministic self-contained daily Visual Evidence review bundle."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.visual_evidence_archive import DEFAULT_VISUAL_ROOT, build_daily_review_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--visual-root", type=Path, default=DEFAULT_VISUAL_ROOT)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        date.fromisoformat(args.date)
    except ValueError:
        parser.error("--date must use YYYY-MM-DD")
    result = build_daily_review_bundle(args.visual_root, args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
