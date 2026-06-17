from app.market.shioaji_client import get_api
from app.market.historical_price_loader import get_historical_prices
from app.market.historical_normalizer import minute_to_daily
from app.market.historical_storage import save_historical_to_csv


api = get_api()

df = get_historical_prices(
    api,
    "2330",
    "2026-01-01",
    "2026-05-29"
)

daily_df = minute_to_daily(df)

file_path = save_historical_to_csv(
    daily_df,
    "2330"
)

print("===== Saved Historical CSV =====")
print(file_path)
