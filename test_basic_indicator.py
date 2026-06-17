from indicators.basic_indicator import calculate_basic_indicators

snapshot = {
    "stock_id": "2330",
    "open": 2340.0,
    "high": 2375.0,
    "low": 2330.0,
    "close": 2355.0,
    "volume": 86,
    "total_volume": 86055,
    "change_price": 60.0,
    "change_rate": 2.61,
    "buy_price": 2350.0,
    "sell_price": 2355.0,
}

result = calculate_basic_indicators(snapshot)

print("===== Basic Indicators =====")
print(result)
