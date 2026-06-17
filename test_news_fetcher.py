from analysis.news_fetcher import fetch_stock_news

news = fetch_stock_news("2330", "台積電")

print("===== News Result =====")
for item in news:
    print(item["published"])
    print(item["title"])
    print(item["source"])
    print(item["link"])
    print("-----")
