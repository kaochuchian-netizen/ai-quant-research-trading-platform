from analysis.news_fetcher import fetch_stock_news
from analysis.news_prompt_builder import build_news_prompt

stock_id = "2330"
stock_name = "台積電"

news_items = fetch_stock_news(stock_id, stock_name)
prompt = build_news_prompt(stock_id, stock_name, news_items)

print(prompt)
