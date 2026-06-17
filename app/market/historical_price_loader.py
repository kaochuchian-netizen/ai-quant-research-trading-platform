import pandas as pd


def get_historical_prices(api, stock_id, start_date, end_date):
    contract = api.Contracts.Stocks[str(stock_id)]

    kbars = api.kbars(
        contract,
        start=start_date,
        end=end_date
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
