from datetime import datetime, timedelta

import pandas as pd


MAX_KBARS_LOOKBACK_DAYS = 30


def bounded_kbars_date_window(start_date, end_date, max_days=MAX_KBARS_LOOKBACK_DAYS):
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    if start > end:
        raise ValueError("start_date must be earlier than or equal to end_date")

    min_start = end - timedelta(days=max_days - 1)
    bounded_start = max(start, min_start)
    return bounded_start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def get_historical_prices(api, stock_id, start_date, end_date):
    bounded_start_date, bounded_end_date = bounded_kbars_date_window(start_date, end_date)
    contract = api.Contracts.Stocks[str(stock_id)]

    kbars = api.kbars(
        contract,
        start=bounded_start_date,
        end=bounded_end_date,
    )

    df = pd.DataFrame({
        "ts": pd.to_datetime(kbars.ts),
        "open": kbars.Open,
        "high": kbars.High,
        "low": kbars.Low,
        "close": kbars.Close,
        "volume": kbars.Volume,
    })

    return df
