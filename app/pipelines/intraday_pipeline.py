from app.pipelines.context import create_pipeline_context


def run_intraday_pipeline(dry_run=False):
    context = create_pipeline_context("intraday")

    print("pipeline_type:", context["pipeline_type"])
    print("pipeline_run_id:", context["pipeline_run_id"])
    print("run_date:", context["run_date"])
    print("run_time:", context["run_time"])
    print("dry_run:", dry_run)
