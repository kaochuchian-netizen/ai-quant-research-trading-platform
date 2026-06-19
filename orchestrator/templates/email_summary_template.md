# AI Orchestrator 階段成果通知

Subject: [AI Orchestrator] <task_id> 完成：<task_name>

## 任務資訊

- Task ID：<task_id>
- Task 名稱：<task_name>
- 完成時間：<completed_at>
- Commit hash：<commit_hash_or_not_created>
- Commit message：<commit_message_or_not_applicable>

## 變更檔案

- <path>

## 本階段完成內容

- <summary>

## 驗證結果

- <command_or_check>: <passed_failed_or_skipped>

## 安全檢查

- Production side effect：none / detected / blocked
- Forbidden path changes：none / list paths
- DB / migration / cron / LINE / formal pipeline：none / detected / blocked
- Credentials / environment files：none / detected / blocked
- Blocked reason：<reason_or_none>

## 下一個建議任務

- Task ID：<next_task_id>
- Task 名稱：<next_task_name>

## 你的決策

目前這封信是純文字 email，尚未啟用 approval endpoint 或 email reply parser，所以不會出現真正可點擊並自動觸發流程的按鈕。

請直接回覆以下其中一個指令，由後續 Orchestrator / ChatGPT 流程判讀：

```text
continue
```

代表：✅ 同意繼續進行下一個已定義的低風險工作。

```text
pause
```

代表：⏸️ 同意目前成果，但下一個工作先暫緩。

## 權限邊界

上述決策只代表是否繼續下一個已定義的低風險 Orchestrator 工作，不代表授權以下高風險操作：

- migration
- LINE 正式推播
- cron 修改
- production DB 修改
- formal pipeline 執行
- credentials 修改
- protected branch merge
- Google Sheet 修改
- 自動下單或交易

## 備註

這是階段成果通知模板。真正的一鍵 approval button 需要後續實作 signed approval endpoint 或 email reply parser 後才會啟用。
