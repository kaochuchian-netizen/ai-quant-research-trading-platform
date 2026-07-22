from datetime import datetime


def normalize_snapshot(snapshot):
    raw_time = snapshot.ts
    if isinstance(raw_time, datetime):
        snapshot_time = raw_time.isoformat()
        time_kind = "exchange_local_datetime" if raw_time.tzinfo is None else "UTC_datetime"
    elif isinstance(raw_time, (int, float)) or str(raw_time).isdigit():
        snapshot_time = str(raw_time)
        length = len(str(abs(int(raw_time))))
        time_kind = {10: "epoch_seconds", 13: "epoch_milliseconds", 16: "epoch_microseconds", 19: "epoch_nanoseconds"}.get(length, "unknown_numeric")
    else:
        snapshot_time = str(raw_time or "")
        time_kind = "unknown"
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

        "snapshot_time": snapshot_time,
        "source_timezone": "Asia/Taipei",
        "source_record_time_kind": time_kind,
        "normalized_timezone": "Asia/Taipei",
    }


def normalize_snapshots(snapshots):
    return [normalize_snapshot(snapshot) for snapshot in snapshots]
