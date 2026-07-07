# AI-DEV-156 Review Card PM-Readable Rendering Cleanup V1

AI-DEV-156 cleans up the Dashboard review card so PM and investment-review readers see decision language rather than raw artifact values. It does not change data sources, forecast formulas, review schemas, snapshot accumulation, calibration gates, delivery behavior, or production scoring logic.

## Problem Statement

The review card was contract-correct but still exposed raw engineering terms such as `generated_at`, `data_quality`, `hit`, `correct`, and `insufficient_data`. It also could show a hit status while the error detail line said only `資料待接`, which made the card feel contradictory.

## Raw Key Mapping

- `generated_at` -> 產生時間
- `data_quality` -> 資料品質摘要
- `insufficient_data` -> 資料不足
- `correct` -> 正確
- `incorrect` -> 錯誤
- `hit` -> 命中
- `partial_hit` -> 部分命中
- `miss` -> 未命中
- `reviewable_single_day` -> 單日資料可檢討
- single-day deterministic evaluation -> 單日 deterministic baseline 評估

## Review Card Structure

The card is split into two sections: 單日檢討 and 7 天滾動檢討. Seven-day insufficiency is explicitly shown as a data accumulation requirement, not as a broken field.

## Error Detail Consistency

If high-low error details exist, the UI shows high/low absolute and percentage errors. If hit status exists but the error object is missing, the UI says: 命中狀態可用；誤差明細欄位待接。 If both are missing, it shows 資料待接. No fake error values are generated.

## Regression Guard

The validator protects AI-DEV-150 through AI-DEV-155 behavior: decision-state semantics, formal prediction/review binding, deterministic_baseline_v1 labels, backtest readability, calibration gate, sample count, and snapshot accumulation.

## Forbidden Changes

No secrets, DB writes, scheduler changes, LINE/Email sending, production pipeline, `python3 main.py`, trading/order action, deterministic_baseline_v1 formula mutation, production scoring mutation, formal artifact semantic mutation, snapshot semantic mutation, calibration gate mutation, or delivery behavior change.
