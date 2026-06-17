def normalize_score(score):
    if score is None:
        return 50

    try:
        return int(score)
    except Exception:
        return 50


def format_number(value):
    if value is None:
        return "-"

    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return str(round(number, 2))
    except Exception:
        return str(value)


def format_lot(value):
    if value is None:
        return "-"

    try:
        number = int(float(value))

        if abs(number) >= 1000:
            return f"{round(number / 1000, 1)}千張"

        return f"{number}張"
    except Exception:
        return str(value)


def zh_signal(signal):
    mapping = {
        "strong_uptrend": "強多趨勢",
        "uptrend": "多頭趨勢",
        "sideways": "盤整",
        "downtrend": "空頭趨勢",
        "strong_downtrend": "強空趨勢",

        "healthy_bullish": "多方健康",
        "overheated": "短線過熱",
        "neutral": "中性",
        "neutral_weak": "中性偏弱",
        "weak_bearish": "偏弱",

        "strong_bullish": "強烈偏多",
        "bullish": "偏多",
        "slightly_bullish": "小幅偏多",
        "slightly_bearish": "小幅偏空",
        "bearish": "偏空",
        "strong_bearish": "強烈偏空",

        "bullish_expanding": "多方擴張",
        "bullish_weakening": "多方轉弱",
        "bearish_expanding": "空方擴張",
        "bearish_weakening": "空方轉弱",

        "break_upper": "突破上緣",
        "above_upper_band": "高於上緣",
        "upper_half": "偏上區間",
        "lower_half": "偏下區間",
        "break_lower": "跌破下緣",
        "below_lower_band": "低於下緣",

        "volume_expansion": "量能放大",
        "above_average_volume": "量能偏高",
        "normal_volume": "量能正常",
        "low_volume": "量能偏低",
    }

    if signal is None:
        return "-"

    return mapping.get(str(signal), str(signal))


def get_total_score(total_score_result, indicator_result):
    if isinstance(total_score_result, dict):
        return normalize_score(
            total_score_result.get("total_score")
            or total_score_result.get("score")
            or total_score_result.get("final_score")
        )

    score_data = indicator_result.get("score", {})

    if isinstance(score_data, dict):
        return normalize_score(score_data.get("bullish_score", 50))

    return normalize_score(score_data)


def get_rating_by_score(score):
    score = normalize_score(score)

    if score >= 80:
        return "A級"
    if score >= 65:
        return "B級"
    if score >= 50:
        return "C級"
    if score >= 35:
        return "D級"
    return "E級"


def get_signal_light(score):
    score = normalize_score(score)

    if score >= 65:
        return "🟢"
    if score >= 50:
        return "🟡"
    if score >= 35:
        return "🟠"
    return "🔴"


def get_key_warning(indicator_result):
    signals = indicator_result.get("signals", {})
    momentum = signals.get("momentum_signal")
    volume = signals.get("volume_signal")
    bollinger = signals.get("bollinger_signal")

    if momentum == "overheated":
        return "RSI偏熱"

    if bollinger in ["break_upper", "above_upper_band"]:
        return "短線偏高"

    if volume in ["volume_expansion", "breakout", "above_average_volume"]:
        return "量能放大"

    return ""


def get_action(score, chip_result=None):
    score = normalize_score(score)

    major_force = ""
    margin_status = ""

    if isinstance(chip_result, dict):
        major_force = chip_result.get("major_force_status", "")
        margin_status = chip_result.get("margin_status", "")

    if "籌碼偏空" in major_force:
        return "降低追價"

    if "籌碼偏亂" in major_force:
        return "保守觀望"

    if "融資增" in margin_status and score < 60:
        return "降低追價"

    if score >= 75:
        return "偏多續抱"
    if score >= 60:
        return "中性偏多"
    if score >= 50:
        return "中性觀察"
    if score >= 35:
        return "降低追價"

    return "保守觀望"


