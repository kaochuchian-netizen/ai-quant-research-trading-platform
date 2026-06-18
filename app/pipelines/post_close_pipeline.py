from app.pipelines.context import create_pipeline_context


def run_post_close_pipeline(dry_run=False):
    context = create_pipeline_context("post_close")
    print(f"pipeline_type: {context['pipeline_type']}")
    print(f"pipeline_run_id: {context['pipeline_run_id']}")
    print(f"run_date: {context['run_date']}")
    print(f"run_time: {context['run_time']}")
    print(f"dry_run: {dry_run}")
