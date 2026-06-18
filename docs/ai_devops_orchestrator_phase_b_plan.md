# AI DevOps Orchestrator Phase B 半自動化骨架設計

本文件設計 Phase B 的 tmux + shell script 半自動化協作骨架。Phase B 的重點是降低 ChatGPT、SSH terminal、SSH 上的 Codex、AI DevOps Orchestrator 之間的操作摩擦，讓 prompt、輸出、diff、status 與 review bundle 更容易追溯。

本 Task 只新增設計文件，不新增 script、不建立目錄、不修改程式、不執行自動化。

## 1. Phase B 目標

Phase B 的核心目標如下：

- 降低 ChatGPT / SSH / Codex 之間的複製貼上成本。
- 減少漏貼、貼錯、漏驗證。
- 保留人工 approval gate。
- 不建立 autonomous coding loop。
- 不自動執行 production side effect。
- 讓每個 Task 的 prompt、輸出、diff、status 與 review summary 更容易追溯。

Phase B 應讓人類更容易掌握目前任務狀態，而不是讓系統自行連續規劃、修改、驗證、修正、commit 或 push。

## 2. Phase B 定位

Phase B 是半自動化協作工具層，定位如下：

- 是 ChatGPT、SSH terminal、Codex 與 Orchestrator 之間的協作輔助層。
- 不是 production 自動執行器。
- 不是自動 coding agent loop。
- 不是自動 approval 系統。
- 只協助搬運 prompt、整理輸出、收集狀態、提示下一步。
- 所有高風險操作仍需人工確認。

Phase B 的設計原則是 read-first、low-risk、human-in-the-loop。任何可能造成 production side effect 的操作，都只能被標示為「需要人工確認」，不得由 Orchestrator 或 script 自動批准或自動執行。

## 3. 建議目錄結構

