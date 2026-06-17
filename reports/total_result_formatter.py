def format_total_result(result):

    indicator = result["indicator"]

    total_score = result["total_score"]

    news_score = result["news_score"]

    adr_score = result["adr_score"]

    stock_id = indicator["stock_id"]

    rating = total_score["rating"]

    action = total_score["action"]

    score = total_score["total_score"]

    trend = indicator["signals"]["trend_signal"]

    report = f"""
【{stock_id}】

總評分：{rating}
投資建議：{action}
綜合分數：{score}

技術面：
{indicator['score']['bullish_score']}

新聞面：
{news_score['score']}

ADR：
{adr_score}

趨勢：
{trend}
"""

    return report
