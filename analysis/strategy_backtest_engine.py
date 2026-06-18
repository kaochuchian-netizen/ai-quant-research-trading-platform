import csv
import os
import sqlite3
from datetime import datetime

DB_PATH = "data/stock_analysis.db"
HISTORICAL_DIR = "data/historical"
OUTPUT_DIR = "analysis/output"

HOLDING_DAYS_LIST = [1, 3, 5, 10, 20]

PRE_OPEN_START_HOUR = 5
PRE_OPEN_END_HOUR = 9

STRATEGIES = [
    {
        "name": "只買 A級",
        "filter": lambda r: r.get("rating") == "A級",
    },
    {
        "name": "只買 B級以上",
        "filter": lambda r: r.get("rating") in ["A級", "B級"],
    },
    {
        "name": "只買 偏多續抱",
        "filter": lambda r: r.get("action") == "偏多續抱",
    },
    {
        "name": "只買 總分 >= 70",
        "filter": lambda r: safe_float(r.get("total_score"), 0) >= 70,
    },
    {
        "name": "只買 ADR >= 60",
        "filter": lambda r: safe_float(r.get("adr_score"), 0) >= 60,
    },
]


def safe_float(value, default=None):
    try:
        if value is None or value == "":
            return default

        return float(value)

    except Exception:
        return default


def parse_datetime(value):
    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def is_pre_open_record(row):
    created_at = row.get("created_at")
    created_dt = parse_datetime(created_at)

    if created_dt is None:
        return False

    return PRE_OPEN_START_HOUR <= created_dt.hour < PRE_OPEN_END_HOUR


def is_backtest_eligible_record(row):
    signal_session = row.get("signal_session")
    is_eligible = row.get("is_backtest_eligible")

    if signal_session is not None or is_eligible is not None:
        return signal_session == "pre_open" and is_eligible == 1

    return is_pre_open_record(row)


