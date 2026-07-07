# AI-DEV-158 LINE Runtime Activation Verification & Tomorrow Delivery Guard V1

AI-DEV-158 is a dry-run activation guard for the four scheduled LINE windows. It confirms that the runtime path is aligned with the AI-DEV-157 link-only notification contract before tomorrow's real scheduler windows run.

## Result

The approved scheduler path is:

1. `run_stock_analysis.sh` detects the scheduler window.
2. When `STOCK_AI_APPROVED_DELIVERY=1`, it calls `scripts/orchestrator/approved_pre_open_delivery.py`.
3. The approved delivery runner builds LINE text through the AI-DEV-157 short notification formatter path.
4. The preview builder renders all four messages without sending LINE.

## Four Windows

- `pre_open_0700`: 07:00 盤前決策摘要
- `intraday_1305`: 13:05 盤中追蹤
- `pre_close_1335`: 13:35 收盤快照
- `post_close_1500`: 15:00 盤後檢討

## Safety

This package does not send LINE, Email, or notifications. It does not change cron, systemd, timers, DB state, forecast formulas, production rating/action/confidence/weight logic, or trading behavior.

## Artifacts

- `artifacts/runtime/line_four_batch_runtime_preview_latest.json`
- `artifacts/runtime/line_four_batch_runtime_preview_latest.md`
- `artifacts/runtime/line_runtime_activation_trace_latest.md`

## Validation

Run:

```bash
./venv/bin/python scripts/orchestrator/build_line_four_batch_runtime_preview_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_line_runtime_activation_guard_v1.py --pretty
```
