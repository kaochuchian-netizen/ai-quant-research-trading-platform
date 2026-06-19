# AI DevOps Orchestrator Phase C 自主協作與 Email Approval 設計

本文件設計 Phase C 的 autonomous-assisted workflow，讓 AI DevOps Orchestrator 可以在低風險範圍內自動推進 Codex 任務、收集結果、執行基本驗證、在安全條件下自動 commit，並於每個重要階段完成後寄出 email summary，由使用者透過 email approval action 決定是否繼續下一階段或暫緩。

本 Task 只新增設計文件，不新增 script、不建立 endpoint、不修改程式、不寄 email。

## 1. Phase C 目標

Phase C 的核心目標如下：

- 減少使用者在 ChatGPT / SSH / Codex 之間反覆貼 prompt 的時間。
- 讓 Orchestrator 可以自動完成中間協作流程。
- 允許在安全條件下自動 commit。
- 每個重要階段完成後寄出 email summary。
- 下一階段是否繼續由使用者透過 email approval 決定。
- 保留 production safety gate。

Phase C 不是把整個 production decision 交給 AI，而是讓低風險、可驗證、可回溯的中間流程自動化，並把關鍵 approval 明確保留給使用者。

## 2. Phase C 定位

Phase C 是 autonomous-assisted workflow，定位如下：

- 是輔助式自主協作流程。
- 不是無限制 autonomous production agent。
- 可以自動完成 research / docs / low-risk code task 的中間流程。
- 可以自動收集 Codex 結果、Git 狀態、diff 與 validation output。
- 可以在明確安全條件下自動 commit。
- 不可自動執行 production side effect。
- 不可自動 approve migration、LINE、cron、DB、正式 pipeline、自動下單。

Phase C 的重點是「低風險任務的自動推進」與「高風險操作的明確阻擋」。只要 Task 涉及 production side effect，Orchestrator 就只能產生摘要與提醒，不得自行批准或執行。

## 3. 建議工作流

建議 Phase C 工作流如下：

```text
ChatGPT 或 task queue 產生 Task
  -> Orchestrator 寫入 prompt
  -> Orchestrator 交給 Codex
  -> Codex 修改
  -> Orchestrator 收集 diff / status / validation output
  -> Orchestrator 判斷是否通過基本驗證
  -> 若通過，Orchestrator 自動 commit
  -> Orchestrator 寄 email 階段成果報告
  -> email 內提供兩個 action：
       1. 同意繼續進行下一個工作
       2. 同意，但下一個工作先暫緩
  -> Orchestrator 等待 approval state
  -> 若 continue，進入下一 Task
  -> 若 pause，停止自動推進並保留狀態
```

建議細部步驟：

1. ChatGPT 或 task queue 產生明確 Task，包含 Task ID、目標、修改範圍、禁止事項、驗證方式與完成回報格式。
2. Orchestrator 將 Task 寫入 prompt 紀錄，保留可追溯輸入。
3. Orchestrator 將 prompt 交給 Codex 執行。
4. Codex 依 Task 完成文件或低風險程式修改，並回報修改檔案、驗證結果與風險。
5. Orchestrator 收集 `git status --short`、`git diff --stat`、必要 diff 摘要、Codex output 與 validation output。
6. Orchestrator 依 Task scope 與安全規則判斷是否通過基本驗證。
7. 若通過且符合自動 commit 條件，Orchestrator 保存 review bundle 後自動 commit。
8. Orchestrator 在 commit 後寄出 email summary。
9. 使用者透過 email 內 approval action 選擇 continue 或 pause。
10. Orchestrator 只在 approval state 為 `approved_continue` 時進入下一個已定義 Task。
11. 若 approval state 為 `approved_pause`，Orchestrator 停止自動推進並保留目前狀態，等待人工下一步。

## 4. 自動 Commit 規則

### 允許自動 commit 條件

Orchestrator 只有在全部條件都成立時，才可自動 commit：

- Git working tree 只包含本 Task 預期檔案。
- `py_compile` 或 Task 指定驗證指令通過。
- 未修改禁止檔案。
- 未涉及 DB / migration / `.env` / credentials / cron / LINE / production pipeline。
- commit message 由 Task ID 與變更摘要產生。
- commit 前保存 review bundle。
- commit 後寄出 email summary。
- Codex 回報明確，沒有 unresolved risk、blocked reason 或不確定結論。
- diff 大小符合 Task scope，沒有超出任務範圍的重構或行為變更。

建議 commit message 格式：

```text
Task <task_id>: <short change summary>
```

review bundle 應至少包含 Task prompt、Codex output、`git status --short`、`git diff --stat`、validation output、風險檢查結果與 commit 前時間戳。

### 禁止自動 commit 條件

