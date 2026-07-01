from app.pipelines.stock_analysis_report_pipeline import (
    LINE_BATCH_SIZE,
    run_stock_analysis_report_pipeline,
    send_reports_in_batches,
)


def run_pre_open_pipeline(dry_run=False, limit=None):
    return run_stock_analysis_report_pipeline(
        "pre_open",
        dry_run=dry_run,
        limit=limit,
        update_historical=True,
        write_results=True,
        send_full_line_report=True,
        run_backtest_update_after=True,
    )
