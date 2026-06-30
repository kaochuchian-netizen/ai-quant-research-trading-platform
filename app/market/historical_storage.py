import os

import pandas as pd


DEFAULT_HISTORICAL_FOLDER = "data/historical"


def historical_csv_path(stock_id, folder=DEFAULT_HISTORICAL_FOLDER):
    return os.path.join(folder, f"{str(stock_id).zfill(4)}_daily.csv")


def inspect_historical_csv(stock_id, folder=DEFAULT_HISTORICAL_FOLDER):
    file_path = historical_csv_path(stock_id, folder=folder)
    result = {
        "stock_id": str(stock_id).zfill(4),
        "csv_path": file_path,
        "exists": os.path.exists(file_path),
        "row_count": 0,
        "latest_date": None,
        "usable": False,
        "warning": None,
    }
    if not result["exists"]:
        result["warning"] = "historical_csv_missing"
        return result

    try:
        df = pd.read_csv(file_path, usecols=["date"])
    except Exception as exc:
        result["warning"] = f"historical_csv_unreadable:{exc.__class__.__name__}"
        return result

    result["row_count"] = int(len(df))
    if not df.empty and "date" in df.columns:
        dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        if not dates.empty:
            result["latest_date"] = dates.max().date().isoformat()
    result["usable"] = result["row_count"] > 0 and result["latest_date"] is not None
    if not result["usable"]:
        result["warning"] = "historical_csv_empty_or_missing_dates"
    return result


def save_historical_to_csv(df, stock_id, folder=DEFAULT_HISTORICAL_FOLDER):
    os.makedirs(folder, exist_ok=True)

    file_path = historical_csv_path(stock_id, folder=folder)

    df.to_csv(file_path, index=False, encoding="utf-8-sig")

    return file_path
