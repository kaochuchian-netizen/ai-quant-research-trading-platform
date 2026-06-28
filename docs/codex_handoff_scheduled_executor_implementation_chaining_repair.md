# Scheduled Codex Executor Implementation Chaining Repair

## Root Cause

PR #75 was a handoff-only PR for GitHub Issue #74. It only added:

```text
docs/mobile_issue_handoffs/issue_74_mobile-auto-pickup-20260628T125252Z.md
```

The executor returned a manual-only planning decision, but the scheduled runner
treated the helper's successful process result as completed Codex execution and
marked the handoff processed. That allowed later scheduled pickup runs to reject
Issue #74 as `already_processed` even though the requested AI-DEV-070
implementation had not happened.

## Repair Contract

`executed_codex_handoff` now means all of the following are true:

- readiness allowed the executor call
- the executor was called through `--execute-headless`
- the executor result has `implementation_completed=true`
- changed files include at least one file outside `docs/mobile_issue_handoffs/`
- idempotency is marked only after verified implementation completion

The runner fails closed with `handoff_only_not_implemented`,
`executor_no_implementation`, or `codex_executor_failed` when these conditions
are not met.

## Issue #74 Retry

The existing handoff remains the retry source:

```text
docs/mobile_issue_handoffs/issue_74_mobile-auto-pickup-20260628T125252Z.md
```

If the old processed record is found with a non-implementation executor
decision, the runner removes only that key and writes a repair artifact with:

```text
unmarked_reason=handoff_only_not_implemented
source_pr=75
safe_to_retry=true
```

No historical run artifacts are deleted.
