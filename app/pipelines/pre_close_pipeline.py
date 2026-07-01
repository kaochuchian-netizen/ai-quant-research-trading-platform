from app.pipelines.stock_analysis_report_pipeline import run_stock_analysis_report_pipeline


def run_pre_close_pipeline(dry_run=False):
    return run_stock_analysis_report_pipeline(
        "pre_close",
        dry_run=dry_run,
        update_historical=False,
        write_results=True,
        send_full_line_report=False,
        run_backtest_update_after=False,
    )
