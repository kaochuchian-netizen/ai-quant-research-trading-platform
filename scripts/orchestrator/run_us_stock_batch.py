#!/usr/bin/env python3
"""Dry-run US stock batch orchestrator contract."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.us_stock.batch import build_us_stock_batch_artifact, us_stock_batch_input_example

WINDOWS = ["us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", required=True, choices=WINDOWS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.dry_run:
        result = {
            "ok": False,
            "status": "rejected",
            "reason": "us_stock_batch_v1_requires_dry_run_until_pm_runtime_activation",
            "scheduler_runtime_activation": False,
            "line_sent": False,
            "email_sent": False,
            "trading_or_order_executed": False,
        }
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
        sys.stdout.write("\n")
        return 2
    artifact = build_us_stock_batch_artifact(us_stock_batch_input_example(), window=args.window)
    text = json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2 if args.pretty else None) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
