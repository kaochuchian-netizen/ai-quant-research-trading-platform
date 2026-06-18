# AGENTS.md — AI Quant Research & Trading Platform

## 回覆語言
除非使用者明確要求英文，所有回覆請使用繁體中文。必要技術名詞可保留英文，例如 Git、Codex、CLI、branch、commit、push、diff、backtest、dashboard、SQLite、cron、LINE。

## 專案概述
本專案是 AI Quant Research & Trading Platform。

主要流程：
Google Sheet 股票清單 -> Shioaji 歷史與行情資料 -> 技術面 / 新聞面 / ADR / 籌碼面分析 -> 總分評級 / 策略回測 / 策略排行榜 -> LINE 推播與未來 Web Dashboard。

目前重點：
1. 台股每日盤前分析
2. 策略訊號回測
3. 策略排行榜
4. 回測結果自動補值
5. 盤前自動回測更新流程
6. 未來擴充盤中分析、收盤分析與個人 Dashboard

## 核心規則
1. 修改任何程式前，必須先閱讀相關檔案目前內容。
2. 優先採用小範圍、高信心、可維護的修改。
3. 不要進行大範圍重寫，除非使用者明確要求。
4. 除非任務明確要求，不要改變既有行為。
5. 不得自行執行會觸發 LINE 推播的指令。
6. 不得自行執行 python3 main.py，除非使用者明確核准。
7. 不得輸出、摘要、修改或顯示 secrets、tokens、API keys、credentials 或 .env 內容。
8. 不得修改 .env、venv、cache、正式資料檔，除非使用者明確要求。
9. 不得自行執行 git commit 或 git push，除非使用者明確要求。

## 開發流程
每次 coding task 請依序執行：
1. 先檢查 git status --short。
2. 先閱讀相關檔案。
3. 簡短說明準備修改什麼。
4. 只修改必要檔案。
5. 執行安全驗證。
6. 顯示 git diff --stat。
7. 最後由使用者決定是否 commit / push。

## 驗證原則
優先使用：
python3 -m py_compile <changed_python_files>

分析與回測模組可執行：
python3 analysis/backtest_engine.py
python3 analysis/strategy_backtest_engine.py
python3 analysis/strategy_ranking_engine.py

除非使用者明確核准，避免執行：
python3 main.py

## 專案決策優先順序
1. 可擴充性
2. 可維護性
3. 可自動化
4. 可回測性
5. 可解釋性
6. 風險控管

## 高風險限制
除非使用者明確要求，不得自行：
1. 發送 LINE 推播
2. 修改 cron 排程
3. 修改 production .env
4. 修改 Google Sheet 設定
5. 修改 GitHub remote
6. 進行資料庫破壞性操作
7. 刪除歷史 CSV、SQLite、回測輸出資料

## 完成回報格式
完成修改後請回報：
- 完成狀態
- 修改檔案
- 驗證結果
- Diff 摘要
- 風險與注意事項
- 建議下一步
