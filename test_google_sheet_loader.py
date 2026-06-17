from app.loaders.google_sheet_loader import load_stock_ids


stock_ids = load_stock_ids()

print("===== 股票清單 =====")

for stock_id in stock_ids:
    print(stock_id)
