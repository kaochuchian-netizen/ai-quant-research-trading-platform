# AI DevOps Orchestrator 三方協作設計

## 1. 角色定位

AI DevOps Orchestrator 是第四方協作角色，負責在 ChatGPT、SSH terminal、SSH 上的 Codex 之間搬運任務、整理輸出、同步狀態與提示下一步。它不是 production 自動執行器，也不取代人工決策。

各角色分工如下：

- ChatGPT：負責策略規劃、Task 定義、review、風險判斷。
- SSH terminal：負責提供實際執行環境，包含檔案狀態、驗證指令、Git 狀態與操作結果。
- Codex：負責依 Task 進行程式修改、文件修改、局部驗證與變更回報。
- AI DevOps Orchestrator：負責任務搬運、prompt relay、輸出整理、狀態同步、下一步提示與 review summary 草稿產生。

Orchestrator 的定位是協作輔助層，主要降低人工操作成本與溝通遺漏，不應直接擁有高風險 production 操作權。

## 2. 核心目標

- 降低人工複製貼上成本。
- 減少漏貼、貼錯、漏驗證。
- 保留人工決策權。
- 不讓 AI 自動執行高風險 production 動作。
- 讓 ChatGPT、terminal、Codex 三方狀態更容易對齊。
- 讓每個 Task 的輸入、輸出、驗證與風險記錄更容易追蹤。

## 3. 初期建議模式

初期應採用 Human-in-the-loop 模式，由人類保留關鍵決策與 approval gate。

建議初期只做半自動協作：

- 半自動 prompt relay：將 ChatGPT 產出的 Task 寫入 prompt file，並協助貼給 Codex。
- 半自動 output summarizer：收集 Codex 回報、terminal 輸出、git status 與 git diff，整理成 review summary 草稿。
- 半自動狀態同步：將目前進度、驗證結果、風險與下一步建議整理給 ChatGPT 與使用者。

初期不建議做全自動 autonomous coding loop。Orchestrator 不應自行連續產生任務、執行修改、驗證、修正、commit、push 或觸發 production 流程。

## 4. 允許自動化的行為

Orchestrator 可自動化低風險、可觀察、可回溯的協作行為：

- 讀取 prompt file。
- 將 prompt 貼給 Codex。
- 收集 Codex 回報。
- 收集 terminal 輸出。
- 整理 `git diff`。
- 整理 `git status`。
- 產生 review summary 草稿。
- 產生驗證結果摘要。
- 產生下一步建議草稿。
- 保存 Task 執行紀錄到 logs。

這些行為應以輔助閱讀、整理與搬運為主，不應包含 production side effect。

## 5. 禁止自動化的行為

Orchestrator 不得自動執行下列高風險動作：

- 不自動執行 `python3 main.py`。
- 不自動執行正式 pipeline。
- 不自動發 LINE。
- 不自動執行 migration。
- 不自動改 cron。
- 不自動 commit / push。
- 不自動啟用正式策略。
- 不自動修改 production DB。
- 不自動修改 `.env`、credentials、tokens、API keys 或其他 secrets。
- 不自動修改 Google Sheet 設定。
- 不自動修改 GitHub remote。
- 不自動刪除歷史 CSV、SQLite、回測輸出資料或正式資料檔。

若 Task 需要上述任何動作，Orchestrator 只能提示需要人工確認，並等待明確 approval。

## 6. 建議目錄結構

建議先以簡單、可人工檢查的目錄結構開始：

```text
prompts/
  tasks/
  reviews/

logs/
  orchestrator/
  codex/
  terminal/

scripts/
  orchestrator/

docs/
  ai_devops_orchestrator_design.md
```

目錄用途：

- `prompts/tasks/`：保存 ChatGPT 產生的 Task prompt。
- `prompts/reviews/`：保存 review prompt 或 review summary 草稿。
- `logs/orchestrator/`：保存 Orchestrator 狀態同步與摘要。
- `logs/codex/`：保存 Codex 回報或轉錄。
- `logs/terminal/`：保存 terminal 指令輸出摘要。
- `scripts/orchestrator/`：未來若需要工具化，可放置 Orchestrator 輔助腳本。
- `docs/`：保存架構設計、流程規範、安全規則與操作 runbook。

初期可以先建立文件與人工流程，不必立即新增 scripts。

## 7. 建議互動流程

建議互動流程如下：

```text
ChatGPT 產生 Task
  -> Orchestrator 寫入 prompt file
  -> Orchestrator 貼給 Codex
  -> Codex 修改或回報
  -> Orchestrator 收集 diff/status/output
  -> ChatGPT review
  -> 人工確認 commit/push
```

更細的工作步驟：

1. ChatGPT 依目前專案狀態產生明確 Task，包含目標、限制、驗證方式與完成回報格式。
2. Orchestrator 將 Task 寫入 prompt file，保留可追溯紀錄。
3. Orchestrator 將 prompt 貼給 SSH 上的 Codex。
4. Codex 依 Task 進行必要修改或回報無法修改的原因。
5. Orchestrator 收集 Codex 回報、terminal 輸出、`git status --short`、`git diff --stat` 與必要 diff 摘要。
6. Orchestrator 產生 review summary 草稿，交由 ChatGPT review。
7. ChatGPT 進行風險判斷與 review，必要時產生修正 Task。
8. 人工確認是否 commit / push。

## 8. 安全閘門

所有可能造成 production side effect 的動作都必須經過人工確認。

必要 approval gate：

- commit 前人工確認。
- push 前人工確認。
- migration 前人工確認。
- 執行 `python3 main.py` 前人工確認。
- LINE 推播前人工確認。
- cron 修改前人工確認。
- DB 修改前人工確認。
- 啟用正式策略前人工確認。
- 修改 Google Sheet 設定前人工確認。
- 修改 production `.env` 或 credentials 前人工確認。

Orchestrator 應在摘要中明確標示：

- 本次是否有 production side effect。
- 本次是否修改程式。
- 本次是否修改 DB。
- 本次是否修改 shell script。
- 本次是否需要人工 approval。
- 下一步建議是否包含高風險操作。

## 9. 未來擴充方向

未來可逐步擴充下列能力：

- tmux session 管理：協助追蹤 ChatGPT、terminal、Codex 對應 session。
- 自動產生驗證 checklist：依修改檔案與模組類型建議安全驗證指令。
- 自動比對 docs 與 code 狀態：提醒文件與實作不一致處。
- 自動產生 task summary：整理 Task 目標、變更、驗證、風險與後續動作。
- 自動產生 review prompt：將 diff、狀態與風險整理成適合 ChatGPT review 的格式。
- 自動追蹤未完成事項：保存 follow-up items 與 blocked reason。
- 自動檢查禁止動作關鍵字：例如 `main.py`、LINE、cron、migration、production DB。

即使未來擴充自動化能力，仍應保留人工 approval gate。Orchestrator 的核心原則是提升協作品質與降低操作摩擦，而不是取代人類對 production 風險的判斷。
