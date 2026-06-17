import os
import sys
from datetime import datetime


PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from analysis.strategy_backtest_engine import run_strategy_backtest
from analysis.strategy_ranking_engine import run_strategy_ranking


OUTPUT_DIR = "analysis/output"
SIGNAL_LOG_FILE = os.path.join(
    OUTPUT_DIR,
    "strategy_signal_logs.csv"
)
RANKING_FILE = os.path.join(
    OUTPUT_DIR,
    "strategy_ranking.csv"
)

def file_exists(path):
    return os.path.exists(path)


def print_file_status(path):
    if not file_exists(path):
        print(f"❌ 找不到輸出檔案：{path}")
        return

    size = os.path.getsize(path)

    print(f"✅ 輸出檔案存在：{path}")
    print(f"   檔案大小：{size} bytes")


def print_header():
    print("03-11-4 Backtest Result Updater")
    print("=" * 40)
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")


def run_backtest_update():
    print_header()

    print("Step 1：執行策略回測，更新 strategy_signal_logs.csv")
    print("-" * 40)

    backtest_results = run_strategy_backtest()

    print("")
    print("Step 1 完成")
    print_file_status(SIGNAL_LOG_FILE)
    print("")


    print("Step 2：執行策略排行榜，更新 strategy_ranking.csv")
    print("-" * 40)

    ranking_results = run_strategy_ranking()

    print("")
    print("Step 2 完成")
    print_file_status(RANKING_FILE)
    print("")

    print("03-11-4 自動回測更新完成")
    print("=" * 40)
    print(f"策略回測組數：{len(backtest_results)}")
    print(f"策略排名組數：{len(ranking_results)}")
    print("")

    return {
        "backtest_results": backtest_results,
        "ranking_results": ranking_results,
        "signal_log_file": SIGNAL_LOG_FILE,
        "ranking_file": RANKING_FILE,
    }


def main():
    run_backtest_update()


if __name__ == "__main__":
    main()


