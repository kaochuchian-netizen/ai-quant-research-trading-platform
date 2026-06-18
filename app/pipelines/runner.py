from app.pipelines.intraday_pipeline import run_intraday_pipeline
from app.pipelines.post_close_pipeline import run_post_close_pipeline
from app.pipelines.pre_close_pipeline import run_pre_close_pipeline
from app.pipelines.pre_open_pipeline import run_pre_open_pipeline


SUPPORTED_PIPELINES = {
    "intraday": run_intraday_pipeline,
    "pre_close": run_pre_close_pipeline,
    "pre_open": run_pre_open_pipeline,
    "post_close": run_post_close_pipeline,
}


def run_pipeline(pipeline_type, dry_run=False):
    if pipeline_type == "pre_open" and not dry_run:
        raise ValueError("pre_open pipeline is only allowed with dry_run=True")

    try:
        pipeline = SUPPORTED_PIPELINES[pipeline_type]
    except KeyError as exc:
        supported = ", ".join(sorted(SUPPORTED_PIPELINES))
        raise ValueError(
            f"Unsupported pipeline_type: {pipeline_type}. Supported: {supported}"
        ) from exc

    return pipeline(dry_run=dry_run)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run a supported stock-ai pipeline.")
    parser.add_argument("pipeline_type", choices=sorted(SUPPORTED_PIPELINES))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run_pipeline(args.pipeline_type, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
