# AI-DEV-113 Afternoon Delivery Content Wiring V1

AI-DEV-113 fixes the content gap discovered after the all-day scheduler activation.
The afternoon scheduler windows were successfully delivering through LINE, Email,
and Dashboard, but the payload came from scheduler status snapshots rather than
stock-analysis report content.

## Change

The 07:00 pre-open stock-analysis/report generation flow is extracted into a
shared pipeline helper:

```text
app/pipelines/stock_analysis_report_pipeline.py
```

The existing pipeline entrypoints now use that helper:

- `pre_open`: keeps existing behavior, including historical update, SQLite writes,
  full production LINE report batches, and backtest auto-update.
- `intraday`: generates stock-analysis report text, writes analysis results, and
  suppresses full LINE batches.
- `pre_close`: generates stock-analysis report text, writes analysis results, and
  suppresses full LINE batches.
- `post_close`: generates stock-analysis report text, writes analysis results, and
  suppresses full LINE batches.

The approved scheduler wrapper remains responsible for concise afternoon LINE
reminders. Email and Dashboard receive the captured report output from the
pipeline run.

## Product Policy

- LINE: concise afternoon reminder only; no full long report and no trading
  instruction.
- Email: full report content from the validated pipeline output when available.
- Dashboard: latest report output from the validated pipeline output when
  available.
- Trading/order/portfolio action: not implemented.

## Safety

- No secret, token, password, `.env`, or credential value is printed by this
  change.
- No trading, order placement, or portfolio action is introduced.
- No cron, systemd, timer, service, Docker, or Dify runtime configuration is
  changed by this repo patch.
- The existing 07:00 behavior is preserved through the shared helper with full
  LINE report batches enabled only for `pre_open`.

## Validation

```bash
python3 -m py_compile \
  app/pipelines/stock_analysis_report_pipeline.py \
  app/pipelines/pre_open_pipeline.py \
  app/pipelines/intraday_pipeline.py \
  app/pipelines/pre_close_pipeline.py \
  app/pipelines/post_close_pipeline.py \
  app/pipelines/runner.py \
  scripts/run_pipeline.py \
  scripts/orchestrator/approved_pre_open_delivery.py

python3 scripts/run_pipeline.py intraday --dry-run --limit 1
python3 scripts/run_pipeline.py pre_close --dry-run --limit 1
python3 scripts/run_pipeline.py post_close --dry-run --limit 1
```

The `--limit` flag remains restricted to pre-open in the runtime contract, so the
last three commands should be executed without `--limit` if the validator has not
been extended. For a low-cost check, use `--dry-run` and inspect for:

```text
pipeline_report_summary
stock_analysis_reports_available
full LINE report disabled
```
