import os


def save_historical_to_csv(df, stock_id, folder="data/historical"):
    os.makedirs(folder, exist_ok=True)

    file_path = os.path.join(folder, f"{stock_id}_daily.csv")

    df.to_csv(file_path, index=False, encoding="utf-8-sig")

    return file_path
