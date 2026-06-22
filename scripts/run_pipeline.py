#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipelines.runner import SUPPORTED_PIPELINES, run_pipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Run a supported stock-ai pipeline.")
    parser.add_argument("pipeline_type", choices=sorted(SUPPORTED_PIPELINES))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--production-approved",
        action="store_true",
        help="Allow an explicitly reviewed production run for scheduled entrypoints.",
    )
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    return run_pipeline(
        args.pipeline_type,
        dry_run=args.dry_run,
        limit=args.limit,
        production_approved=args.production_approved,
    )


if __name__ == "__main__":
    main()