def load_analysis_results():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            run_date,
            stock_id,
            stock_name,
            rating,
            action,
            total_score,
            adr_score,
            created_at,
            signal_session,
            pipeline_type,
            pipeline_run_id,
            signal_time,
            is_backtest_eligible,
            schema_version
        FROM analysis_results
        ORDER BY run_date ASC, stock_id ASC
        """
    )

    rows = [
        dict(row)
        for row in cursor.fetchall()
    ]

    conn.close()

    pre_open_rows = [
        row
        for row in rows
        if is_backtest_eligible_record(row)
    ]

    print(
        "策略回測資料篩選："
        f"全部 {len(rows)} 筆，"
        f"07:00 盤前區間 {len(pre_open_rows)} 筆"
    )

    return pre_open_rows


def load_historical_prices(stock_id):
    csv_path = os.path.join(
        HISTORICAL_DIR,
        f"{stock_id}_daily.csv"
    )

    if not os.path.exists(csv_path):
        return []

    prices = []

    with open(
        csv_path,
        "r",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            date = row.get("date")
            close = safe_float(row.get("close"))

            if date and close is not None:

                prices.append(
                    {
                        "date": date,
                        "close": close,
                    }
                )

    prices.sort(
        key=lambda x: x["date"]
    )

    return prices


def find_price_index(prices, run_date):
    for index, row in enumerate(prices):

        if row["date"] == run_date:
            return index

    return None


def calculate_future_returns(prices, start_index):
    result = {}

    base_close = prices[start_index]["close"]

    for holding_days in HOLDING_DAYS_LIST:

        future_index = (
            start_index + holding_days
        )

        if future_index >= len(prices):

            result[f"future_date_{holding_days}d"] = None
            result[f"return_{holding_days}d"] = None

            continue

        future_close = prices[
            future_index
        ]["close"]

        return_pct = (
            (future_close - base_close)
            / base_close
        ) * 100

        result[f"future_date_{holding_days}d"] = prices[future_index]["date"]
        result[f"return_{holding_days}d"] = round(return_pct, 2)

    return result


def build_backtest_records():
    rows = load_analysis_results()
    records = []
    historical_cache = {}

    for row in rows:

        stock_id = str(row.get("stock_id")).zfill(4)
        run_date = row.get("run_date")

        if stock_id not in historical_cache:

            historical_cache[stock_id] = (
                load_historical_prices(stock_id)
            )

        prices = historical_cache[stock_id]

        if not prices:
            continue

        start_index = find_price_index(
            prices,
            run_date
        )

        if start_index is None:
            continue

        future_returns = calculate_future_returns(
            prices,
            start_index
        )

        record = dict(row)
        record.update(future_returns)

        records.append(record)

    return records


def judge_result(return_pct):
    if return_pct is None:
        return "pending"

    if return_pct > 0:
        return "win"

    if return_pct < 0:
        return "lose"

    return "flat"


def build_strategy_signal_logs(records):
    logs = []

    for strategy in STRATEGIES:

        matched_records = [
            record
            for record in records
            if strategy["filter"](record)
        ]

        for record in matched_records:

            for holding_days in HOLDING_DAYS_LIST:

                return_key = f"return_{holding_days}d"
                future_date_key = f"future_date_{holding_days}d"

                return_pct = record.get(return_key)

                logs.append(
                    {
                        "strategy_name": strategy["name"],
                        "signal_session": "pre_open",
                        "run_date": record.get("run_date"),
                        "future_date": record.get(future_date_key),
                        "stock_id": record.get("stock_id"),
                        "stock_name": record.get("stock_name"),
                        "rating": record.get("rating"),
                        "action": record.get("action"),
                        "total_score": record.get("total_score"),
                        "adr_score": record.get("adr_score"),
                        "holding_days": holding_days,
                        "future_return_pct": return_pct,
                        "result": judge_result(return_pct),
                    }
                )

    return logs


def export_strategy_signal_logs(logs):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_path = os.path.join(
        OUTPUT_DIR,
        "strategy_signal_logs.csv"
    )

    fieldnames = [
        "strategy_name",
        "signal_session",
        "run_date",
        "future_date",
        "stock_id",
        "stock_name",
        "rating",
        "action",
        "total_score",
        "adr_score",
        "holding_days",
        "future_return_pct",
        "result",
    ]

    with open(
        output_path,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(logs)

    return output_path


def calculate_strategy_performance(records):
    results = []

    for strategy in STRATEGIES:

        matched_records = [
            record
            for record in records
            if strategy["filter"](record)
        ]

        performance = {
            "strategy_name": strategy["name"],
            "matched_count": len(matched_records),
            "holding_results": {},
        }

        for holding_days in HOLDING_DAYS_LIST:

            key = f"return_{holding_days}d"

            pending_count = len(
                [
                    record
                    for record in matched_records
                    if record.get(key) is None
                ]
            )

            returns = [
                record.get(key)
                for record in matched_records
                if record.get(key) is not None
            ]

            trade_count = len(returns)

            if trade_count == 0:

                performance["holding_results"][
                    holding_days
                ] = {
                    "trade_count": 0,
                    "pending_count": pending_count,
                    "win_rate": None,
                    "avg_return": None,
                    "cumulative_return": None,
                }

                continue


            win_count = len(
                [
                    value
                    for value in returns
                    if value > 0
                ]
            )

            cumulative_return = 1.0

            for value in returns:
                cumulative_return *= (
                    1 + value / 100
                )

            performance["holding_results"][
                holding_days
            ] = {
                "trade_count": trade_count,
                "pending_count": pending_count,
                "win_rate": round(
                    win_count / trade_count * 100,
                    2
                ),
                "avg_return": round(
                    sum(returns) / trade_count,
                    2
                ),
                "cumulative_return": round(
                    (cumulative_return - 1) * 100,
                    2
                ),
            }

        results.append(performance)

    return results


def format_value(value, suffix=""):
    if value is None:
        return "N/A"

    return f"{value}{suffix}"


def print_strategy_performance(results):
    print("03-11-2 Strategy Backtest")
    print("=" * 30)
    print("回測基準：07:00 盤前推播")

    for result in results:

        print("")
        print(f"策略：{result['strategy_name']}")
        print(f"符合訊號數：{result['matched_count']}")

        header = (
            "持有天期 | 可計算筆數 | pending | "
            "勝率 | 平均報酬 | 累積報酬"
        )

        print(header)
        print("-" * len(header))

        for holding_days in HOLDING_DAYS_LIST:

            stats = result["holding_results"][
                holding_days
            ]

            print(
                f"{holding_days}日 | "
                f"{stats['trade_count']} | "
                f"{stats['pending_count']} | "
                f"{format_value(stats['win_rate'], '%')} | "
                f"{format_value(stats['avg_return'], '%')} | "
                f"{format_value(stats['cumulative_return'], '%')}"
            )


def run_strategy_backtest():
    records = build_backtest_records()

    if not records:
        print("03-11-2 Strategy Backtest")
        print("=" * 30)
        print("回測基準：07:00 盤前推播")
        print("")
        print("沒有 07:00 盤前回測資料")
        print("略過策略訊號明細輸出，避免覆蓋既有 CSV")

        return []

    results = calculate_strategy_performance(records)
    logs = build_strategy_signal_logs(records)
    output_path = export_strategy_signal_logs(logs)

    print_strategy_performance(results)

    print("")
    print("策略訊號明細輸出完成")
    print(f"檔案位置：{output_path}")
    print(f"明細筆數：{len(logs)}")

    return results

if __name__ == "__main__":
    run_strategy_backtest()

