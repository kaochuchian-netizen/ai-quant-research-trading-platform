from analysis.news_analysis_engine import analyze_news
from analysis.news_scoring_engine import calculate_news_score

analysis = analyze_news(
    "2330",
    "台積電"
)

result = calculate_news_score(analysis)

print(result)
