import os
import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORICAL_DIR = os.path.join(BASE_DIR, "data", "historical")


def load_historical_csv(stock_id: str) -> pd.DataFrame:
    stock_id = str(stock_id).zfill(4) if str(stock_id).isdigit() and len(str(stock_id)) < 4 else str(stock_id)

    file_path = os.path.join(HISTORICAL_DIR, f"{stock_id}_daily.csv")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到歷史資料檔案：{file_path}")

    df = pd.read_csv(file_path)

    required_columns = ["date", "open", "high", "low", "close", "volume"]
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(f"{stock_id} CSV 缺少欄位：{missing}")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    return df
