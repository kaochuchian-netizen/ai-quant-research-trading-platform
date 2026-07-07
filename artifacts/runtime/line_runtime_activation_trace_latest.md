# AI-DEV-158 LINE Runtime Activation Trace

## Scope
Read-only/dry-run verification package for tomorrow's four LINE scheduler windows. This artifact does not send LINE and does not change cron, systemd, or timers.

## Runtime Path Summary
- run_stock_analysis.sh detects STOCK_AI_SCHEDULER_WINDOW or local time and calls scripts/orchestrator/approved_pre_open_delivery.py when STOCK_AI_APPROVED_DELIVERY=1.
- 07:00 pre_open_0700 runs the pre_open pipeline, whose LINE path uses reports.line_short_formatter.format_line_short.
- 13:05 intraday_1305, 13:35 pre_close_1335, and 15:00 post_close_1500 use approved_pre_open_delivery.build_line_message, now delegated to app.reports.multi_window_formatter.line_notification_text.
- The approved wrapper and run_stock_analysis.sh default Dashboard URL point to the four-window Decision Intelligence Dashboard.

## Four-Window Formatter Summary
- 07:00 `pre_open_0700`: app.pipelines.pre_open_pipeline.send_reports_in_batches -> reports.line_short_formatter.format_line_short
- 13:05 `intraday_1305`: scripts.orchestrator.approved_pre_open_delivery.build_line_message -> app.reports.multi_window_formatter.line_notification_text
- 13:35 `pre_close_1335`: scripts.orchestrator.approved_pre_open_delivery.build_line_message -> app.reports.multi_window_formatter.line_notification_text
- 15:00 `post_close_1500`: scripts.orchestrator.approved_pre_open_delivery.build_line_message -> app.reports.multi_window_formatter.line_notification_text

## Old Formatter / Old URL Risk Check
- Active dry-run preview messages do not contain `status:`, `state:`, `pipeline output available`, or the old `/stock-ai-dashboard/index.html` URL.
- Historical logs and older docs may still contain old wording as records; they are not the active formatter path validated by this preview.

## Dry-Run Preview Artifact
- JSON: `artifacts/runtime/line_four_batch_runtime_preview_latest.json`
- Markdown: `artifacts/runtime/line_four_batch_runtime_preview_latest.md`

## No Actual Send Confirmation
- `is_actual_send=false` for every window.
- `safety_mode=dry_run_preview_only` for every window.
- LINE, Email, and external notification sending were not invoked by this builder.

## Tomorrow Manual Verification Checklist
- 07:00: exactly one short reminder, no stock details, no C級/B級/score/technical/chip fields, and the new Dashboard URL.
- 13:05: short reminder only, no status/state/pipeline wording, and the new Dashboard URL.
- 13:35: says 收盤快照, no status/state/pipeline wording, and the new Dashboard URL.
- 15:00: says 盤後檢討, no raw English pending/insufficient-data wording, and the new Dashboard URL.
