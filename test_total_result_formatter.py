from analysis.master_analysis_engine import (
    analyze_stock_full
)

from reports.total_result_formatter import (
    format_total_result
)

result = analyze_stock_full(
    stock_id="2330",
    stock_name="台積電",
    csv_path="data/historical/2330_daily.csv"
)

report = format_total_result(result)

print(report)