只要符合任一條件，Orchestrator 不得自動 commit：

- 有未預期檔案。
- 有 secret / `.env` / credentials 變更。
- 有 DB / migration / cron / LINE / `main.py` formal run 相關風險。
- 驗證失敗。
- Codex 回報不確定。
- diff 過大或超出 Task scope。
- 有 production pipeline、正式資料、Google Sheet、GitHub remote 或自動下單相關變更。
- 有刪除歷史 CSV、SQLite、回測輸出資料或正式資料檔的風險。
- Git working tree 在 Task 開始前不是 clean，且無法確認差異歸屬。

禁止自動 commit 時，Orchestrator 應產生 blocked summary，說明阻擋原因、目前 diff/status、驗證結果與建議人工處理方式。

## 5. Email 成果報告內容

每封階段 email 應包含：

- Task ID。
- Task 名稱。
- 完成時間。
- commit hash。
- 修改檔案列表。
- 變更摘要。
- 驗證結果。
- 是否有 production side effect。
- 風險檢查結果。
- 下一階段建議工作。
- 兩個 approval action：
  - ✅ 同意繼續進行下一個工作
  - ⏸️ 同意，但下一個工作先暫緩

建議 email 結構：

```text
Subject: [AI Orchestrator] Task <task_id> completed: <task_name>

Task ID:
Task 名稱:
完成時間:
Commit hash:

修改檔案:
- <path>

變更摘要:
- <summary>

驗證結果:
- <command>: passed / failed / skipped

Production side effect:
- none / detected / blocked

風險檢查:
- working tree scope:
- forbidden files:
- DB / migration / cron / LINE:
- credentials / .env:
- production pipeline:

下一階段建議工作:
- <next_task>

Approval actions:
[✅ 同意繼續進行下一個工作]
[⏸️ 同意，但下一個工作先暫緩]
```

若沒有 commit，例如驗證失敗或被安全規則阻擋，commit hash 應顯示 `not_created`，並在風險檢查中說明原因。

## 6. Email Approval Action 設計

本節只設計，不實作 endpoint、不建立 mailbox parser、不寄 email。

### 方式 A：Approval Endpoint

approval endpoint 方式如下：

- email 按鈕連到 signed one-time URL。
- URL 包含 `task_id`、`approval_token`、`action`。
- `action` 可為 `continue` 或 `pause`。
- token 必須一次性。
- token 必須可過期。
- endpoint 只寫入 approval state，不直接執行高風險命令。
- Orchestrator polling approval state 後才進下一步。

建議 URL 欄位：

```text
https://<approval-host>/approval?task_id=<task_id>&action=<continue|pause>&approval_token=<signed_token>
```

endpoint 行為限制：

- 只驗證 token、task_id、action 與過期時間。
- 只寫入 approval state。
- 不直接觸發 Codex。
- 不直接執行 commit / push。
- 不直接執行 migration、LINE、cron、DB、正式 pipeline 或自動下單。
- 不接受任意 shell command。
- 不回傳 secrets、diff 全文或 credentials。

優點：

- 使用者操作清楚，按鈕即可完成 approval。
- token 可一次性與過期，安全性較容易控管。
- state machine 較明確，方便 audit。
- Orchestrator 可以穩定 polling approval state。

缺點：

- 需要建立 endpoint、token 儲存與狀態儲存。
- 需要處理 HTTPS、身份驗證、過期與重放攻擊。
- 需要確保 endpoint 本身不成為 production command trigger。

### 方式 B：Email Reply Fallback

email reply fallback 方式如下：

- 使用者可回信 `continue` 或 `pause`。
- Orchestrator 讀取指定 mailbox 或 label。
- Orchestrator 解析 `task_id` 與 `action`。
- 作為 approval endpoint 不可用時的備援方案。

建議解析規則：

- subject 或 hidden metadata 必須包含 Task ID。
- email body 第一個有效 action 必須是 `continue` 或 `pause`。
- 只接受來自 allowlist 使用者 email。
- 已處理信件必須標記 processed，避免重複套用。
- 無法解析或多重 action 時，進入 `error` 或保留 `waiting_approval`。

優點：

- 不一定需要建立 web endpoint。
- 在行動裝置上回覆 email 容易操作。
- 可作為 endpoint 異常時的備援。

缺點：

- email parsing 容易受 quote、signature、thread history 影響。
- mailbox polling 與權限管理較複雜。
- 重複信、轉寄、thread 混淆與延遲較難處理。
- action audit 與防重放設計通常比 signed URL 困難。

### 初期建議

初期優先採用 approval endpoint，email reply 作為 fallback。原因是 approval endpoint 的 action、token、過期時間與 state transition 較容易定義與稽核；email reply 則適合作為 endpoint 不可用或使用者不方便點擊按鈕時的備援。

