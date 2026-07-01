# AI-DEV-112 Unified All-Day Scheduler Delivery Activation V1

AI-DEV-112 extends the approved scheduler delivery path from the existing
07:00 pre-open window to the remaining daily windows while preserving the
07:00 production behavior.

## Scheduler Mechanism

The production schedule uses user cron entries that invoke:

```bash
/home/kaochuchian/stock-ai/run_stock_analysis.sh
```

Approved delivery requires the cron entry to set:

```bash
STOCK_AI_APPROVED_DELIVERY=1
```

`run_stock_analysis.sh` detects the scheduler window in Taiwan time and routes
approved entries to:

```bash
scripts/orchestrator/approved_pre_open_delivery.py --window <window_id>
```

The runner executes:

```bash
scripts/run_pipeline.py <pipeline_type> --production-approved
```

## Windows

| Window | Taiwan time | Pipeline | LINE | Email | Dashboard | Fallback |
| --- | ---: | --- | --- | --- | --- | --- |
| `pre_open_0700` | 07:00 | `pre_open` | Existing production pre-open pipeline sends the report. | Full scheduled summary. | Publish latest full scheduler snapshot. | Include output tail if report content is partial. |
| `intraday_1305` | 13:05 | `intraday` | Concise reminder only with key status and dashboard URL. | Full report from validated pipeline output when available. | Publish latest intraday snapshot. | Mark report content pending / insufficient data if only context summary exists. |
| `pre_close_1335` | 13:35 | `pre_close` | Concise risk / market status reminder only; no trading instruction. | Full report from validated pipeline output when available. | Publish latest pre-close snapshot. | Mark report content pending / insufficient data if only context summary exists. |
| `post_close_1500` | 15:00 | `post_close` | One concise summary reminder with dashboard URL. | Full post-close / prediction review report, including pending state. | Publish latest post-close / prediction review snapshot. | Mark prediction review pending / insufficient data when review records are unavailable. |

## Dashboard

The approved runner publishes:

```bash
/var/www/stock-ai-dashboard/index.html
/var/www/stock-ai-dashboard/publish_manifest.json
```

The public URL remains:

```text
http://35.201.242.167/stock-ai-dashboard/index.html
```

## Safety

- No trading, order placement, or portfolio action is implemented.
- Afternoon LINE delivery is concise only and includes the dashboard URL.
- Full report content is reserved for Email and Dashboard.
- Secret values are not printed. Runtime delivery failures report only error type.
- The runner writes a JSON result artifact per window under `/tmp` by default.
- 07:00 behavior remains routed through the existing pre-open production pipeline.

## Validation

```bash
python3 -m py_compile \
  app/pipelines/runner.py \
  scripts/orchestrator/approved_pre_open_delivery.py \
  scripts/orchestrator/production_scheduler_gate_runtime.py \
  scripts/orchestrator/validate_production_scheduler_gate_runtime_result.py \
  scripts/orchestrator/validate_scheduled_runner.py

for window in pre_open_0700 intraday_1305 pre_close_1335 post_close_1500; do
  STOCK_AI_APPROVED_DELIVERY=1 python3 scripts/orchestrator/approved_pre_open_delivery.py \
    --window "$window" \
    --dashboard-publish-dir "/tmp/stock_ai_ai_dev_112_dashboard_$window" \
    --output "/tmp/approved_${window}_delivery_dry_run.json" \
    --dry-run
done

python3 scripts/orchestrator/validate_scheduled_runner.py --pretty
```
