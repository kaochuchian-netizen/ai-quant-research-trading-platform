from analysis.news_fetcher import fetch_stock_news
from analysis.news_prompt_builder import build_news_prompt
from analysis.gemini_client import generate_analysis


def analyze_news(stock_id, stock_name):
    news_items = fetch_stock_news(stock_id, stock_name)

    prompt = build_news_prompt(
        stock_id,
        stock_name,
        news_items
    )

    result = generate_analysis(prompt)

    return result
