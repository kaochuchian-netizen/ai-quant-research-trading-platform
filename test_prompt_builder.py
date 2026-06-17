from indicators.indicator_engine_v2 import build_indicator_result
from analysis.analysis_builder import build_analysis_input
from analysis.prompt_builder import build_analysis_prompt


stock_id = "2330"
csv_path = "data/historical/2330_daily.csv"

indicator_result = build_indicator_result(stock_id, csv_path)

analysis_input = build_analysis_input(indicator_result)

prompt = build_analysis_prompt(analysis_input)

print("===== Prompt Builder =====")
print(prompt)
