#!/usr/bin/env python3
"""Prepare one selector-resolved Visual Evidence artifact for a future connector."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.visual_evidence_transport import prepare_chatgpt_transport


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--market", choices=("TW", "US"))
    parser.add_argument("--window")
    parser.add_argument("--revision", default="latest_valid")
    parser.add_argument("--artifact", required=True, choices=(
        "pdf", "png", "text", "html", "manifest", "canonical", "daily_bundle", "review_bundle",
    ))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = prepare_chatgpt_transport(
        effective_date=args.date, market=args.market, window=args.window,
        revision=args.revision, artifact=args.artifact,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result.get("status") == "READY_FOR_EXTERNAL_CONNECTOR" else 2


if __name__ == "__main__":
    raise SystemExit(main())
