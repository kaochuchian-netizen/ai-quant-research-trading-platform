def format_line_short(result):

    indicator = result["indicator"]

    total_score = result["total_score"]

    news_score = result["news_score"]

    adr_score = result["adr_score"]

    stock_id = indicator["stock_id"]

    stock_name = result.get(
        "stock_name",
        ""
    )

    score = total_score["total_score"]

    rating = total_score["rating"]

    action = total_score["action"]

    action_mapping = {
        "Strong Buy": "強力買進",
        "Buy": "偏多布局",
        "Watch": "持續觀察",
        "Neutral": "中性觀望",
        "Avoid": "避免進場"
    }

    action = action_mapping.get(
        action,
        action
    )

    trend = indicator["signals"]["trend_signal"]

    if trend == "strong_uptrend":
        icon = "🟢"
        summary = "多頭趨勢延續"

    elif trend == "uptrend":
        icon = "🟡"
        summary = "偏多整理"

    elif trend == "sideways":
        icon = "⚪"
        summary = "區間震盪"

    else:
        icon = "🔴"
        summary = "空頭趨勢"

    report = f"""
【{stock_id} {stock_name}】{icon}

{rating}級｜{score}分

技術：{indicator['score']['bullish_score']}
新聞：{news_score['score']}
ADR：{adr_score}

策略：{action}

{summary}
"""

    return report.strip()
