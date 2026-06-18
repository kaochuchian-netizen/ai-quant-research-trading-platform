from app.pipelines.context import create_pipeline_context


def run_pre_close_pipeline(dry_run=False):
    context = create_pipeline_context("pre_close")

    print("pipeline_type:", context["pipeline_type"])
    print("pipeline_run_id:", context["pipeline_run_id"])
    print("run_date:", context["run_date"])
    print("run_time:", context["run_time"])
    print("dry_run:", dry_run)
