from analysis.analysis_builder import build_analysis_input
from analysis.prompt_builder import build_analysis_prompt
from analysis.gemini_client import generate_analysis
from app.market.adr_service import get_adr_result


def analyze_stock(indicator_result, adr_result=None, news_result=None):
    """
    產生 AI 分析報告
    """
    if adr_result is None:
        stock_id = indicator_result.get("stock_id")
        adr_result = get_adr_result(stock_id)

    indicator_result["adr"] = adr_result

    analysis_input = build_analysis_input(
        indicator_result,
        adr_result
    )

    analysis_input["news"] = news_result

    prompt = build_analysis_prompt(analysis_input)

    report = generate_analysis(prompt)

    return report
