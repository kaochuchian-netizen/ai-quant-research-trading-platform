from reports.report_formatter import format_stock_report


indicator_result = {
    "stock_id": "2330",
    "date": "2026-05-29",
    "close": 2355.0,
    "ma": {
        "ma5": 2306.0,
        "ma20": 2263.25,
        "ma60": 2051.67
    },
    "rsi": {
        "rsi14": 63.33
    },
    "macd": {
        "macd": 55.75,
        "signal": 57.43,
        "hist": -1.67
    },
    "bollinger": {
        "upper": 2343.27,
        "middle": 2263.25,
        "lower": 2183.23
    },
    "volume": {
        "volume": 85969,
        "volume_ma5": 40386.2,
        "volume_ma20": 33485.0
    },
    "signals": {
        "trend_signal": "strong_uptrend",
        "momentum_signal": "neutral",
        "macd_signal": "weak_bearish",
        "bollinger_signal": "break_upper",
        "volume_signal": "volume_expansion"
    },
    "score": 75,
    "rating": "偏多"
}

ai_analysis = """
台積電目前股價維持在主要均線之上，整體趨勢偏多。
短線雖然出現 MACD 動能略為收斂，但成交量放大，代表市場關注度仍高。
操作上可觀察是否能站穩短期均線，若量能持續放大，後續仍有延續強勢的機會。
"""

report = format_stock_report(
    stock_id="2330",
    indicator_result=indicator_result,
    ai_analysis=ai_analysis
)

print(report)
