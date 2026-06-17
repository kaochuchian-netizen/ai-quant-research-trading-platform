from reports.line_report_sender import send_line_report


message = """
【AI 股票分析系統測試】

LINE Report Sender 已建立成功

股票代號：2330
日期：2026-05-29

測試完成
"""

result = send_line_report(message)

print(result)
