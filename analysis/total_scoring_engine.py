def normalize_score(score):
    try:
        return int(score or 50)
    except Exception:
        return 50


def calculate_total_score(
    technical_score,
    news_score,
    adr_score,
    chip_score=50,
):
    technical_score = normalize_score(technical_score)
    news_score = normalize_score(news_score)
    adr_score = normalize_score(adr_score)
    chip_score = normalize_score(chip_score)

    total_score = (
        technical_score * 0.40
        + news_score * 0.20
        + adr_score * 0.20
        + chip_score * 0.20
    )

    total_score = round(total_score)

    if total_score >= 80:
        rating = "A級"
        action = "偏多加碼"
    elif total_score >= 65:
        rating = "B級"
        action = "偏多續抱"
    elif total_score >= 50:
        rating = "C級"
        action = "中性觀察"
    elif total_score >= 35:
        rating = "D級"
        action = "降低追價"
    else:
        rating = "E級"
        action = "保守觀望"

    return {
        "total_score": total_score,
        "rating": rating,
        "action": action,
        "technical_score": technical_score,
        "news_score": news_score,
        "adr_score": adr_score,
        "chip_score": chip_score,
    }
