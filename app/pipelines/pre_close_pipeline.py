from app.pipelines.afternoon_report_pipeline import run_afternoon_report_pipeline


def run_pre_close_pipeline(dry_run=False):
    return run_afternoon_report_pipeline("pre_close", dry_run=dry_run)
