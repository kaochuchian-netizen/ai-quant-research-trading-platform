# AI-DEV-158 LINE Runtime Preview

Dry-run only. No LINE, Email, or external notification was sent.

Dashboard URL: http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html

## 07:00 pre_open_0700

Formatter: `app.pipelines.pre_open_pipeline.send_reports_in_batches -> reports.line_short_formatter.format_line_short`

```text
【Stock AI】07:00 盤前決策摘要已更新
今日盤前報告、baseline 預測、資料品質與風險提示請看 Dashboard。
Dashboard：
http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html
僅供研究參考，非交易指令。
```
Forbidden content hits: 0

## 13:05 intraday_1305

Formatter: `scripts.orchestrator.approved_pre_open_delivery.build_line_message -> app.reports.multi_window_formatter.line_notification_text`

```text
【Stock AI】13:05 盤中追蹤已更新
盤中狀態、風險變化與資料完整度請看 Dashboard。
Dashboard：
http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html
僅供研究參考，非交易指令。
```
Forbidden content hits: 0

## 13:35 pre_close_1335

Formatter: `scripts.orchestrator.approved_pre_open_delivery.build_line_message -> app.reports.multi_window_formatter.line_notification_text`

```text
【Stock AI】13:35 收盤快照已更新
收盤快照、當日狀態與後續檢討進度請看 Dashboard。
Dashboard：
http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html
僅供研究參考，非交易指令。
```
Forbidden content hits: 0

## 15:00 post_close_1500

Formatter: `scripts.orchestrator.approved_pre_open_delivery.build_line_message -> app.reports.multi_window_formatter.line_notification_text`

```text
【Stock AI】15:00 盤後檢討已更新
單日檢討、7 天滾動檢討、樣本累積與校準狀態請看 Dashboard。
Dashboard：
http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html
僅供研究參考，非交易指令。
```
Forbidden content hits: 0
