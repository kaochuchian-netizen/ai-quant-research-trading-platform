from app.pipelines.afternoon_report_pipeline import run_afternoon_report_pipeline


def run_intraday_pipeline(dry_run=False):
    return run_afternoon_report_pipeline("intraday", dry_run=dry_run)
