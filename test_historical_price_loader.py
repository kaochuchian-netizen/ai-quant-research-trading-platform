from app.market.shioaji_client import get_api
from app.market.historical_price_loader import get_historical_prices


api = get_api()

df = get_historical_prices(
    api=api,
    stock_id="2330",
    start_date="2026-01-01",
    end_date="2026-05-29"
)

print("===== Historical Prices =====")
print(df.head())
print()
print(df.tail())
print()
print(df.shape)
