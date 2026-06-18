from datetime import datetime

from app.database.sqlite_client import get_connection, init_database


def save_analysis_result(
    stock_id,
    stock_name,
    indicator_result,
    technical_score,
    news_score,
    adr_score,
    chip_score,
    total_score_result,
    report_text,
    signal_session=None,
    pipeline_type=None,
    pipeline_run_id=None,
    signal_time=None,
    is_backtest_eligible=None,
    schema_version=1,
):
    init_database()

    run_date = datetime.now().strftime("%Y-%m-%d")

    close_price = indicator_result.get("close")
    if close_price is None:
        close_price = indicator_result.get("latest_close")

    total_score = total_score_result.get("total_score")
    rating = total_score_result.get("rating")
    action = total_score_result.get("action")
    strategy = total_score_result.get("strategy", action)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO analysis_results (
            run_date,
            stock_id,
            stock_name,
            close_price,
            technical_score,
            news_score,
            adr_score,
            chip_score,
            total_score,
            rating,
            action,
            strategy,
            report_text,
            signal_session,
            pipeline_type,
            pipeline_run_id,
            signal_time,
            is_backtest_eligible,
            schema_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_date,
            stock_id,
            stock_name,
            close_price,
            technical_score,
            news_score,
            adr_score,
            chip_score,
            total_score,
            rating,
            action,
            strategy,
            report_text,
            signal_session,
            pipeline_type,
            pipeline_run_id,
            signal_time,
            is_backtest_eligible,
            schema_version,
        ),
    )

    conn.commit()
    conn.close()
