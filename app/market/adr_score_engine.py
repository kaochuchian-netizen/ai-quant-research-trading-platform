def calculate_adr_score(adr_result):
    if not adr_result:
        return 50

    signal = adr_result.get("signal")

    mapping = {
        "strong_bullish": 85,
        "bullish": 70,
        "neutral": 50,
        "bearish": 30,
        "strong_bearish": 15,
    }

    return mapping.get(signal, 50)
