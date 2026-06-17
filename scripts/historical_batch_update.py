import sys
import os

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.append(BASE_DIR)


from datetime import datetime

from app.loaders.google_sheet_loader import load_stock_ids
from app.market.shioaji_client import get_api
from app.market.historical_price_loader import get_historical_prices
from app.market.historical_normalizer import minute_to_daily
from app.market.historical_storage import save_historical_to_csv


START_DATE = "2026-01-01"


def update_one_stock(api, stock_id):
    today = datetime.today().strftime("%Y-%m-%d")

    print(f"開始更新歷史資料：{stock_id}")

    df = get_historical_prices(
        api,
        stock_id,
        START_DATE,
        today
    )

    daily_df = minute_to_daily(df)

    file_path = save_historical_to_csv(
        daily_df,
        stock_id
    )

    print(f"完成更新：{stock_id} -> {file_path}")

    return file_path


def main():
    api = get_api()

    stock_ids = load_stock_ids()
    success = 0
    failed = 0

    print("===== Historical Batch Update Start =====")

    for stock_id in stock_ids:
        try:
            update_one_stock(api, str(stock_id))
            success += 1
        except Exception as e:
            failed += 1
            print(f"更新失敗：{stock_id}")
            print(e)

    print("===== Historical Batch Update Finished =====")
    print(f"Total: {len(stock_ids)}")
    print(f"Success: {success}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
