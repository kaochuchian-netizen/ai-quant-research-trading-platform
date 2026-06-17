from indicators.indicator_engine_v2 import (
    build_indicator_result
)

from analysis.analysis_engine import (
    analyze_stock
)

from analysis.news_analysis_engine import (
    analyze_news
)

from analysis.news_scoring_engine import (
    calculate_news_score
)

from analysis.total_scoring_engine import (
    calculate_total_score
)

from app.market.adr_service import (
    get_adr_result
)

from app.market.adr_score_engine import (
    calculate_adr_score
)

def analyze_stock_full(
    stock_id,
    stock_name,
    csv_path
):

    # 技術面

    indicator_result = build_indicator_result(
        stock_id,
        csv_path
    )

    technical_score = indicator_result["score"]["bullish_score"]
    # AI技術分析

    ai_analysis = analyze_stock(
        indicator_result
    )

    # 新聞分析

    news_analysis = analyze_news(
        stock_id,
        stock_name
    )

    news_result = calculate_news_score(
        news_analysis
    )

    news_score = news_result["score"]

    # ADR

    adr_result = get_adr_result(
        stock_id
    )

    adr_score = calculate_adr_score(
        adr_result
    )

    # 總分

    total_result = calculate_total_score(
        technical_score,
        news_score,
        adr_score
    )

    return {
        "stock_name": stock_name,

        "indicator": indicator_result,
        "ai_analysis": ai_analysis,
 
        "news_analysis": news_analysis,
        "news_score": news_result,

        "adr_result": adr_result,
        "adr_score": adr_score,

        "total_score": total_result
    }
