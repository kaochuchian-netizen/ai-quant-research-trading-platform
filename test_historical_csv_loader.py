from app.market.historical_csv_loader import load_historical_csv


df = load_historical_csv("2330")

print("===== Local Historical CSV =====")
print(df.head())
print(df.tail())
print(df.columns)
