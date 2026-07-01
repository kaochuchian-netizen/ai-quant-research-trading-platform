# AI-DEV-111 Production 07:00 Scheduler Approved Delivery V1

AI-DEV-111 enables the existing weekday 07:00 user-cron scheduler path to run
approved pre-open delivery when the scheduler entry sets:

```bash
STOCK_AI_APPROVED_DELIVERY=1
```

The activation remains limited to `pre_open_0700`. The approved runner rejects
intraday, pre-close, and other windows.

## Scheduler Path

Existing cron entry:

```bash
0 7 * * 1-5 /home/kaochuchian/stock-ai/run_stock_analysis.sh
```

Approved delivery entry:

```bash
0 7 * * 1-5 STOCK_AI_APPROVED_DELIVERY=1 /home/kaochuchian/stock-ai/run_stock_analysis.sh
```

`run_stock_analysis.sh` routes that entry to:

```bash
scripts/orchestrator/approved_pre_open_delivery.py --window pre_open_0700
```

The runner then executes:

```bash
scripts/run_pipeline.py pre_open --production-approved
```

## Delivery Scope

- LINE is sent by the existing production `pre_open` pipeline.
- Email is sent after the pipeline run using the orchestrator mail config file.
- Dashboard is written to `/var/www/stock-ai-dashboard/index.html` by default.
- The public dashboard URL remains:
  `http://35.201.242.167/stock-ai-dashboard/index.html`

## Safety

- No trading, order placement, or portfolio action is implemented.
- The approved runner only supports `pre_open_0700`.
- Secret values are not printed. Runtime email failures report only error type.
- No duplicate scheduler entry is required; update the existing 07:00 entry.

## Validation

```bash
python3 -m py_compile \
  scripts/orchestrator/approved_pre_open_delivery.py \
  scripts/orchestrator/validate_scheduled_runner.py

STOCK_AI_APPROVED_DELIVERY=1 python3 scripts/orchestrator/approved_pre_open_delivery.py \
  --window pre_open_0700 \
  --dashboard-publish-dir /tmp/stock_ai_ai_dev_111_dashboard \
  --output /tmp/approved_pre_open_delivery_dry_run.json \
  --dry-run

python3 scripts/orchestrator/validate_scheduled_runner.py --pretty
```
