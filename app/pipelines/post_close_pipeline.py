from app.pipelines.context import create_pipeline_context


def build_post_close_context_summary(context, dry_run=False):
    return {
        "pipeline_type": context["pipeline_type"],
        "pipeline_run_id": context["pipeline_run_id"],
        "run_date": context["run_date"],
        "run_time": context["run_time"],
        "dry_run": dry_run,
    }


def print_post_close_context_summary(summary):
    print("pipeline_type:", summary["pipeline_type"])
    print("pipeline_run_id:", summary["pipeline_run_id"])
    print("run_date:", summary["run_date"])
    print("run_time:", summary["run_time"])
    print("dry_run:", summary["dry_run"])


def run_post_close_pipeline(dry_run=False):
    context = create_pipeline_context("post_close")
    summary = build_post_close_context_summary(context, dry_run=dry_run)
    print_post_close_context_summary(summary)

    return summary
