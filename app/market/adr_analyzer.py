def judge_adr_signal(change_rate):

    if change_rate >= 5:
        return "strong_bullish"

    if change_rate >= 2:
        return "bullish"

    if change_rate > -2:
        return "neutral"

    if change_rate > -5:
        return "bearish"

    return "strong_bearish"

