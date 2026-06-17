from indicators.indicator_engine_v2 import build_indicator_result
from analysis.analysis_builder import build_analysis_input
from app.market.adr_service import get_adr_result


stock_id = "2330"
csv_path = f"data/historical/{stock_id}_daily.csv"

indicator_result = build_indicator_result(stock_id, csv_path)
adr_result = get_adr_result(stock_id)

analysis_input = build_analysis_input(
    indicator_result,
    adr_result
)

print("===== Analysis Builder with ADR =====")
print(analysis_input)
