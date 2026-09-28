"""Prediction-side rule extracted unchanged from tw_ohlcv_range_direction_v2.
No tactical score, outcome band, market data or action ownership.
"""
def moving_average_direction(ma5, ma10):
    if ma5 is not None and ma10 is not None and ma5 > ma10 * 1.002:
        return "bullish"
    if ma5 is not None and ma10 is not None and ma5 < ma10 * .998:
        return "bearish"
    return "neutral"
