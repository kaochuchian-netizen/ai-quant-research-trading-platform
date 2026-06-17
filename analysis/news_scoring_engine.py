def calculate_news_score(news_analysis: str):

    analysis = news_analysis.lower()

    score = 50

    bullish_keywords = [
        "偏多",
        "樂觀",
        "成長",
        "創新高",
        "上漲",
        "利多",
        "強勁",
        "買盤",
    ]

    bearish_keywords = [
        "偏空",
        "衰退",
        "下滑",
        "利空",
        "風險",
        "修正",
        "競爭加劇",
    ]

    for word in bullish_keywords:
        if word in news_analysis:
            score += 5

    for word in bearish_keywords:
        if word in news_analysis:
            score -= 5

    score = max(0, min(score, 100))

    if score >= 80:
        sentiment = "bullish"

    elif score >= 60:
        sentiment = "slightly_bullish"

    elif score >= 40:
        sentiment = "neutral"

    elif score >= 20:
        sentiment = "slightly_bearish"

    else:
        sentiment = "bearish"

    return {
        "score": score,
        "sentiment": sentiment,
    }
