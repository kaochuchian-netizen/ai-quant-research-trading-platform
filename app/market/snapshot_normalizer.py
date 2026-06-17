from datetime import datetime


def normalize_snapshot(snapshot):
    return {
        "stock_id": snapshot.code,

        "open": snapshot.open,
        "high": snapshot.high,
        "low": snapshot.low,
        "close": snapshot.close,

        "volume": snapshot.volume,
        "total_volume": snapshot.total_volume,

        "change_price": snapshot.change_price,
        "change_rate": snapshot.change_rate,

        "buy_price": snapshot.buy_price,
        "buy_volume": snapshot.buy_volume,
        "sell_price": snapshot.sell_price,
        "sell_volume": snapshot.sell_volume,

        "snapshot_time": snapshot.ts.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(snapshot.ts, datetime)
        else str(snapshot.ts),
    }


def normalize_snapshots(snapshots):
    return [normalize_snapshot(snapshot) for snapshot in snapshots]
