from app.market.shioaji_client import get_api
from app.market.historical_price_loader import get_historical_prices
from app.market.historical_normalizer import minute_to_daily


api = get_api()

df = get_historical_prices(
    api,
    "2330",
    "2026-01-01",
    "2026-05-29"
)

daily_df = minute_to_daily(df)

print(daily_df.head())
print()
print(daily_df.tail())
print()
print(daily_df.shape)
