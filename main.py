import argparse

from app.pipelines.pre_open_pipeline import run_pre_open_pipeline


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline without sending LINE messages.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.dry_run:
        raise ValueError("main.py only allows --dry-run execution. Use scripts/run_pipeline.py for formal runs.")
    run_pre_open_pipeline(dry_run=args.dry_run)
