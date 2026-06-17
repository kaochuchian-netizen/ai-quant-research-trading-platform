from indicators.indicator_engine_v2 import build_indicator_result


if __name__ == "__main__":
    result = build_indicator_result(
        stock_id="2330",
        csv_path="data/historical/2330_daily.csv"
    )

    print("===== Indicator Engine v2 =====")
    print(result)
