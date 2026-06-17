import csv
import math
import os
from collections import defaultdict

INPUT_FILE = "analysis/output/strategy_signal_logs.csv"
OUTPUT_FILE = "analysis/output/strategy_ranking.csv"


def safe_float(value):
    try:
        if value is None or value == "" or value == "N/A":
            return None
        return float(value)
    except ValueError:
        return None


def calc_sharpe(returns):
    if len(returns) < 2:
        return None

    avg_return = sum(returns) / len(returns)
    variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
    std_return = math.sqrt(variance)

    if std_return == 0:
        return None

    return avg_return / std_return


def consistency_star(sharpe):
    if sharpe is None:
        return "N/A"
    if sharpe >= 1.8:
        return "★★★★★"
    if sharpe >= 1.5:
        return "★★★★☆"
    if sharpe >= 1.0:
        return "★★★☆☆"
    if sharpe >= 0.5:
        return "★★☆☆☆"
    return "★☆☆☆☆"


def load_strategy_logs():
    if not os.path.exists(INPUT_FILE):
        print(f"找不到檔案：{INPUT_FILE}")
        return []

    rows = []

    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            strategy = row.get("strategy_name") or row.get("strategy")
            holding_days = row.get("holding_days")
            return_pct = row.get("future_return_pct") or row.get("return_pct")
            result = row.get("result")

            if not strategy:
                continue

            rows.append({
                "strategy": strategy,
                "holding_days": holding_days,
                "return_pct": safe_float(return_pct),
                "result": result,
            })

    return rows


def build_ranking(rows):
    grouped = defaultdict(lambda: {
        "returns": [],
        "pending": 0,
        "total": 0,
    })

    for row in rows:
        key = (row["strategy"], row["holding_days"])

        grouped[key]["total"] += 1

        if row["return_pct"] is None:
            grouped[key]["pending"] += 1
            continue

        grouped[key]["returns"].append(row["return_pct"])


    ranking = []

    for (strategy, holding_days), data in grouped.items():
        returns = data["returns"]
        completed = len(returns)
        pending = data["pending"]
        total = data["total"]

        if completed == 0:
            ranking.append({
                "strategy": strategy,
                "holding_days": holding_days,
                "total": total,
                "completed": 0,
                "pending": pending,
                "win_rate": None,
                "avg_return": None,
                "cumulative_return": None,
                "sharpe": None,
                "consistency": "N/A",
                "ranking_score": -999999,
            })
            continue

        win_count = sum(1 for r in returns if r > 0)
        win_rate = win_count / completed * 100
        avg_return = sum(returns) / completed

        cumulative_multiplier = 1.0
        for r in returns:
            cumulative_multiplier *= (1 + r / 100)

        cumulative_return = (cumulative_multiplier - 1) * 100

        sharpe = calc_sharpe(returns)

        ranking_score = (
            cumulative_return * 0.4
            + avg_return * 0.3
            + win_rate * 0.2
            + ((sharpe or 0) * 10) * 0.1
        )

        ranking.append({
            "strategy": strategy,
            "holding_days": holding_days,
            "total": total,
            "completed": completed,
            "pending": pending,
            "win_rate": win_rate,
            "avg_return": avg_return,
            "cumulative_return": cumulative_return,
            "sharpe": sharpe,
            "consistency": consistency_star(sharpe),
            "ranking_score": ranking_score,
        })

    ranking.sort(key=lambda x: x["ranking_score"], reverse=True)

    return ranking


def fmt_pct(value):
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def fmt_num(value):
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def export_ranking(ranking):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    fieldnames = [
        "rank",
        "strategy",
        "holding_days",
        "total",
        "completed",
        "pending",
        "win_rate",
        "avg_return",
        "cumulative_return",
        "sharpe",
        "consistency",
        "ranking_score",
    ]

    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, item in enumerate(ranking, start=1):
            writer.writerow({
                "rank": idx,
                "strategy": item["strategy"],
                "holding_days": item["holding_days"],
                "total": item["total"],
                "completed": item["completed"],
                "pending": item["pending"],
                "win_rate": round(item["win_rate"], 2) if item["win_rate"] is not None else "",
                "avg_return": round(item["avg_return"], 2) if item["avg_return"] is not None else "",
                "cumulative_return": round(item["cumulative_return"], 2) if item["cumulative_return"] is not None else "",
                "sharpe": round(item["sharpe"], 4) if item["sharpe"] is not None else "",
                "consistency": item["consistency"],
                "ranking_score": round(item["ranking_score"], 4),
            })

    return OUTPUT_FILE


def print_ranking(ranking):
    print("03-11-3 Strategy Ranking")
    print("==============================")

    if not ranking:
        print("沒有策略資料")
        return

    print("排名 | 策略 | 持有天期 | 總筆數 | 完成 | pending | 勝率 | 平均報酬 | 累積報酬 | Sharpe | 穩定度")
    print("-" * 110)

    for idx, item in enumerate(ranking, start=1):
        print(
            f"{idx} | "
            f"{item['strategy']} | "
            f"{item['holding_days']}日 | "
            f"{item['total']} | "
            f"{item['completed']} | "
            f"{item['pending']} | "
            f"{fmt_pct(item['win_rate'])} | "
            f"{fmt_pct(item['avg_return'])} | "
            f"{fmt_pct(item['cumulative_return'])} | "
            f"{fmt_num(item['sharpe'])} | "
            f"{item['consistency']}"
        )


def run_strategy_ranking():
    rows = load_strategy_logs()
    ranking = build_ranking(rows)
    print_ranking(ranking)

    output_path = export_ranking(ranking)

    print("")
    print("策略排行榜輸出完成")
    print(f"檔案位置：{output_path}")
    print(f"排名筆數：{len(ranking)}")

    return ranking


def main():
    run_strategy_ranking()


if __name__ == "__main__":
    main()
