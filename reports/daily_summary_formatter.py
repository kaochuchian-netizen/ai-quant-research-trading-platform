def format_daily_summary(results):
    lines = []

    lines.append("【每日股票總結】")
    lines.append("")

    if not results:
        lines.append("今日沒有可分析的股票資料")
        return "\n".join(lines)

    date = results[0].get("date", "")
    lines.append(f"日期：{date}")
    lines.append(f"追蹤檔數：{len(results)}")
    lines.append("")

    strong = []
    watch = []
    weak = []

    for item in results:
        stock_id = item.get("stock_id", "")
        rating = item.get("rating", "")
        score = item.get("score", 0)

        if score >= 80:
            strong.append(stock_id)
        elif score >= 60:
            watch.append(stock_id)
        else:
            weak.append(stock_id)

    lines.append("一、今日重點")
    lines.append(f"- 強勢：{', '.join(strong) if strong else '無'}")
    lines.append(f"- 觀察：{', '.join(watch) if watch else '無'}")
    lines.append(f"- 弱勢：{', '.join(weak) if weak else '無'}")
    lines.append("")

    lines.append("二、個股摘要")

    for item in results:
        stock_id = item.get("stock_id", "")
        stock_name = item.get("stock_name", "")
        close = item.get("close", "")
        rating = item.get("rating", "")
        score = item.get("score", "")
        signals = item.get("signals", {})

        trend = signals.get("trend_signal", "")
        momentum = signals.get("momentum_signal", "")

        lines.append("")
        title = f"{stock_id} {stock_name}".strip()
        lines.append(title)
        lines.append(f"- 收盤：{close}")
        lines.append(f"- 評級：{rating} / 分數：{score}")
        lines.append(f"- 趨勢：{trend}")
        lines.append(f"- 動能：{momentum}")
        lines.append(f"- 策略：{build_simple_strategy(item)}")

    lines.append("")
    lines.append("三、明日優先觀察")

    top_results = sorted(
        results,
        key=lambda x: x.get("score", 0),
        reverse=True
    )[:3]

    for i, item in enumerate(top_results, start=1):
        stock_id = item.get("stock_id", "")
        lines.append(f"{i}. {stock_id}：觀察趨勢是否延續")

    return "\n".join(lines)


def build_simple_strategy(item):
    score = item.get("score", 0)
    signals = item.get("signals", {})
    trend = signals.get("trend_signal", "")
    momentum = signals.get("momentum_signal", "")

    if score >= 80:
        return "偏多續抱，拉回觀察支撐"
    if score >= 60:
        return "可續觀察，不建議追高"
    if trend in ["downtrend", "strong_downtrend"]:
        return "偏弱，等待止跌或轉強"
    if momentum in ["weak_bearish", "bearish"]:
        return "動能偏弱，降低進場急迫性"

    return "區間整理，等待明確訊號"
