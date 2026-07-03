# Scheduled Delivery Content Quality Runbook

## Identify raw logs leaking into reports
Inspect delivered Email/Dashboard/LINE body for Shioaji, Solace, Response Code, Event Code, APISUB, P2P, host addresses, SQLite operational writes, `開始分析股票`, `pipeline_report_summary`, or raw JSON dumps.

## Check whether formatter label is wrong
Confirm the scheduler window and pipeline type. Post-close content must show 盤後, prediction review content must show 預測檢討, and only pre-open content should show 盤前.

## Verify user-facing content vs diagnostics
User-facing content should include title, summary, clean sections, stock/review cards, warnings, and dashboard URL. Diagnostics should contain suppression counts, raw log categories, source warnings, and operator action requirements.

## Verify LINE/Email/Dashboard policies
LINE should receive concise summary policy where configured. Email should receive the clean full report. Dashboard should show clean report plus diagnostics sections. Raw stdout must not be the main report body.

## Why not to resend malformed report immediately
A resend can duplicate bad content and hide the root cause. First build sanitized output offline, verify diagnostics, and confirm whether any previous delivery was sent.

## Validate sanitized output

Use this section to validate sanitized output before any resend decision.
Run `./venv/bin/python scripts/orchestrator/validate_multi_window_report_content_v1.py --pretty` and build each window artifact. Confirm raw operational patterns are absent from `user_facing_report` and present only as diagnostic suppression summaries.

## post-incident verification checklist
- user-facing content has the correct window label
- post_close does not show 盤前
- prediction_review does not show 盤前
- raw logs are suppressed
- SQLite operational lines are suppressed
- pipeline summary dumps are suppressed
- diagnostics contain suppression summary
- no LINE/Email resend occurred during validation
- no dashboard production publish occurred during validation
