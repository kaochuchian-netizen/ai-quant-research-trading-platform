#!/usr/bin/env python3
"""Build deterministic US stock batch lifecycle artifact."""
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
    parser.add_argument("--window", choices=WINDOWS, default="us_pre_market_2000")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write-input-template", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Accepted for production validation; no side effects other than optional --output.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.write_input_template:
        args.write_input_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_input_template.write_text(json.dumps(us_stock_batch_input_example(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    payload = json.loads(args.input.read_text(encoding="utf-8")) if args.input else us_stock_batch_input_example()
    artifact = build_us_stock_batch_artifact(payload, window=args.window)
    artifact["build_mode"] = "dry_run" if args.dry_run else "deterministic_builder"
    artifact["line_sent"] = False
    artifact["email_sent"] = False
    artifact["scheduler_runtime_activation"] = False
    text = json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2 if args.pretty else None) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
