from datetime import datetime, timedelta

from app.loaders.google_sheet_loader import load_stock_ids
from app.market.shioaji_client import get_api
from app.market.historical_price_loader import get_historical_prices
from app.market.historical_normalizer import minute_to_daily
from app.market.historical_storage import save_historical_to_csv


def main():
    api = get_api()
    stock_ids = load_stock_ids()

    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=180)).strftime("%Y-%m-%d")

    for stock_id in stock_ids:
        stock_id = str(stock_id).zfill(4)

        print(f"開始更新歷史資料：{stock_id}")

        minute_df = get_historical_prices(
            api=api,
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date,
        )

        daily_df = minute_to_daily(minute_df)
        csv_path = save_historical_to_csv(daily_df, stock_id)

        print(f"完成：{csv_path}")


if __name__ == "__main__":
    main()
