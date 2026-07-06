# AI-DEV-149 Four-Batch Delivery Content Audit & Strategy V2 Coverage Alignment V1

## Purpose
This document aligns the current four-batch delivery model with the broader Strategy V2 0620 expectations while preserving safety boundaries. It is one integrated audit, contract, formatter, dashboard, validation, publish, and closeout task.

## Four-batch mapping
- 07:00 `pre_open_0700`: 台股盤前預測, today high/low, next-day high/low, 1M/3M trend, confidence, rationale, risk notes, 台指期夜盤觀察, 美股盤後摘要狀態.
- 13:05 `intraday_1305`: replaces original 11:30 盤中分析 with current price state, range proximity, volume/chip/ADR/external proxy status, pre-open assumption validity, risk notes.
- 13:35 `pre_close_1335`: runtime key is retained for compatibility, but the user-facing label is `收盤快照 / Close Snapshot`; full prediction review is deferred to 15:00.
- 15:00 `post_close_1500` / `prediction_review_1500`: full daily prediction review, 7-day rolling hit-rate, forecast vs actual, high/low error, direction hit, confidence calibration, factor effectiveness, error reason, next-day improvement.

## Channel differentiation
- LINE: short decision-oriented summary, prediction data status, major risks, Dashboard URL. No long tables or raw logs.
- Email: full report sections defined by the content contract. 07:00 must include all daily prediction fields even if values are missing.
- Dashboard: full data state, freshness, missing/stale reasons, delivery audit summary, debug artifact inventory.

## Prediction fallback
Missing prediction values must remain visible and must use: `資料待接：尚未找到正式 prediction runtime artifact，不產生假預測。` Forecast values must not be fabricated.

## US market and futures mapping
台指期夜盤觀察 and 美股盤後摘要 are shown in the 07:00 batch. 美股預測 and 美股 7-day rolling review remain `美股資料待接：尚未提供美股股票代號或正式 runtime artifact。`

## Safety boundaries
This task does not read secrets, write DB, modify scheduler/cron/systemd/timer, send LINE/Email, run production pipeline, execute `python3 main.py`, trade/order, mutate production rating/action/confidence/weight, change nginx/systemd/firewall, or modify Mac/iPhone/wimac local workspaces. Controlled static Dashboard preview publish is the only approved publish action.

## Validation and rollback
The validator checks audit rows, contract rows, channel differentiation, prediction fallback visibility, 13:35 Close Snapshot semantics, no raw logs, no secret patterns, and safety flags. Rollback uses the existing static Dashboard preview publish manifest and backup path.
