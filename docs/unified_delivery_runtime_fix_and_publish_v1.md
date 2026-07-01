# Unified Delivery Runtime Fix and Publish V1

AI-DEV-109 closes the repo-side runtime gaps for controlled LINE, Email, and
private static dashboard delivery.

## Changes

- `controlled_line_runtime.py` now inserts the repository root into `sys.path`
  before importing `reports.line_report_sender`.
- `controlled_email_runtime.py` provides a gate-checked one-shot SMTP test path.
  It loads only documented `ORCH_MAIL_*` settings from
  `~/.config/stock-ai-orchestrator/mail.env` by default and reports only
  presence booleans, env names, and redacted error types.
- `unified_controlled_delivery_runtime.py` safely checks the documented mail env
  file and points the Email test command at the controlled Email runtime.
- `private_static_dashboard_publish.py` can inspect existing static web roots
  and publish to a browser-viewable local file export when no writable served
  static root is available.

## Safety

These helpers do not print secret values, tokens, passwords, recipient values,
SMTP host values, or LINE IDs. They do not modify cron, systemd, timers,
services, remotes, Google Sheet settings, broker settings, portfolio state, or
trading state.

Scheduler activation remains a separate final confirmation step. The candidate
command is emitted for review only and is not run by this fix.

## Commands

Unified dry run:

```bash
python3 scripts/orchestrator/unified_controlled_delivery_runtime.py \
  --input templates/unified_controlled_delivery_runtime_input.example.json \
  --output /tmp/unified_controlled_delivery_runtime_result.json \
  --summary-output /tmp/unified_controlled_delivery_runtime_summary.json \
  --pretty
```

Controlled Email one-shot test:

```bash
python3 scripts/orchestrator/controlled_email_runtime.py \
  --input /tmp/ai_dev_109_unified_approved_input.json \
  --output /tmp/ai_dev_109_email_test_result.json \
  --summary-output /tmp/ai_dev_109_email_test_summary.json \
  --pretty --send-test-email
```

Private static dashboard publish:

```bash
python3 scripts/orchestrator/private_static_dashboard_publish.py \
  --input /tmp/ai_dev_109_dashboard_gate_approved_input.json \
  --output /tmp/ai_dev_109_dashboard_publish_result.json \
  --pretty --publish --auto-browser-target
```