以下是建議目錄結構。本文件只做設計，不建立這些目錄。

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
```

各目錄用途如下：

- `prompts/tasks/`：保存 ChatGPT 或 Orchestrator 產生、準備交給 Codex 的 Task prompt。每個 Task 應保留原始需求、限制、驗證方式與完成回報格式。
- `prompts/reviews/`：保存準備交給 ChatGPT review 的 prompt、review 問題、review checklist 或人工確認提示。
- `logs/orchestrator/`：保存 Orchestrator 整理出的狀態摘要、review bundle、下一步提示與需要人工確認的紀錄。
- `logs/codex/`：保存 Codex 回報、輸出轉錄、執行摘要與修改後的完成回報。
- `logs/terminal/`：保存 SSH terminal 中安全指令的輸出摘要，例如 `git status --short`、`git diff --stat` 或編譯驗證結果。
- `scripts/orchestrator/`：未來放置 Orchestrator 輔助 shell script。初期 script 應以 `echo`、`cat` 與 read-only collection 為主。

## 4. 初期建議檔案

以下是初期建議檔案。本文件只做設計，不建立這些檔案。

### `prompts/tasks/next_codex_task.md`

- 用途：保存下一個要交給 Codex 的 Task prompt。
- 來源：ChatGPT 產生，或由人工 / Orchestrator 從 ChatGPT 輸出整理後寫入。
- 內容格式：
  - Task 標題。
  - 目標。
  - 修改範圍。
  - 明確限制。
  - 驗證方式。
  - 完成回報格式。

### `prompts/reviews/last_review_prompt.md`

- 用途：保存最近一次要交給 ChatGPT 的 review prompt。
- 來源：Orchestrator 根據 Codex 回報、diff、status 與驗證結果整理。
- 內容格式：
  - Task 背景。
  - 本次變更摘要。
  - 需要 review 的檔案或 diff 摘要。
  - 驗證結果。
  - 風險與待確認事項。
  - 希望 ChatGPT review 的重點。

### `logs/codex/last_codex_output.log`

- 用途：保存最近一次 Codex 的輸出或完成回報。
- 來源：從 SSH 上的 Codex session 複製、tmux capture，或未來由安全 capture script 取得。
- 內容格式：
  - Codex 回報原文或摘要。
  - 修改檔案列表。
  - 驗證結果。
  - 無法完成或需人工確認的事項。

### `logs/terminal/last_terminal_output.log`

- 用途：保存最近一次 SSH terminal 安全指令輸出。
- 來源：人工複製或 read-only capture script。
- 內容格式：
  - 執行時間。
  - 指令名稱。
  - 指令輸出。
  - exit code。
  - 是否涉及 production side effect。

### `logs/orchestrator/last_review_bundle.md`

- 用途：保存最近一次 Orchestrator 產生的 review bundle，供 ChatGPT 或人工 review。
- 來源：Orchestrator 從 prompt、Codex 輸出、terminal 輸出、`git status`、`git diff` 與驗證結果整理。
- 內容格式：
  - Task 來源與目標。
  - 修改摘要。
  - `git status --short` 摘要。
  - `git diff --stat` 摘要。
  - 驗證結果。
  - 風險與注意事項。
  - 是否需要人工 approval。
  - 建議下一步。

## 5. 未來 Shell Script 設計

以下 scripts 僅為未來設計，本 Task 不建立任何 script。

- `scripts/orchestrator/send_prompt_to_codex.sh`
- `scripts/orchestrator/capture_git_status.sh`
- `scripts/orchestrator/capture_diff.sh`
- `scripts/orchestrator/collect_review_bundle.sh`
- `scripts/orchestrator/approval_alert.sh`

初期所有 script 都應採取 dry-run / no-op 思維，以 `echo`、`cat` 與 read-only collection 為主。不得自動執行危險命令，不得自動 commit / push，不得自動修改 production DB，不得自動執行 `main.py` 或正式 pipeline。

## 6. 每個 Script 的預期功能

### `scripts/orchestrator/send_prompt_to_codex.sh`

- 功能：讀取 `prompts/tasks/next_codex_task.md`，將 prompt 顯示出來，供人工確認後交給 Codex。後續階段才評估 tmux paste。
- 輸入：
  - `prompts/tasks/next_codex_task.md`
  - 可選 tmux session / pane 名稱。
- 輸出：
  - terminal 顯示的 prompt。
  - 可選的操作摘要。
- 預期使用場景：
  - ChatGPT 已產生 Task，使用者要準備交給 SSH 上的 Codex。
  - Orchestrator 需要避免漏貼或貼錯 Task。
- 禁止做的事：
  - 不自動送出 Enter 執行 Codex。
  - 不自動建立 autonomous coding loop。
  - 不自動修改 prompt。
  - 不自動執行 `python3 main.py`、正式 pipeline、commit 或 push。

### `scripts/orchestrator/capture_git_status.sh`

- 功能：收集目前 repository 的 `git status --short`，輸出到 terminal 或指定 log。
- 輸入：
  - repository 工作目錄。
  - 可選輸出檔，例如 `logs/terminal/last_terminal_output.log`。
- 輸出：
  - `git status --short` 結果。
  - 執行時間與 exit code。
- 預期使用場景：
  - Codex 修改後，Orchestrator 需要快速整理工作區狀態。
  - ChatGPT review 前，需要確認是否只有預期檔案被修改。
- 禁止做的事：
  - 不自動 stage。
  - 不自動 commit。
  - 不自動 reset / checkout。
  - 不自動刪檔。
  - 不自動 push。

### `scripts/orchestrator/capture_diff.sh`

- 功能：收集 `git diff --stat` 與必要的 read-only diff 摘要，供 review bundle 使用。
- 輸入：
  - repository 工作目錄。
  - 可選輸出檔，例如 `logs/orchestrator/last_review_bundle.md` 的暫存片段。
- 輸出：
  - `git diff --stat`。
  - 可選的 `git diff -- <path>` 摘要。
- 預期使用場景：
  - Codex 完成修改後，整理變更範圍。
  - ChatGPT review 前，快速確認是否有非預期修改。
- 禁止做的事：
  - 不自動修改檔案。
  - 不自動套用 patch。
  - 不自動 revert。
  - 不自動 commit / push。
  - 不自動執行測試、回測、migration 或正式 pipeline。

### `scripts/orchestrator/collect_review_bundle.sh`

- 功能：從 prompt、Codex 輸出、terminal 輸出、git status 與 diff 摘要整理 review bundle。
- 輸入：
  - `prompts/tasks/next_codex_task.md`
  - `logs/codex/last_codex_output.log`
  - `logs/terminal/last_terminal_output.log`
  - `git status --short`
  - `git diff --stat`
- 輸出：
  - `logs/orchestrator/last_review_bundle.md`
- 預期使用場景：
  - 準備把本次 Task 的狀態交給 ChatGPT review。
  - 人工需要快速確認本次改了什麼、驗證了什麼、還缺什麼。
- 禁止做的事：
  - 不自動判定 approval 通過。
  - 不自動修正程式。
  - 不自動觸發 Codex 下一輪修改。
  - 不自動 commit / push。
  - 不自動執行 production side effect。

### `scripts/orchestrator/approval_alert.sh`

- 功能：當流程需要人工確認時，提示使用者回到電腦確認。
- 輸入：
  - approval 類型，例如 commit、push、migration、LINE、main.py、cron、DB、production pipeline。
  - Task ID 或 review bundle 路徑。
  - 可選本機提醒方式設定。
- 輸出：
  - terminal 提示。
  - 未來可擴充本機通知或狀態檔。
- 預期使用場景：
  - Orchestrator 發現下一步涉及高風險操作。
  - ChatGPT review 結論需要人工決定是否繼續。
- 禁止做的事：
  - 不自動 approve。
  - 不自動執行需要 approval 的命令。
  - 不自動 commit / push。
  - 不自動改 production DB。
  - 不自動發 LINE、改 cron、跑 migration、執行 `main.py` 或正式 pipeline。

## 7. 人工確認提醒機制 / Approval Alert

Approval Alert 的目的只是提醒「需要人工 approval」，不是執行 approval。

因為 SSH server 是遠端 GCP VM，真正有用的聲音提醒應該優先設計為「本機電腦發聲」或「本機桌面通知」，不是只讓遠端 server beep。若只在遠端 server 發出 bell 或 beep，使用者可能完全聽不到。

初期可以先規劃 alert hook，不實作。未來可考慮：

- local terminal bell。
- macOS desktop notification。
- Windows desktop notification。
- local sound file。
- LINE 通知。
- Telegram 通知。
- email 通知。

設計限制：

- approval alert 只代表「需要人工 approval」。
- approval alert 不得自動執行 approval。
- 任何需要 approval 的操作仍必須由人回到電腦後明確確認。
- 若本機與遠端 SSH session 分離，需在後續設計中明確定義 alert 是由本機端腳本觸發，還是由遠端產生狀態檔後由本機 watcher 偵測。

## 8. 安全限制

Phase B 禁止自動化下列行為：

- 不自動執行 `python3 main.py`。
- 不自動執行正式 pipeline。
- 不自動發 LINE。
- 不自動執行 migration。
- 不自動改 cron。
- 不自動 commit / push。
- 不自動改 DB。
- 不自動刪檔。
- 不自動修改 `.env` / credentials / tokens / API keys。
- 不自動修改 Google Sheet。
- 不自動修改 GitHub remote。
- 不自動啟用正式策略。
- 不自動 approve 任何高風險操作。

若未來新增任何 script，script 內也應明確寫入上述限制，並以 dry-run / no-op 的方式先接受 review。

## 9. 建議操作流程

Phase B 預期互動流程如下：

```text
ChatGPT 產生 Task
  -> 人工或 Orchestrator 寫入 prompts/tasks/next_codex_task.md
  -> script 將 prompt 貼給 Codex
  -> Codex 修改或回報
  -> script 收集 diff / status / output
  -> Orchestrator 產生 review bundle
  -> ChatGPT review
  -> 若需要人工確認，觸發 approval alert
  -> 使用者回到電腦確認
  -> 人工決定 commit / push 或修正 Task
