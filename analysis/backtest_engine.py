import csv
import os
import sqlite3
from collections import defaultdict
from datetime import datetime

DB_PATH = "data/stock_analysis.db"
HISTORICAL_DIR = "data/historical"
HOLDING_DAYS_LIST = [1, 3, 5, 10, 20]

PRE_OPEN_START_HOUR = 5
PRE_OPEN_END_HOUR = 9


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
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            run_date,
            stock_id,
            stock_name,
            close_price,
            technical_score,
            news_score,
            adr_score,
            chip_score,
            total_score,
            rating,
            action,
            strategy,
            created_at,
            signal_session,
            pipeline_type,
            pipeline_run_id,
            signal_time,
            is_backtest_eligible,
            schema_version
        FROM analysis_results
        ORDER BY run_date ASC, stock_id ASC, id ASC
        """
    )

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    pre_open_rows = [
        row
        for row in rows
        if is_backtest_eligible_record(row)
    ]

    print(
        "回測資料篩選："
        f"全部 {len(rows)} 筆，"
        f"07:00 盤前區間 eligible pre_open records {len(pre_open_rows)} 筆"
    )

    return pre_open_rows


def load_historical_prices(stock_id):
    csv_path = os.path.join(HISTORICAL_DIR, f"{stock_id}_daily.csv")

    if not os.path.exists(csv_path):
        return []

    prices = []

    with open(csv_path, "r", encoding="utf-8-sig") as file:
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

    prices.sort(key=lambda x: x["date"])
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
        future_index = start_index + holding_days

        if future_index >= len(prices):
            result[f"return_{holding_days}d"] = None
            continue

        future_close = prices[future_index]["close"]
        return_pct = ((future_close - base_close) / base_close) * 100
        result[f"return_{holding_days}d"] = round(return_pct, 2)

    return result


def build_backtest_records():
    analysis_rows = load_analysis_results()
    records = []
    historical_cache = {}

    for row in analysis_rows:
        stock_id = str(row.get("stock_id")).zfill(4)
        run_date = row.get("run_date")

        if stock_id not in historical_cache:
            historical_cache[stock_id] = load_historical_prices(stock_id)

        prices = historical_cache[stock_id]

        if not prices:
            continue

        start_index = find_price_index(prices, run_date)

        if start_index is None:
            continue

        future_returns = calculate_future_returns(prices, start_index)

        record = dict(row)
        record.update(future_returns)
        records.append(record)

    return records


def summarize_records(records, group_key=None):
    summary = defaultdict(
        lambda: {
            "count": 0,
            "return_sum": defaultdict(float),
            "return_count": defaultdict(int),
            "win_count": defaultdict(int),
        }
    )

    for record in records:
        group_name = record.get(group_key) if group_key else "ALL"

        if not group_name:
            group_name = "UNKNOWN"

        summary[group_name]["count"] += 1

        for holding_days in HOLDING_DAYS_LIST:
            key = f"return_{holding_days}d"
            value = record.get(key)

            if value is None:
                continue

            summary[group_name]["return_sum"][key] += value
            summary[group_name]["return_count"][key] += 1

            if value > 0:
                summary[group_name]["win_count"][key] += 1

    return summary


def format_value(value, suffix=""):
    if value is None:
        return "N/A"

    return f"{value}{suffix}"


def build_summary_rows(summary):
    rows = []

    for group_name, data in summary.items():
        row = {
            "group": group_name,
            "count": data["count"],
        }

        for holding_days in HOLDING_DAYS_LIST:
            key = f"return_{holding_days}d"
            count = data["return_count"][key]

            if count == 0:
                row[f"avg_{holding_days}d"] = None
                row[f"win_rate_{holding_days}d"] = None
            else:
                avg_return = data["return_sum"][key] / count
                win_rate = data["win_count"][key] / count * 100

                row[f"avg_{holding_days}d"] = round(avg_return, 2)
                row[f"win_rate_{holding_days}d"] = round(win_rate, 2)

        rows.append(row)

    rows.sort(key=lambda x: str(x["group"]))
    return rows


def format_summary_table(title, summary):
    rows = build_summary_rows(summary)

    lines = []
    lines.append("")
    lines.append(title)
    lines.append("-" * len(title))

    if not rows:
        lines.append("無可回測資料")
        return "\n".join(lines)

    header = (
        "分類 | 筆數 | "
        "1日均報酬/勝率 | "
        "3日均報酬/勝率 | "
        "5日均報酬/勝率 | "
        "10日均報酬/勝率 | "
        "20日均報酬/勝率"
    )

    lines.append(header)
    lines.append("-" * len(header))

    for row in rows:
        line = (
            f"{row['group']} | "
            f"{row['count']} | "
            f"{format_value(row.get('avg_1d'), '%')}/"
            f"{format_value(row.get('win_rate_1d'), '%')} | "
            f"{format_value(row.get('avg_3d'), '%')}/"
            f"{format_value(row.get('win_rate_3d'), '%')} | "
            f"{format_value(row.get('avg_5d'), '%')}/"
            f"{format_value(row.get('win_rate_5d'), '%')} | "
            f"{format_value(row.get('avg_10d'), '%')}/"
            f"{format_value(row.get('win_rate_10d'), '%')} | "
            f"{format_value(row.get('avg_20d'), '%')}/"
            f"{format_value(row.get('win_rate_20d'), '%')}"
        )
        lines.append(line)

    return "\n".join(lines)


def generate_backtest_report():
    records = build_backtest_records()

    lines = []
    lines.append("03-11 Signal Backtest Report")
    lines.append("=" * 30)
    lines.append("回測基準：07:00 盤前推播")
    lines.append(f"有效回測筆數：{len(records)}")

    lines.append(format_summary_table("整體績效", summarize_records(records)))
    lines.append(format_summary_table("依 Rating 分組", summarize_records(records, "rating")))
    lines.append(format_summary_table("依 Action 分組", summarize_records(records, "action")))
    lines.append(format_summary_table("依股票分組", summarize_records(records, "stock_id")))

    return "\n".join(lines)


def run_backtest():
    report = generate_backtest_report()
    print(report)
    return report


if __name__ == "__main__":
    run_backtest()
