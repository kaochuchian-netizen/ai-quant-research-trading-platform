# AI-DEV-167 Manual Rerun Status Visibility Runbook

## Purpose

AI-DEV-167 adds a visible Dashboard status card for manual single-window reruns. The goal is PM-readable completion feedback: after pressing one of the four rerun buttons, the Dashboard shows whether the request is waiting, running, completed, rejected, or failed.

This runbook does not authorize sending LINE/Email, running the production pipeline directly, using the real PIN in validation, or changing scheduler behavior.

## Where To Look On The Dashboard

Open the four-window Dashboard and find the `手動重跑` section. Immediately below the PIN form is the status card titled:

`手動重跑狀態`

The card shows:

- `目前狀態`
- `批次`
- `模式`
- `任務 ID`
- `送出時間`
- `開始時間`
- `完成時間`
- `LINE 是否觸發`
- `Email 是否觸發`
- `交易/下單是否發生`
- `錯誤/拒絕原因`
- `最後更新時間`

The card is designed for mobile/iPhone reading: short labels, compact values, and a completion summary line.

## Status Meaning

PM-readable mapping:

- `ready`, `idle`, `manual_rerun_disabled`: 尚未執行 / 目前沒有手動重跑任務
- `accepted`, `queued`: 已送出，等待執行
- `running`: 執行中
- `completed`, `success`, `succeeded`: 已完成
- `rejected`: 已拒絕
- `invalid_pin_format`: PIN 格式錯誤
- `unauthorized`, `invalid_pin`, `pin_mismatch`: PIN 錯誤或未授權
- `failed`, `error`: 執行失敗
- unknown or unexpected value: 狀態未知，請檢查 runtime

## How PM Knows A Rerun Is Complete

A rerun is complete when the status card shows a terminal status:

- `重跑已完成`
- `重跑失敗`
- `重跑被拒絕`

For a successful manual rerun, confirm:

- `目前狀態`: 已完成
- `完成時間`: populated
- `LINE 是否觸發`: 否
- `Email 是否觸發`: 否
- `交易/下單是否發生`: 否

## Polling Behavior

After a manual rerun request is submitted, the Dashboard immediately displays `已送出 / 執行中` style feedback and polls:

`GET /stock-ai-dashboard/api/manual-rerun/status`

Polling interval:

`4 seconds`

Polling stops when a terminal status appears:

- completed / success / succeeded
- failed / error
- rejected
- invalid_pin_format
- unauthorized / invalid_pin / pin_mismatch
- manual_rerun_disabled

## Manual Refresh Button

Use:

`重新整理重跑狀態`

This button only fetches `/status`. It does not trigger a rerun, does not submit a PIN, and does not send LINE/Email.

## Terminal Verification

From GCP, status can be inspected without using a PIN:

```bash
curl -sS http://35.201.242.167/stock-ai-dashboard/api/manual-rerun/status | python3 -m json.tool
```

Direct bridge status can also be inspected:

```bash
curl -sS http://172.19.0.1:18080/stock-ai-dashboard/api/manual-rerun/status | python3 -m json.tool
```

Completion criteria from terminal:

- terminal `status` value
- `finished_at` populated for completed jobs
- `line_attempted=false`
- `email_attempted=false`
- `trading_or_order_executed=false` or absent/false by contract
- no rerun process remains running

Process check:

```bash
ps -ef | grep -E 'run_stock_analysis.sh|approved_pre_open_delivery.py|scripts/run_pipeline.py|manual_rerun_single_window.py' | grep -v grep || true
```

## Safe Rejection Tests

These are allowed for validation and do not use the real PIN.

Invalid PIN format:

```bash
curl -sS -X POST http://35.201.242.167/stock-ai-dashboard/api/manual-rerun \
  -H 'Content-Type: application/json' \
  -d '{"window":"intraday_1305","mode":"dashboard_refresh_only","pin":"abc123","confirm_single_window_only":true}' \
  | python3 -m json.tool
```

Missing confirmation:

```bash
curl -sS -X POST http://35.201.242.167/stock-ai-dashboard/api/manual-rerun \
  -H 'Content-Type: application/json' \
  -d '{"window":"intraday_1305","mode":"dashboard_refresh_only","pin":"abc123"}' \
  | python3 -m json.tool
```

Expected: HTTP 403 JSON rejection, no delivery process, no LINE, no Email, no DB write, no trading/order action.

## Do Not Use The Real PIN In Validation

The real 6-digit PIN is only for operator UI use. It must not be pasted into ChatGPT, Codex, GitHub, docs, logs, artifacts, or validation commands.

## Safety Boundaries

AI-DEV-167 is UI/status-layer only. It does not change runtime security behavior, scheduler, nginx/systemd/firewall, production rating/action/confidence/weight logic, forecast formula, DB, or notification delivery behavior.