```

可半自動的步驟：

- 將 Task prompt 寫入或讀出 `prompts/tasks/next_codex_task.md`。
- 顯示準備交給 Codex 的 prompt。
- 收集 `git status --short`。
- 收集 `git diff --stat`。
- 收集 Codex output 與 terminal output。
- 產生 review bundle 草稿。
- 偵測下一步是否可能需要人工 approval。
- 發出「需要人工確認」的提示。

必須人工確認的步驟：

- 是否真的把 prompt 送給 Codex 執行。
- 是否接受 Codex 的修改結果。
- 是否執行任何非 read-only 驗證或高風險命令。
- 是否執行 `python3 main.py`、正式 pipeline、migration、LINE、cron、DB 相關操作。
- 是否 commit。
- 是否 push。
- 是否修改 `.env`、credentials、Google Sheet 或 GitHub remote。
- 是否 approve 任何高風險操作。

## 10. Phase B 實作前檢查清單

實作 Phase B 前應確認：

- Git clean。
- 已完成 Phase B 設計文件。
- 明確禁止 production side effect。
- 先建立目錄，再建立只讀 / 收集型 script。
- script 初期只做 `echo` / `cat` / read-only collection。
- alert 初期只做提示，不做 approval。
- commit / push / migration / `main.py` / LINE / cron / DB 相關動作仍維持人工確認。
- 每個 script 都要有 dry-run 或 no-op 思維。
- 每次新增 script 都要先 review 再 commit。

## 11. Phase B 分階段建議

### Phase B-1

- 建立 `prompts/`、`logs/`、`scripts/orchestrator/` 目錄。
- 建立空白 placeholder / README。
- 不建立可執行 script。

### Phase B-2

- 建立 read-only capture scripts。
- capture git status。
- capture diff。
- collect review bundle。

### Phase B-3

- 建立 prompt relay script。
- 初期只 echo prompt，不自動貼到 Codex。
- 後續再評估 tmux paste。

### Phase B-4

- 建立 approval alert hook。
- 先設計本機提醒方式。
- 不自動 approve。

### Phase B-5

- 評估 tmux session 管理。
- 仍保留人工 approval gate。

## 12. 初期不做事項

本階段初期不做：

- 不新增 shell script。
- 不建立目錄。
- 不修改 Python。
- 不修改 DB。
- 不執行 `main.py`。
- 不執行回測。
- 不執行 Codex 外部自動化。
- 不修改 LINE / cron / Google Sheet / `.env`。
- 不自動 commit / push。
