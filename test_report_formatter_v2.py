from reports.report_formatter_v2 import format_stock_report_v2


sample_indicator_result = {
    "stock_id": "2330",
    "date": "2026-06-04",
    "close": 1080,
    "score": 85,
    "rating": "A",
    "signals": {
        "trend_signal": "strong_uptrend",
        "momentum_signal": "neutral",
        "macd_signal": "weak_bearish",
        "bollinger_signal": "break_upper",
        "volume_signal": "volume_expansion",
    }
}


report = format_stock_report_v2(
    stock_id="2330",
    stock_name="台積電",
    indicator_result=sample_indicator_result,
    ai_analysis=None
)

print(report)
