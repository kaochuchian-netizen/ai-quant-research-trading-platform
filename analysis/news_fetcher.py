import feedparser
import requests
from urllib.parse import quote


def fetch_stock_news(stock_id: str, stock_name: str, max_items: int = 5):
    query = f"{stock_name} {stock_id} 股票"
    encoded_query = quote(query)

    url = (
        f"https://news.google.com/rss/search?"
        f"q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )

    response = requests.get(url, timeout=8, headers={"User-Agent": "stock-ai-news/1.0"})
    response.raise_for_status()
    feed = feedparser.parse(response.content)

    news_items = []

    for entry in feed.entries[:max_items]:
        news_items.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "source": entry.get("source", {}).get("title", "")
            if isinstance(entry.get("source", {}), dict)
            else "",
        })

    return news_items
