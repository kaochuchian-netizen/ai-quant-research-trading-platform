def calculate_basic_indicators(snapshot):
    close = snapshot.get("close")
    open_price = snapshot.get("open")
    high = snapshot.get("high")
    low = snapshot.get("low")
    volume = snapshot.get("volume")
    total_volume = snapshot.get("total_volume")
    change_price = snapshot.get("change_price")
    change_rate = snapshot.get("change_rate")
    buy_price = snapshot.get("buy_price")
    sell_price = snapshot.get("sell_price")

    result = {
        "stock_id": snapshot.get("stock_id"),
        "price": {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "change_price": change_price,
            "change_rate": change_rate,
        },
        "volume": {
            "volume": volume,
            "total_volume": total_volume,
        },
        "spread": {
            "buy_price": buy_price,
            "sell_price": sell_price,
            "spread": None,
        },
        "position": {
            "range_position": None,
        },
        "signals": [],
    }

    if (
        buy_price is not None
        and sell_price is not None
        and buy_price > 0
        and sell_price > 0
    ):
        result["spread"]["spread"] = sell_price - buy_price

    if high is not None and low is not None and close is not None and high != low:
        result["position"]["range_position"] = round(
            (close - low) / (high - low), 4
        )

    if change_rate is not None:
        if change_rate > 2:
            result["signals"].append("strong_up")
        elif change_rate < -2:
            result["signals"].append("strong_down")
        else:
            result["signals"].append("neutral_change")

    return result
