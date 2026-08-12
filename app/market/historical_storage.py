import os

import pandas as pd

from app.market.tw_history_admission import public_admission, validate_history_candidate


DEFAULT_HISTORICAL_FOLDER = "data/historical"


def historical_csv_path(stock_id, folder=DEFAULT_HISTORICAL_FOLDER):
    return os.path.join(folder, f"{str(stock_id).zfill(4)}_daily.csv")


def inspect_historical_csv(stock_id, folder=DEFAULT_HISTORICAL_FOLDER, *, target_date=None, minimum_bars=20):
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
        df = pd.read_csv(file_path)
    except Exception as exc:
        result["warning"] = f"historical_csv_unreadable:{exc.__class__.__name__}"
        return result

    target_date = target_date or pd.Timestamp.now().date()
    admission = validate_history_candidate(df, source="existing_historical_csv", target_date=target_date, minimum_bars=minimum_bars)
    result.update({
        "row_count": admission["row_count"], "latest_date": admission["latest_date"],
        "usable": admission["admission_success"], "admission": public_admission(admission),
    })
    if not result["usable"]:
        result["warning"] = (admission.get("reason_codes") or ["ADMISSION_REJECTED"])[0]
    return result


def save_historical_to_csv(df, stock_id, folder=DEFAULT_HISTORICAL_FOLDER):
    os.makedirs(folder, exist_ok=True)

    file_path = historical_csv_path(stock_id, folder=folder)

    df.to_csv(file_path, index=False, encoding="utf-8-sig")

    return file_path
