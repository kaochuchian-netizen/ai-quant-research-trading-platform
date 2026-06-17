from analysis.analysis_engine import analyze_stock

sample_data = {
    "stock_id": "2330",
    "date": "2026-06-04",
    "close": 2385.0,

    "ma": {
        "ma5": 2380.0,
        "ma20": 2286.25,
        "ma60": 2086.33
    },

    "rsi": {
        "rsi14": 63.33
    },

    "macd": {
        "macd": 66.76,
        "signal": 61.34,
        "hist": 5.42
    },

    "bollinger": {
        "upper": 2416.18,
        "middle": 2286.25,
        "lower": 2156.32
    },

    "volume": {
        "volume": 24875,
        "volume_ma5": 39554.2,
        "volume_ma20": 32752.0
    },

    "signals": {
        "trend_signal": "strong_uptrend",
        "momentum_signal": "healthy_bullish",
        "macd_signal": "bullish_expanding",
        "bollinger_signal": "upper_half",
        "volume_signal": "normal_volume"
    },

    "score": {
        "bullish_score": 65,
        "risk_score": 0,
        "overall_rating": "bullish"
    },

    "rating": "bullish"
}

report = analyze_stock(sample_data)

print("===== AI Analysis =====")
print(report)
