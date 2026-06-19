# Phase C-6 VM-side Stage Validation Runner 設計

本文件定義 Phase C-6 的 VM-side stage validation runner 規格。目標是把目前人工在 VM 執行的 `git pull`、安全驗證、階段通知，整理成可審計、可逐步自動化的標準流程。

Phase C-6 不建立 approval endpoint，不執行 production pipeline，不自動下單，不修改 credentials。本階段只設計 VM 端低風險驗證與階段通知流程。

## 1. 背景

目前 Phase C 已具備：

- read-only validation snapshot：`scripts/orchestrator/collect_validation_snapshot.py`
- notice renderer：`scripts/orchestrator/render_notice_from_template.py`
- SMTP notifier：`scripts/orchestrator/notify_stage_report.py`
- one-shot stage notification runner：`scripts/orchestrator/run_stage_notification.py`

目前限制是：

- GitHub connector 可直接完成低風險 commit。
- VM 本機仍需要人工或 Codex 執行 `git pull` 與驗證。
- 驗證完成後，還需要人工觸發 stage notification。

Phase C-6 的目標是補上 VM 端標準化流程，讓低風險任務完成後，可以用單一安全入口完成：

```text
git pull
-> scoped validation
-> safety snapshot
-> notice render
-> optional email send
```

## 2. Phase C-6 目標

Phase C-6 的目標如下：

1. 建立 VM-side stage task state 格式。
2. 建立低風險 validation runner 規格。
3. 允許 runner 根據 task state 執行明確列出的安全 validation commands。
4. 預設不寄信，只有加 `--send` 才寄信。
5. 所有 output 預設寫入 `/tmp` 或 task state 指定的非正式輸出位置。
6. 保留 production safety gate。
7. 讓階段成果可由 email summary 彙整，使用者只需要看信決定 continue / pause。

## 3. 明確非目標

Phase C-6 不做以下事項：

- 不建立 approval endpoint。
- 不解析 email reply。
- 不自動執行 Codex 任務。
- 不執行 `python3 main.py`。
- 不執行 formal pipeline。
- 不執行正式回測。
- 不執行 migration。
- 不修改 DB。
- 不修改 cron。
- 不寄 LINE。
- 不修改 Google Sheet。
- 不讀取或輸出 SMTP 密碼。
- 不把 `.env` 或 credentials 寫入 repo。
- 不執行自動下單或交易。

## 4. 建議新增 script

建議下一步新增：

```text
scripts/orchestrator/run_vm_stage_validation.py
```

此 script 只負責 VM 端 stage validation orchestration，不負責 production execution。

建議 CLI：

```bash
python3 scripts/orchestrator/run_vm_stage_validation.py \
  --task-state orchestrator/tasks/phase_c6_task_state.json \
  --env-file ~/.config/stock-ai-orchestrator/mail.env \
  --send
```

預設行為：

- 不寄信。
- 不執行任何 task state 未明列的 validation command。
- 不接受任意 shell string。
- 只執行 allowlist command type。
- 所有 subprocess 使用 list args，不使用 `shell=True`。

## 5. Task State 規格擴充

Phase C-6 task state 應保留既有欄位，並新增 VM validation 區塊。

建議欄位：

```json
{
  "vm_validation": {
    "enabled": true,
    "sync": {
      "git_pull_allowed": true,
      "expected_branch": "main",
      "require_clean_before_pull": true
    },
    "commands": [
      {
        "id": "py_compile_strategy_ranking",
        "type": "py_compile",
        "args": ["analysis/strategy_ranking_engine.py"],
        "required": true
      },
      {
        "id": "inline_console_validation",
        "type": "python_inline",
        "script_path": "orchestrator/validation_snippets/strategy_ranking_console_check.py",
        "required": true
      }
    ],
    "outputs": {
      "validation_result_path": "/tmp/stock_ai_orchestrator_vm_validation.json",
      "notice_output_path": "/tmp/stock_ai_orchestrator_notice.md"
    }
  }
}
```

## 6. Validation Command Allowlist

Phase C-6 runner 不應接受任意 shell command。建議只允許以下 command type：

| type | 行為 | 風險等級 |
|---|---|---|
| `py_compile` | `python3 -m py_compile <file>` | 低 |
| `python_script_readonly` | 執行明確標記 readonly 的驗證 script | 中低 |
| `python_inline_file` | 執行 repo 內固定 validation snippet | 中低 |
| `collect_snapshot` | 呼叫 `collect_validation_snapshot.py` | 低 |

禁止 command type：

- shell raw command
- `main.py`
- migration
- formal pipeline
- backtest formal run
- DB writer
- LINE sender
- cron editor
- credential writer
- order execution

## 7. Safety Gate

runner 在執行前必須檢查：

1. 目前 branch 是否為 task state 指定 branch。
2. `git status --short` 是否 clean。
3. task state 是否明確列出 expected files。
4. task state 是否列出 forbidden files。
5. validation commands 是否全部屬於 allowlist。
6. 是否有任何 command 指向 forbidden path。
7. 是否有 command 會執行 production side effect。

若任一檢查失敗，runner 應：

- 停止後續 command。
- 不寄正式成功信。
- 輸出 blocked summary。
- 可選擇寄出 blocked notice，但 subject 必須標明 blocked。

## 8. Git Pull 策略

`git pull` 屬於 VM 同步操作，允許在低風險條件下執行，但必須受控。

允許條件：

- task state 設定 `git_pull_allowed=true`。
- pull 前 working tree clean。
- branch 等於 expected branch。
- 不存在 untracked files。

禁止條件：

- working tree dirty。
- 有 untracked files。
- branch 不是 expected branch。
- pull 可能造成 merge conflict。

若 `git pull` 失敗，runner 應停止並回報 blocked。

## 9. Email Notification 行為

Phase C-6 runner 可以串接既有：

```text
scripts/orchestrator/run_stage_notification.py
```

規則：

- 預設不寄信。
- 只有 runner 收到 `--send` 才傳遞 `--send`。
- `--env-file` 只傳遞路徑，不讀取、不列印內容。
- 信件內容應包含 validation summary、git status、commit hash、blocked reason 或 next task。
- 若 task state 是範例檔，不應寄正式成功信。

## 10. 建議執行流程

```text
load task state
-> validate task state schema
-> check branch / clean tree
-> optional git pull
-> run allowlisted validation commands
-> collect validation snapshot
-> render notice
-> preview or send email
-> write final VM validation result to /tmp
```

## 11. 完成條件

Phase C-6 完成條件：

- 有一個 VM-side validation runner。
- runner 支援 task-state 驅動。
- runner 預設不寄信。
- runner 只允許 allowlist validation command。
- runner 不使用 `shell=True`。
- runner 可安全執行 `git pull` 前置檢查。
- runner 可產生 `/tmp` validation result。
- runner 可串接 stage notification runner。
- 驗證過程不碰 production side effect。

## 12. 下一步 Task 建議

建議下一個 implementation task：

```text
Phase C-6-1：新增 VM-side validation runner skeleton
```

範圍：

- 新增 `scripts/orchestrator/run_vm_stage_validation.py`
- 只支援 `py_compile` command type
- 支援 clean tree / branch check
- 支援 dry-run summary
- 不執行 git pull
- 不寄信

第二步再擴充：

```text
Phase C-6-2：加入受控 git pull 與 stage notification 串接
```
