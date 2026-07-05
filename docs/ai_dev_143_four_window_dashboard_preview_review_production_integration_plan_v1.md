# AI-DEV-143 Four-Window Dashboard Preview Review & Production Integration Plan V1

## Purpose

AI-DEV-143 is the read-only UI quality review and production integration planning step after AI-DEV-142. It evaluates whether the four-window Decision Intelligence dashboard preview is readable, complete, and semantically aligned before any controlled dashboard route integration.

It does not directly publish production dashboard, does not modify scheduler, does not send LINE / Email, does not execute production pipeline, and does not change rating/action/confidence.

## Review Scope

The review artifact checks:

- four-window completeness
- timing alignment
- readability
- mobile readability
- Decision Intelligence coverage
- source policy visibility
- warning / badge visibility
- mutation policy visibility
- production integration plan readiness
- safety boundaries

## Four-Window Review

The review covers:

- 07:00 `pre_open_0700` / 盤前預測
- 13:05 `intraday_1305` / 盤中追蹤
- 13:35 `pre_close_1335` runtime key with `close_snapshot_1335` UI label / 收盤快照
- 15:00 `post_close_1500` and `prediction_review_1500` / 盤後檢討

The 13:35 review preserves runtime key compatibility while confirming the UI no longer uses 收盤前 or pre-close as the main semantic frame. Full review remains deferred to 15:00.

## Readability Review

The preview is checked for card-first layout, short headings, no raw JSON blob in the main view, readable warnings and badges, understandable official source policy, clear recommendation/mutation policy, and visibly distinct daily windows.

## Mobile Readability Review

The review checks reasonable card count, mobile-friendly section order, short paragraphs, debug/details separation, and absence of technical logs in the main view.

## Production Integration Plan

AI-DEV-143 recommends AI-DEV-144 as a controlled dashboard route integration task. The proposed path is to connect the static preview artifact to a controlled dashboard route with validator gates, rollback plan, no-notification rule, no-scheduler-change rule, and human review gate.

No production publish is executed by AI-DEV-143.

## Safety

This task is read-only with respect to runtime and production systems. It does not call external APIs, read secrets, write DBs, modify scheduler / cron / systemd / timer, send LINE / Email / notification, publish production dashboard, run `python3 main.py`, execute production pipeline, trade, or mutate rating/action/confidence/weights.
