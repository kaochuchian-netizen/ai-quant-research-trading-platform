# LINE Runtime Activation Verification Runbook V1

AI-DEV-158 verifies tomorrow's four scheduled LINE windows without sending LINE, changing scheduler entries, reading secrets, or running the production pipeline.

## What This Checks

- The approved scheduler wrapper resolves to the AI-DEV-157 link-only formatter.
- The default Dashboard URL is the four-window Decision Intelligence page.
- Dry-run preview messages do not contain stock details, raw pipeline status, or the legacy `/stock-ai-dashboard/index.html` URL.
- The check is a dry-run preview only; the real delivery must still be observed tomorrow on LINE.

## Tomorrow Manual Verification Checklist

### 07:00 盤前

- Only one short reminder is received.
- No per-stock details appear.
- No `C級`, `B級`, score, close, technical, chip, strategy, or stock-card fields appear.
- The message links to the four-window Dashboard URL.

### 13:05 盤中

- Only a short reminder is received.
- No `status`, `state`, or `pipeline` wording appears.
- The message links to the four-window Dashboard URL.

### 13:35 收盤快照

- The message says `收盤快照`.
- No `status`, `state`, or `pipeline` wording appears.
- The message links to the four-window Dashboard URL.
- It is not presented as a full prediction review.

### 15:00 盤後檢討

- The message says `盤後檢討`.
- No raw English `prediction review pending` or `insufficient data` wording appears.
- The message links to the four-window Dashboard URL.

## Safety Boundaries

This runbook does not approve actual LINE test sends, scheduler changes, DB writes, production pipeline execution, `python3 main.py`, trading/order actions, or secret inspection.
