#!/usr/bin/env python3
"""Safely capture one admitted Dashboard route into the Visual Evidence Archive."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.dashboard_url_registry import get_window_archive_path
from app.dashboard.visual_evidence_archive import DEFAULT_VISUAL_ROOT, capture_snapshot_visual_evidence
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", required=True, choices=sorted(MARKET_WINDOWS))
    parser.add_argument("--window", required=True)
    parser.add_argument("--snapshot-archive-root", type=Path, default=ROOT / "artifacts/archive/window_snapshots")
    parser.add_argument("--dashboard-root", type=Path, default=Path("/var/www/stock-ai-dashboard"))
    parser.add_argument("--visual-root", type=Path, default=DEFAULT_VISUAL_ROOT)
    parser.add_argument("--capture-origin", choices=("scheduled", "manual_rerun"), default="scheduled")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.window not in MARKET_WINDOWS[args.market]:
        parser.error(f"unsupported window for {args.market}: {args.window}")
    selected = resolve_snapshots(args.snapshot_archive_root, args.market, args.window).latest
    route = args.dashboard_root / get_window_archive_path(args.market, args.window).lstrip("/")
    if args.dry_run:
        result = {
            "status": "DRY_RUN",
            "capture_attempted": False,
            "eligible_snapshot_found": selected is not None,
            "dashboard_path": str(route),
            "visual_root": str(args.visual_root),
            "notification_attempted": False,
            "production_pipeline_executed": False,
            "trading": False,
        }
    elif not selected:
        result = {"status": "SKIPPED_INELIGIBLE", "reason_code": "BATCH_NOT_ADMITTED"}
    else:
        result = capture_snapshot_visual_evidence(
            selected,
            route,
            output_root=args.visual_root,
            capture_origin=args.capture_origin,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result.get("status") in {"SUCCESS", "DRY_RUN", "SKIPPED_INELIGIBLE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
