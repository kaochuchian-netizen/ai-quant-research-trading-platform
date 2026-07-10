#!/usr/bin/env python3
"""Build Multi-Market Dashboard V2 static pages without publishing."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.dashboard.multi_market_dashboard import OUTPUT_DIR, build_pages

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=OUTPUT_DIR)
    parser.add_argument('--pretty', action='store_true')
    args = parser.parse_args()
    result = build_pages(args.output_dir)
    print(json.dumps({'ok': True, **result}, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
