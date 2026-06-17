from analysis.master_analysis_engine import (
    analyze_stock_full
)

result = analyze_stock_full(
    stock_id="2330",
    stock_name="台積電",
    csv_path="data/historical/2330_daily.csv"
)

print("===== ADR =====")
print(result["adr_result"])

print("===== ADR SCORE =====")
print(result["adr_score"])

print("===== NEWS SCORE =====")
print(result["news_score"])

print("===== TOTAL =====")
print(result["total_score"])
