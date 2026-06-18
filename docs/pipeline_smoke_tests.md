# Pipeline Smoke Tests

本文件記錄 pipeline runner 目前可安全執行的 smoke test 指令、預期防呆錯誤，以及驗證順序。

## 安全 dry-run 指令

以下四個 pipeline 目前都有一致的 runner 入口與安全執行骨架。`pre_open` 已接既有完整盤前流程，dry-run 安全且支援 `--limit`；`intraday`、`pre_close`、`post_close` 目前僅輸出 context summary，無副作用。

以下指令目前可安全執行，且應維持 dry-run 行為：

```bash
python3 scripts/run_pipeline.py pre_open --dry-run --limit 1
python3 scripts/run_pipeline.py pre_open --dry-run --limit 2
python3 scripts/run_pipeline.py intraday --dry-run
python3 scripts/run_pipeline.py pre_close --dry-run
python3 scripts/run_pipeline.py post_close --dry-run
```

## pre_open 正式模式防呆

以下指令會被 runner 防呆擋下，這是正確行為：

```bash
python3 scripts/run_pipeline.py pre_open
```

預期錯誤：

```text
ValueError: pre_open pipeline is only allowed with dry_run=True
```

## limit 支援範圍

`limit` 目前只支援 `pre_open` pipeline。以下指令會被 runner 防呆擋下，這是正確行為：

```bash
python3 scripts/run_pipeline.py intraday --dry-run --limit 1
python3 scripts/run_pipeline.py pre_close --dry-run --limit 1
python3 scripts/run_pipeline.py post_close --dry-run --limit 1
```

預期錯誤：

```text
ValueError: limit is only supported for pre_open pipeline
```

## 安全原則

- 不直接執行 `python3 main.py`。
- `pre_open` 正式模式目前不能從 runner 執行。
- `pre_open` dry-run 已接既有完整盤前流程，但會跳過副作用。
- `intraday`、`pre_close`、`post_close` 僅輸出 context summary，無副作用。
- dry-run 不應寫 SQLite。
- dry-run 不應發 LINE。
- dry-run 不應跑回測自動補值。
- dry-run 不應更新 historical CSV。

## 建議驗證順序

1. 先執行 `py_compile`，確認 runner 與 pipeline 檔案語法正確。
2. 再執行 `pre_open --dry-run --limit 1`，確認有限股票數的盤前 dry-run 可跑。
3. 再執行其他安全骨架 pipeline dry-run，確認 runner dispatch 與 context summary 輸出正常。
4. 最後驗證防呆錯誤，確認正式 `pre_open` 與非 `pre_open` 的 `limit` 都會被擋下。

建議驗證指令：

```bash
python3 -m py_compile app/pipelines/pre_open_pipeline.py app/pipelines/runner.py scripts/run_pipeline.py
cat docs/pipeline_smoke_tests.md
```

預期結果：

- `py_compile` 通過。
- 文件內容清楚列出安全 dry-run、防呆錯誤、安全原則與驗證順序。
- 不執行任何會發 LINE 的流程。
