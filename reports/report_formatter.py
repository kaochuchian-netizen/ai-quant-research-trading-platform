SIGNAL_LABELS = {
    "strong_uptrend": "強多",
    "uptrend": "偏多",
    "neutral": "中性",
    "sideways": "震盪",
    "downtrend": "偏空",
    "strong_downtrend": "強空",
    "weak_bearish": "轉弱",
    "weak_bullish": "偏多",
    "bullish": "偏多",
    "bearish": "偏空",
    "positive_but_weakening": "偏多轉弱",
    "break_upper": "突破",
    "above_upper_band": "突破",
    "break_lower": "跌破",
    "inside_band": "區間",
    "volume_expansion": "量增",
    "volume_shrink": "量縮",
}


def translate_signal(signal):
    return SIGNAL_LABELS.get(signal, signal)


def trend_icon(signal):
    if signal in ["strong_uptrend", "uptrend"]:
        return "🟢"
    if signal in ["downtrend", "strong_downtrend"]:
        return "🔴"
    return "🟡"


def judge_action(trend_signal, macd_signal):
    if trend_signal in ["strong_uptrend", "uptrend"]:
        if macd_signal in ["weak_bearish", "positive_but_weakening", "bearish"]:
            return "續抱，不追高"
        return "續抱"

    if trend_signal in ["downtrend", "strong_downtrend"]:
        return "減碼/避開"

    return "觀望"


def format_stock_report(stock_id, indicator_result, ai_analysis):
    stock_name = indicator_result.get("stock_name", stock_id)

    rsi = indicator_result.get("rsi", {})
    signals = indicator_result.get("signals", {})
    adr = indicator_result.get("adr")

    trend_signal = signals.get("trend_signal", "")
    macd_signal = signals.get("macd_signal", "")
    volume_signal = signals.get("volume_signal", "")

    icon = trend_icon(trend_signal)
    action = judge_action(trend_signal, macd_signal)

    rsi14 = rsi.get("rsi14", "")

    adr_line = ""
    if adr:
        adr_line = (
            f"\nADR {adr.get('change_rate')}%｜"
            f"{translate_signal(adr.get('signal'))}"
        )

    report = f"""
{stock_id} {stock_name}
{icon} {translate_signal(trend_signal)}{adr_line}
RSI {rsi14}｜MACD {translate_signal(macd_signal)}
量能 {translate_signal(volume_signal)}
建議：{action}
"""

    return report.strip()
