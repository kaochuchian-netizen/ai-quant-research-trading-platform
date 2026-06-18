# Pipeline Overview

本文件說明目前 pipeline 架構、狀態、runner 規則與安全原則。

實際 smoke test 指令與預期錯誤請見 `docs/pipeline_smoke_tests.md`。

## 目前 pipeline 架構總覽

目前 pipeline 相關檔案如下：

- `app/pipelines/context.py`
  - 建立 pipeline 執行 context。
  - 目前 context 包含 `pipeline_type`、`pipeline_run_id`、`run_date`、`run_time`、`created_at`。
- `app/pipelines/pre_open_pipeline.py`
  - 盤前分析 pipeline。
  - 接上既有盤前分析流程，包含股票清單、historical CSV、技術面、ADR、新聞面、籌碼面、總分、報告、SQLite、LINE 與回測自動補值相關流程。
- `app/pipelines/intraday_pipeline.py`
  - 盤中 pipeline 入口。
  - 目前僅建立 pipeline context 並輸出基本資訊。
- `app/pipelines/pre_close_pipeline.py`
  - 盤前收盤前 pipeline 入口。
  - 目前僅建立 pipeline context 並輸出基本資訊。
- `app/pipelines/post_close_pipeline.py`
  - 收盤後 pipeline 入口。
  - 目前僅建立 pipeline context 並輸出基本資訊。
- `app/pipelines/runner.py`
  - 統一管理支援的 pipeline 清單與 dispatch 規則。
  - 負責擋下目前不允許的正式執行模式與不支援的參數組合。
- `scripts/run_pipeline.py`
  - CLI 入口。
  - 從 `app.pipelines.runner` 匯入 `SUPPORTED_PIPELINES` 與 `run_pipeline`。

## 每個 pipeline 目前狀態

### pre_open

- 已接完整既有盤前流程。
- dry-run 已跳過 SQLite 初始化、historical CSV 更新、SQLite 寫入、LINE 推播、回測自動補值。
- 從 runner 執行時目前只允許 dry-run。
- 支援 `--limit` 測試參數。

### intraday

- 目前為空殼。
- 僅建立 pipeline context 並輸出基本資訊。
- 尚未接分析、SQLite、LINE、回測、cron。

### pre_close

- 目前為空殼。
- 僅建立 pipeline context 並輸出基本資訊。
- 尚未接分析、SQLite、LINE、回測、cron。

### post_close

- 目前為空殼。
- 僅建立 pipeline context 並輸出基本資訊。
- 尚未接分析、SQLite、LINE、回測、cron。

## runner 規則

- `SUPPORTED_PIPELINES` 統一管理支援清單。
- `scripts/run_pipeline.py` 從 runner 匯入 `SUPPORTED_PIPELINES`。
- `pre_open` 非 dry-run 會被 `ValueError` 擋下。
- `limit` 目前只支援 `pre_open`，其他 pipeline 使用 `limit` 會被 `ValueError` 擋下。

## 安全原則

- 不直接執行 `python3 main.py`。
- 不在 smoke test 中發 LINE。
- 不在 dry-run 寫 SQLite。
- 不在 dry-run 更新 historical CSV。
- 不在 dry-run 跑回測自動補值。
- 正式 cron 尚未切換到 `scripts/run_pipeline.py`。

## 與 pipeline_smoke_tests.md 的關係

- `docs/pipeline_overview.md` 說明架構與規則。
- `docs/pipeline_smoke_tests.md` 說明實際驗證指令。
