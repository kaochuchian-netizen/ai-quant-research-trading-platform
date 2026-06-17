import pandas as pd


def minute_to_daily(df):

    df = df.copy()

    df["date"] = df["ts"].dt.date

    daily = (
        df.groupby("date")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )

    return daily