def format_news_text(news_result):
    if not news_result:
        return "新聞：中性"

    if isinstance(news_result, dict):
        news_signal = (
            news_result.get("news_signal")
            or news_result.get("signal")
            or news_result.get("direction")
        )

        news_signal = zh_signal(news_signal)

        if news_signal and news_signal != "-":
            return f"新聞：{news_signal}"

        return "新聞：中性"

    text = str(news_result).strip()

    if not text:
        return "新聞：中性"

    direction = ""

    for line in text.splitlines():
        line = line.strip()

        if line.startswith("消息面方向："):
            direction = line.replace("消息面方向：", "").strip()

    direction = zh_signal(direction)

    if direction and direction != "-":
        return f"新聞：{direction}"

    return "新聞：中性"


def format_adr_text(adr_result):
    if not adr_result:
        return "ADR：無"

    if adr_result.get("message"):
        return "ADR：無"

    adr_change = format_number(adr_result.get("change_rate"))
    adr_signal = zh_signal(adr_result.get("signal"))

    if adr_change != "-" and adr_signal != "-":
        return f"ADR：{adr_change}%（{adr_signal}）"

    if adr_change != "-":
        return f"ADR：{adr_change}%"

    return "ADR：無"


def format_institutional_text(chip_result):
    if not isinstance(chip_result, dict):
        return "法人：資料不足"

    result = chip_result.get("institutional", {})

    if result.get("status") != "ok":
        return "法人：資料不足"

    foreign = result.get("foreign", 0)
    trust = result.get("investment_trust", 0)

    foreign_text = "外資買" if foreign > 0 else "外資賣" if foreign < 0 else "外資平"
    trust_text = "投信買" if trust > 0 else "投信賣" if trust < 0 else "投信平"

    return f"法人：{foreign_text} / {trust_text}"


def format_major_force_text(chip_result):
    if not isinstance(chip_result, dict):
        return "主力：資料不足"

    status = chip_result.get("major_force_status", "主力資料不足")

    return f"主力：{status}"


def format_margin_text(chip_result):
    if not isinstance(chip_result, dict):
        return "資券：資料不足"

    margin = chip_result.get("margin", {})
    status = chip_result.get("margin_status", "資券資料不足")

    if margin.get("status") != "ok":
        return "資券：資料不足"

    margin_change = margin.get("margin_change", 0)
    short_change = margin.get("short_change", 0)

    return (
        f"資券：{status}"
        f"（資{format_lot(margin_change)} / 券{format_lot(short_change)}）"
    )


def format_chip_score_text(chip_result):
    if not isinstance(chip_result, dict):
        return "籌碼：資料不足"

    chip_score = normalize_score(chip_result.get("chip_score", 50))

    if chip_score >= 65:
        direction = "偏多"
    elif chip_score >= 50:
        direction = "中性偏多"
    elif chip_score >= 35:
        direction = "中性偏空"
    else:
        direction = "偏空"

    return f"籌碼：{direction}（{chip_score}）"


def format_stock_report_v2(
    stock_id,
    stock_name,
    indicator_result,
    ai_analysis,
    adr_result=None,
    news_result=None,
    total_score_result=None,
    chip_result=None,
):
    score = get_total_score(total_score_result, indicator_result)
    rating = get_rating_by_score(score)
    light = get_signal_light(score)
    action = get_action(score, chip_result)
    warning = get_key_warning(indicator_result)

    close = format_number(indicator_result.get("close"))

    signals = indicator_result.get("signals", {})
    trend_signal = zh_signal(signals.get("trend_signal", "-"))
    momentum_signal = zh_signal(signals.get("momentum_signal", "-"))

    adr_text = format_adr_text(adr_result)
    news_text = format_news_text(news_result)

    institutional_text = format_institutional_text(chip_result)
    major_force_text = format_major_force_text(chip_result)
    margin_text = format_margin_text(chip_result)
    chip_score_text = format_chip_score_text(chip_result)

    report = f"""【{stock_id} {stock_name}】盤前 {light}

{rating}｜{score}分

收盤：{close}

技術：{trend_signal}
動能：{momentum_signal}
{adr_text}
{institutional_text}
{major_force_text}
{margin_text}
{news_text}
{chip_score_text}

策略：{action}"""

    if warning:
        report = f"{report}\n\n{warning}"

    return report.strip()


def format_multi_stock_report_v2(reports):
    return "\n\n----------------\n\n".join(reports)
