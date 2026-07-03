# AI-DEV-128 Multi-Window Report Content Contract V1

## Purpose
AI-DEV-128 establishes deterministic multi-window user-facing report contracts and delivery sanitization so scheduled reports do not expose raw operational logs or mislabeled content.

## Incident summary
The 2026-07-03 15:00 post_close / prediction review delivery completed, but report content included raw Shioaji/Solace/network session logs, SQLite operational lines, stock analysis operational lines, and post_close cards labeled as 盤前. Pipeline stdout was effectively mixed into user-facing report content.

## Scope
This release adds window context, report artifact contracts, diagnostics separation, sanitizer logic, multi-window formatter behavior, deterministic builders, validators, examples, and a scheduled delivery content quality runbook. It also routes approved delivery user-facing content through the sanitizer contract.

## Non-goals
- No production pipeline run
- No LINE or Email send
- No dashboard production publish
- No scheduler time change
- No cron/systemd/timer mutation
- No secrets read
- No production DB write
- No broker login, simulation order, production order, or trading action
- No forecast weight, confidence formula, rating rule, or action rule mutation
- No `python3 main.py`
- No n8n or Dify runtime start

## Window context model
Each supported scheduler window has a context with `schema_version`, `scheduler_window`, `pipeline_type`, `display_title`, `display_label`, `market_phase`, `primary_purpose`, `allowed_sections`, `disallowed_sections`, delivery policies, diagnostics policy, and `advisory_only=true`.

Labels are distinct: `pre_open_0700=盤前`, `intraday_1305=盤中`, `pre_close_1335=收盤前`, `post_close_1500=盤後`, and `prediction_review_1500=預測檢討`.

## User-facing report contract
The user-facing report contains title, subtitle, summary, sections, stock cards, review cards, warnings, dashboard URL, rendered text, and advisory-only status. It must not contain raw Shioaji/Solace logs, Response Code lines, APISUB/P2P session text, SQLite operational writes, `開始分析股票`, raw pipeline summary dumps, or tracebacks.

## Diagnostics contract
Diagnostics hold pipeline status, source warnings, suppression summary, raw traceback suppression state, operational log suppression state, artifact status, and operator action requirement. Raw operational logs are summarized, not rendered as main report content.

## Sanitizer policy
The sanitizer deterministically suppresses known operational patterns while preserving legitimate stock report lines. It records suppressed counts and categories so operators can see what was removed.

## Multi-window formatter policy
The formatter derives labels from the window context and never hardcodes one label for every report. Post-close stock cards use 盤後. Prediction review cards use 預測檢討 and render review states when full evaluation data is pending or insufficient.

## Post-close / prediction review content states
Supported states include `stock_analysis_reports_available`, `prediction_review_available`, `prediction_review_pending`, `prediction_review_insufficient_data`, `no_fresh_artifact`, `pipeline_timed_out`, `failed`, and `partial`. Pending and insufficient states render clear human-readable explanations instead of dumping pipeline stdout.

## Delivery wrapper integration contract
Approved delivery user-facing content is routed through `build_report_content_artifact`. Email and dashboard rendering consume sanitized rendered text. Raw stdout remains diagnostic-only through pipeline diagnostics. Validation never sends delivery or publishes dashboard.

## Validation commands
```bash
./venv/bin/python -m py_compile \
  app/reports/window_context.py \
  app/reports/report_content_contract.py \
  app/reports/report_sanitizer.py \
  app/reports/multi_window_formatter.py \
  app/reports/report_sections.py \
  app/reports/diagnostics_separator.py \
  scripts/orchestrator/build_multi_window_report_artifact.py \
  scripts/orchestrator/validate_multi_window_report_content_v1.py

./venv/bin/python scripts/orchestrator/validate_multi_window_report_content_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_multi_window_report_artifact.py --pretty
./venv/bin/python scripts/orchestrator/build_multi_window_report_artifact.py --pretty --window pre_open_0700
./venv/bin/python scripts/orchestrator/build_multi_window_report_artifact.py --pretty --window intraday_1305
./venv/bin/python scripts/orchestrator/build_multi_window_report_artifact.py --pretty --window pre_close_1335
./venv/bin/python scripts/orchestrator/build_multi_window_report_artifact.py --pretty --window post_close_1500
./venv/bin/python scripts/orchestrator/build_multi_window_report_artifact.py --pretty --window prediction_review_1500
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Safety boundary
All builders and validators use deterministic offline sample data. They do not run production pipelines, send LINE/Email, publish dashboard files, mutate scheduler settings, read secrets, write production DB state, trade, or start n8n/Dify.

## Rollback plan
Rollback is a code revert of the PR. Scheduler times, cron/systemd/timer configuration, delivery channels, prediction weights, confidence formulas, and rating/action rules are not changed.

## Future follow-up
- real historical artifact ingestion
- rolling evaluation
- production dashboard publish candidate
- source connector timeout hardening
