#!/usr/bin/env python3
"""Publish Multi-Market Dashboard V2 static pages to the approved public root."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.dashboard.multi_market_dashboard import OUTPUT_DIR, STATIC_ROOT, build_pages, publish_pages

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--apply', '--publish', dest='apply', action='store_true')
    parser.add_argument('--static-root', type=Path, default=STATIC_ROOT)
    parser.add_argument('--source-dir', type=Path, default=OUTPUT_DIR)
    parser.add_argument('--pretty', action='store_true')
    args = parser.parse_args()
    if args.apply and args.dry_run:
        raise SystemExit('--dry-run and --apply cannot both be set')
    if args.apply:
        result = publish_pages(args.static_root, args.source_dir)
    else:
        result = build_pages(args.source_dir)
        result.update({'published': False, 'dry_run': True, 'static_root': str(args.static_root), 'notification_sent': False, 'production_pipeline_executed': False})
    print(json.dumps({'ok': True, **result}, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
