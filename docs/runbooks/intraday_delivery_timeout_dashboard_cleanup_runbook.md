# Intraday Delivery Timeout Dashboard Cleanup Runbook

## Scope

This runbook covers AI-DEV-160 timeout, late-delivery suppression, heartbeat artifact, and Dashboard content checks.

## Operator Triage

1. Inspect the latest delivery result artifact for the window.
2. Inspect the matching progress artifact under `artifacts/runtime/`.
3. Confirm whether `pipeline_completed` is false, `status` is `timed_out`, or `late_delivery_suppressed` is true.
4. Do not manually send LINE or Email for stale 13:05 or 13:35 output.

## Timeout Interpretation

`status=timed_out` means the child pipeline exceeded the configured window timeout. The wrapper should also show `line_attempted=false`, `email_attempted=false`, and `dashboard_publish_attempted=false`.

## Late Delivery Interpretation

`status=completed_late_delivery_suppressed` means the child pipeline completed but the delivery window grace period was exceeded. The artifact may be useful for review, but user-facing LINE and Email delivery are intentionally suppressed.

## Inspect Without Sending LINE or Email

Use validators and simulation helpers only:

```bash
./venv/bin/python scripts/orchestrator/simulate_intraday_delivery_timeout_guard_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_intraday_delivery_timeout_dashboard_cleanup_v1.py --pretty
```

Do not run production delivery with live send flags while investigating.

## Dashboard Checks

The main Dashboard should show human-readable missing states, one shared method section, one shared risk reminder, localized trends and confidence levels, and safe major-news fallback text.

Main Dashboard stock cards must not show raw artifact keys such as `source_evidence`, `read_mode`, `source_type`, `local_analysis_context`, `pipeline_run_id`, or `advisory_only`.

## No Fake Data

When news, runtime artifacts, review samples, or forecast fields are missing, leave them missing with explicit wording. Do not invent values or titles to fill the UI.

## Regression Guard

Run the AI-DEV-160 validator before merge. It also checks prior LINE, Dashboard card, review card, snapshot, calibration, value engine, runtime artifact, and four-window data-binding validators.

## Future Optional Design

Future work can add an early nonblocking warning that a pipeline is still running, but AI-DEV-160 only adds timeout, suppression, artifacts, and rendering cleanup.
