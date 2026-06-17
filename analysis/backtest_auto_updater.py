import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from analysis.backtest_engine import run_backtest
from analysis.strategy_backtest_engine import run_strategy_backtest
from analysis.strategy_ranking_engine import run_strategy_ranking


def run_stage(stage_name, stage_func):
    print("")
    print(f"開始執行：{stage_name}")
    print("-" * 40)

    try:
        result = stage_func()
        print(f"完成：{stage_name}")

        return {
            "stage": stage_name,
            "status": "success",
            "result": result,
            "error": None,
        }

    except Exception as e:
        print(f"失敗：{stage_name}")
        print(f"錯誤原因：{e}")

        return {
            "stage": stage_name,
            "status": "failed",
            "result": None,
            "error": str(e),
        }


def run_backtest_auto_update():
    print("")
    print("03-11-4 Backtest Auto Updater")
    print("=" * 40)
    print("自動執行回測更新流程")

    stages = [
        ("03-11-1 基礎回測引擎", run_backtest),
        ("03-11-2 策略回測引擎", run_strategy_backtest),
        ("03-11-3 策略排行榜", run_strategy_ranking),
    ]

    results = []

    for stage_name, stage_func in stages:
        stage_result = run_stage(stage_name, stage_func)
        results.append(stage_result)

    success_count = len(
        [
            item
            for item in results
            if item["status"] == "success"
        ]
    )

    failed_count = len(results) - success_count

    print("")
    print("03-11-4 Backtest Auto Updater Summary")
    print("=" * 40)
    print(f"總階段數：{len(results)}")
    print(f"成功：{success_count}")
    print(f"失敗：{failed_count}")

    if failed_count > 0:
        print("")
        print("失敗階段：")

        for item in results:
            if item["status"] == "failed":
                print(f"- {item['stage']}：{item['error']}")

    return results


def main():
    run_backtest_auto_update()


if __name__ == "__main__":
    main()
