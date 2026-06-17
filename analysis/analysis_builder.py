def build_analysis_input(indicator_result, adr_result=None):
    """
    將 Indicator Engine v2 與 ADR 結果整理成 AI 分析用輸入資料
    """

    return {
        "stock_id": indicator_result.get("stock_id"),
        "date": indicator_result.get("date"),
        "close": indicator_result.get("close"),

        "ma": indicator_result.get("ma", {}),
        "rsi": indicator_result.get("rsi"),
        "macd": indicator_result.get("macd", {}),
        "bollinger": indicator_result.get("bollinger", {}),
        "volume": indicator_result.get("volume", {}),

        "signals": indicator_result.get("signals", {}),
        "score": indicator_result.get("score"),
        "rating": indicator_result.get("score", {}).get("overall_rating"),

        "adr": adr_result,
    }
