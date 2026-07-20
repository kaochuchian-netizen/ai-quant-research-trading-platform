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
9. Git commit、push 與 PR／merge 行為依下方「Codex 授權與治理政策」執行；不得直接 push main。

## 開發流程
每次 coding task 請依序執行：
1. 先檢查 git status --short。
2. 先閱讀相關檔案。
3. 簡短說明準備修改什麼。
4. 只修改必要檔案。
5. 執行安全驗證。
6. 顯示 git diff --stat。
7. Commit、push、PR 與 merge 依下方「Codex 授權與治理政策」及 active AI-DEV 任務授權範圍執行。

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

# AI Quant Research & Trading Platform — Codex Authorization Policy

## Default authorization

在正式 GCP repository `~/stock-ai` 內，例行開發工作預先授權，Codex 不應反覆詢問使用者。

以下動作可自動執行：

- 讀取與搜尋 repository 檔案
- 建立與切換 feature branch
- 編輯任務相關 source、tests、validators、docs、schemas、templates、runbooks
- 執行 py_compile、lint、test、validator、inspector
- 執行 controlled no-send 與 temporary-target verification
- 唯讀檢查 production/runtime/archive/generated artifacts
- 執行 git status、diff、log、fetch、pull --ff-only
- 在 feature branch commit
- push feature branch
- 建立與更新 PR
- 等待及檢查 GitHub Actions
- 所有 gates PASS 後，依 active AI-DEV 任務允許範圍 merge
- merge 後同步 main、做 post-merge validation、清理 feature branch
- 輸出 implementation、validation、merge、safety report

不要針對上述例行動作重複要求批准。

## Actions requiring explicit user approval

只有以下行為必須在執行前取得使用者明確批准。

### Trading / orders

- 真實下單
- 修改或取消訂單
- 啟用 order execution
- 將策略結果接到 broker endpoint
- 任何可能產生真實部位或金融義務的操作

### Credentials / secrets

- 讀取、顯示、複製、建立、修改、旋轉或刪除 credentials
- 存取 `.env`
- 存取 API token、password、private key、OAuth token、broker credential、LINE token、Email credential、cloud service account key
- 修改 IAM、SSH key、firewall、secret scope
- 將 secrets 放入 log、commit、artifact、prompt、screenshot 或 report

只讀取環境變數名稱、不讀值，允許自動執行。

### Production Email / LINE delivery

- 寄送真實 Email
- 發送真實 LINE
- 啟用 production-approved delivery
- 修改 recipient
- replay / resend / backfill notification
- 執行會自動觸發正式通知的 production batch

Formatter preview、provenance generation 與 controlled no-send 預先授權。

## Conditional production actions

以下動作只有 active AI-DEV 任務明確授權時才可自動執行；否則需詢問：

- Controlled static publish
- Production pipeline execution
- Scheduler / cron / systemd timer 修改
- Production runtime artifact 修改
- Immutable archive 或 snapshot 修改
- Production backfill
- Infrastructure 或 network configuration 修改

Controlled static publish 若任務已明確允許，且 merge、CI、post-merge、rollback、no-send gates 全數 PASS，則不需再次詢問。

## Existing dirty files

既有 production/runtime/generated dirty files 必須保留。

禁止：

- git reset
- git restore
- git clean
- git stash
- 刪除
- 覆寫
- 加入 implementation commit

只允許 stage 與 commit 本任務相關檔案。

## Git governance

- GitHub main 是 source of truth
- 禁止直接 push main
- 必須走 branch → PR → CI → merge → post-merge validation
- required gates 未 PASS 不得 merge
- natural production verification 尚未完成時，不得宣稱 CLOSED
- 使用 `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`

## Approval behavior

只有以下情況才詢問：

- 屬於上述必須批准類別
- 需求存在實質矛盾
- 技術上無法在目前環境完成
- 必須執行不可逆或破壞性動作
- 繼續會違反 repo governance 或 production safety

需要批准時，只能提出一次整合問題，內容包含：

- exact action
- necessity
- affected environment
- side effects
- rollback

不得把同一操作拆成多個零碎批准問題。

## 完成回報格式
完成修改後請回報：
- 完成狀態
- 修改檔案
- 驗證結果
- Diff 摘要
- 風險與注意事項
- 建議下一步
