# AI-DEV-115A Pre-Open Delivery Incident Regression Guard

## Incident Summary

On 2026-07-02 07:00, run `approved-pre_open_0700-delivery-20260702-070001`
failed during the `pre_open_0700` approved scheduler delivery.

Observed impact:

- LINE did not send.
- Email was sent but contained incorrect raw failure content.
- Dashboard updated, but the user-facing section displayed traceback / raw scheduler output.
- The pre-open pipeline stopped when stock name lookup called Shioaji and login failed.

## Root Cause

Historical CSV fallback was available, but `app/market/stock_name_loader.py`
called `get_api()` before entering any fallback handling. A Shioaji login/version
failure raised `ShioajiClientError` during stock name lookup and interrupted
the report pipeline before validated report content could be produced.

The approved delivery wrapper then reused the raw pipeline output tail as the
main Dashboard and Email content, so runtime diagnostics appeared as the
user-facing report.

## Files Changed

- `app/market/stock_name_loader.py`
- `app/pipelines/pre_open_pipeline.py`
- `app/pipelines/afternoon_report_pipeline.py`
- `scripts/orchestrator/approved_pre_open_delivery.py`
- `scripts/orchestrator/validate_ai_dev_115a_preopen_delivery_incident_regression_guard.py`
- `docs/ai_dev_115a_preopen_delivery_incident_regression_guard.md`

## Fix Summary

- Added a safe stock name resolver that never lets Shioaji lookup failure crash
  report generation.
- Fallback order is local stock-name map files when present, then stock ID.
- Added stock-name fallback diagnostics to pre-open and afternoon report
  summaries.
- Kept four scheduler windows on the same stock-name fallback path:
  `pre_open`, `intraday`, `pre_close`, and `post_close`.
- Separated approved delivery user-facing content from diagnostics.
- Dashboard and Email now render a safe status message when the pipeline fails
  or raw output contains traceback.
- Raw pipeline output tail remains in the delivery artifact diagnostics.
- LINE delivery artifacts now expose `line_delivery_status` and
  `line_delivery_reason` when no LINE message is sent.

## User-Facing vs Diagnostics Policy

User-facing Dashboard and Email content must not render Python traceback,
`ShioajiClientError`, or raw scheduler summary as the main report body.

Diagnostics may retain the raw pipeline output tail, return code, and traceback
markers inside structured delivery artifacts for operator review.

## Validation Commands

```bash
python3 -m py_compile \
  app/pipelines/pre_open_pipeline.py \
  app/pipelines/intraday_pipeline.py \
  app/pipelines/pre_close_pipeline.py \
  app/pipelines/post_close_pipeline.py \
  app/market/stock_name_loader.py

python3 scripts/orchestrator/validate_ai_dev_115a_preopen_delivery_incident_regression_guard.py --pretty

python3 scripts/run_pipeline.py pre_open --dry-run
python3 scripts/run_pipeline.py intraday --dry-run
python3 scripts/run_pipeline.py pre_close --dry-run
python3 scripts/run_pipeline.py post_close --dry-run
```

## Safety Boundaries

- No LINE test notification sent.
- No Email test notification sent.
- No scheduler, cron, or systemd time changed.
- No trading, order, or portfolio action.
- No `.env`, secret, token, API key, or credential content read or printed.
- No production database destructive operation.
