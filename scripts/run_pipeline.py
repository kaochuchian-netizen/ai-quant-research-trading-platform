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
    return parser.parse_args()


def main():
    args = parse_args()
    return run_pipeline(args.pipeline_type, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