## 7. 兩個按鈕文案

email 內兩個按鈕文案如下：

- ✅ 同意繼續進行下一個工作
- ⏸️ 同意，但下一個工作先暫緩

語意說明：

- `continue` 只代表允許進入下一個已定義 Task。
- `pause` 代表目前成果接受，但停止自動推進。
- 兩者都不代表允許 migration、LINE、cron、DB、正式 pipeline 或自動下單。
- 兩者都不代表允許修改 `.env`、credentials、tokens、API keys 或 Google Sheet。
- 兩者都不代表允許 push、merge 到 protected branch 或執行超出 Task scope 的命令。

若下一個 Task 涉及高風險操作，即使使用者按下 continue，Orchestrator 仍必須停在 production safety gate，產生人工確認提示，不得自動執行。

## 8. Approval State 設計

建議 approval state 如下：

### `waiting_approval`

- 代表 email summary 已送出，Orchestrator 正在等待使用者 action。
- 可做：poll approval state、檢查 token 是否過期、顯示目前等待狀態。
- 不可做：進入下一 Task、執行高風險命令、重複 commit、push、merge。

### `approved_continue`

- 代表使用者同意進入下一個已定義 Task。
- 可做：讀取下一個 Task、重新檢查 Task scope 與 safety gate、啟動低風險 Orchestrator 流程。
- 不可做：跳過 safety gate、執行 migration、LINE、cron、DB、正式 pipeline、自動下單、push 或 protected branch merge。

### `approved_pause`

- 代表使用者接受目前成果，但要求暫緩下一個工作。
- 可做：停止自動推進、保存狀態、產生 paused summary。
- 不可做：進入下一 Task、重新觸發 Codex、自動修改檔案、commit、push。

### `expired`

- 代表 approval token 或等待期限已過期。
- 可做：保存 expired 狀態、寄出或產生過期摘要、等待人工重新開啟 approval。
- 不可做：使用過期 approval 繼續流程、重用 token、進入下一 Task。

### `rejected`

- 代表使用者拒絕目前成果或明確要求停止。
- 可做：停止自動推進、保存 rejected reason、產生人工 follow-up 建議。
- 不可做：自動修正、自動 commit、自動 revert、自動 push、自動進入下一 Task。

### `error`

- 代表 approval action 解析錯誤、token 驗證錯誤、state 寫入錯誤或流程不一致。
- 可做：停止自動推進、保存錯誤細節、要求人工檢查。
- 不可做：猜測使用者意圖、套用模糊 action、進入下一 Task、執行任何高風險命令。

## 9. 安全邊界

Phase C 仍禁止自動化下列行為：

- 不自動執行 `python3 main.py`。
- 不自動執行正式 pipeline。
- 不自動發 LINE。
- 不自動執行 migration。
- 不自動改 cron。
- 不自動改 production DB。
- 不自動修改 `.env` / credentials / tokens / API keys。
- 不自動修改 Google Sheet。
- 不自動自動下單。
- 不自動 merge 到 protected branch。
- 不自動執行任何超出 Task scope 的命令。
- 不自動修改 GitHub remote。
- 不自動刪除歷史 CSV、SQLite、回測輸出資料或正式資料檔。
- 不把 email approval action 解讀成 production approval。

Phase C 的 continue approval 只能允許 Orchestrator 進入下一個已定義且通過 safety gate 的 Task。所有 production side effect 仍需要額外、明確、單次的人工作業確認。

## 10. 建議分階段實作

### Phase C-1

- 只建立 task state file 與 review bundle 格式。
- 不寄 email。
- 不自動 commit。

### Phase C-2

- 加入自動 validation collection。
- 仍不自動 commit。

### Phase C-3

- 允許 docs-only task 自動 commit。
- commit 後產生 email 草稿，不寄出。

### Phase C-4

- 允許寄出 email summary。
- 但 approval action 先用手動回報。

### Phase C-5

- 建立 approval endpoint 或 email reply parser。
- 支援 `continue` / `pause`。

### Phase C-6

- 擴大到低風險 code task。
- 仍禁止 production side effect。

## 11. 初期不做事項

Phase C 初期不做：

- 不新增 script。
- 不新增 endpoint。
- 不寄 email。
- 不修改 Python。
- 不修改 DB。
- 不執行 `main.py`。
- 不執行回測。
- 不執行 migration。
- 不改 LINE / cron / Google Sheet / `.env`。
- 不自動 push。
- 不自動 merge。
- 不執行 production side effect。

本文件只是 Phase C 的設計規格。任何後續實作都應拆成小 Task，逐步建立狀態檔、review bundle、validation collection、email draft、email sending、approval endpoint 或 email reply parser，且每一步都必須先經過安全規則與人工 review。
