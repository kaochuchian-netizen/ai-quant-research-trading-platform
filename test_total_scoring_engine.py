from analysis.total_scoring_engine import (
    calculate_total_score
)

result = calculate_total_score(
    technical_score=80,
    news_score=70,
    adr_score=75
)

print(result)
