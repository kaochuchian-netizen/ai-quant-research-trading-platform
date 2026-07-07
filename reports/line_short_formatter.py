DASHBOARD_URL = "http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html"


def format_line_short(result):
    """Return the approved link-only LINE notification."""
    payload = result or {}
    window = str(payload.get("scheduler_window") or payload.get("pipeline_type") or "pre_open_0700")
    if window in {"intraday", "intraday_1305"}:
        title = "【Stock AI】13:05 盤中追蹤已更新"
        body = "盤中狀態、風險變化與資料完整度請看 Dashboard。"
    elif window in {"pre_close", "pre_close_1335", "close_snapshot_1335"}:
        title = "【Stock AI】13:35 收盤快照已更新"
        body = "收盤快照、當日狀態與後續檢討進度請看 Dashboard。"
    elif window in {"post_close", "post_close_1500", "prediction_review", "prediction_review_1500"}:
        title = "【Stock AI】15:00 盤後檢討已更新"
        body = "單日檢討、7 天滾動檢討、樣本累積與校準狀態請看 Dashboard。"
    else:
        title = "【Stock AI】07:00 盤前決策摘要已更新"
        body = "今日盤前報告、baseline 預測、資料品質與風險提示請看 Dashboard。"
    return "\n".join([title, body, "Dashboard：", DASHBOARD_URL, "僅供研究參考，非交易指令。"])
