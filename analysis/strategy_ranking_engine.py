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


def calc_max_drawdown(returns):
    if not returns:
        return None

    equity = 1.0
    peak_equity = equity
    max_drawdown = 0.0

    for return_pct in returns:
        equity *= (1 + return_pct / 100)
        peak_equity = max(peak_equity, equity)
        drawdown = (equity - peak_equity) / peak_equity
        max_drawdown = min(max_drawdown, drawdown)

    return max_drawdown * 100


def calc_pending_ratio(completed, pending):
    denominator = completed + pending

    if denominator == 0:
        return None

    return pending / denominator * 100


def determine_ranking_status(
    completed,
    pending,
    max_drawdown,
    min_trade_count=20,
    max_pending_ratio=30.0,
    max_drawdown_limit=-20.0,
):
    if completed < min_trade_count:
        return (
            "insufficient_sample",
            f"trade_count {completed} < minimum {min_trade_count}",
        )

    pending_ratio = calc_pending_ratio(completed, pending)

    if pending_ratio is not None and pending_ratio > max_pending_ratio:
        return (
            "too_many_pending",
            f"pending_ratio {pending_ratio:.2f}% > maximum {max_pending_ratio:.2f}%",
        )

    if max_drawdown is None:
        return ("risk_rejected", "max_drawdown unavailable")

    if max_drawdown < max_drawdown_limit:
        return (
            "risk_rejected",
            f"max_drawdown {max_drawdown:.2f}% < limit {max_drawdown_limit:.2f}%",
        )

    return ("candidate_watchlist", "passed initial ranking filters")


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
        pending_ratio = calc_pending_ratio(completed, pending)
        max_drawdown = calc_max_drawdown(returns)
        ranking_status, ranking_reason = determine_ranking_status(
            completed,
            pending,
            max_drawdown,
        )

        if completed == 0:
            ranking.append({
                "strategy": strategy,
                "holding_days": holding_days,
                "total": total,
                "completed": 0,
                "pending": pending,
                "pending_ratio": pending_ratio,
                "win_rate": None,
                "avg_return": None,
                "cumulative_return": None,
                "max_drawdown": None,
                "sharpe": None,
                "consistency": "N/A",
                "ranking_status": ranking_status,
                "ranking_reason": ranking_reason,
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
            "pending_ratio": pending_ratio,
            "win_rate": win_rate,
            "avg_return": avg_return,
            "cumulative_return": cumulative_return,
            "max_drawdown": max_drawdown,
            "sharpe": sharpe,
            "consistency": consistency_star(sharpe),
            "ranking_status": ranking_status,
            "ranking_reason": ranking_reason,
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


def export_ranking(ranking, output_path=None):
    target_path = output_path or OUTPUT_FILE
    target_dir = os.path.dirname(target_path)

    if target_dir:
        os.makedirs(target_dir, exist_ok=True)

    fieldnames = [
        "rank",
        "strategy",
        "holding_days",
        "total",
        "completed",
        "pending",
        "pending_ratio",
        "win_rate",
        "avg_return",
        "cumulative_return",
        "max_drawdown",
        "sharpe",
        "consistency",
        "ranking_status",
        "ranking_reason",
        "ranking_score",
    ]

    with open(target_path, "w", encoding="utf-8-sig", newline="") as f:
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
                "pending_ratio": round(item["pending_ratio"], 2) if item["pending_ratio"] is not None else "",
                "win_rate": round(item["win_rate"], 2) if item["win_rate"] is not None else "",
                "avg_return": round(item["avg_return"], 2) if item["avg_return"] is not None else "",
                "cumulative_return": round(item["cumulative_return"], 2) if item["cumulative_return"] is not None else "",
                "max_drawdown": round(item["max_drawdown"], 2) if item["max_drawdown"] is not None else "",
                "sharpe": round(item["sharpe"], 4) if item["sharpe"] is not None else "",
                "consistency": item["consistency"],
                "ranking_status": item["ranking_status"],
                "ranking_reason": item["ranking_reason"],
                "ranking_score": round(item["ranking_score"], 4),
            })

    return target_path


def print_ranking(ranking):
    print("03-11-3 Strategy Ranking")
    print("==============================")

    if not ranking:
        print("沒有策略資料")
        return

    print("排名 | 策略 | 持有天期 | 總筆數 | 完成 | pending | 勝率 | 平均報酬 | 累積報酬 | Sharpe | 穩定度 | 狀態 | 原因")
    print("-" * 150)

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
            f"{item['consistency']} | "
            f"{item['ranking_status']} | "
            f"{item['ranking_reason']}"
        )


def run_strategy_ranking():
    rows = load_strategy_logs()

    if not rows:
        print("03-11-3 Strategy Ranking")
        print("==============================")
        print("沒有策略資料")
        print("略過策略排行榜輸出，避免覆蓋既有 CSV")

        return []

    ranking = build_ranking(rows)

    if not ranking:
        print("03-11-3 Strategy Ranking")
        print("==============================")
        print("沒有可排名策略")
        print("略過策略排行榜輸出，避免覆蓋既有 CSV")

        return []

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
