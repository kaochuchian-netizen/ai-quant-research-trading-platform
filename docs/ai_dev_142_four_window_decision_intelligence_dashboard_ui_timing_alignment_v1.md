# AI-DEV-142 Four-Window Decision Intelligence Dashboard UI & Timing Alignment V1

## Purpose

AI-DEV-142 is the first user-visible four-window UI integration for the V10 Decision Intelligence chain. It turns deterministic artifacts from AI-DEV-136 through AI-DEV-141 into a static, mobile-readable dashboard preview for four daily decision windows.

This task intentionally combines review pack, UI contract, and UI integration into one repo-side foundation so the dashboard can be visually inspected instead of only reviewed as JSON or Markdown.

## Four Windows

| Runtime key | UI window id | Time | UI label | Purpose |
| --- | --- | --- | --- | --- |
| `pre_open_0700` | `pre_open_0700` | 07:00 | 盤前預測 / Pre-open Forecast | Forecast context before market open. |
| `intraday_1305` | `intraday_1305` | 13:05 | 盤中追蹤 / Intraday Tracking | Track whether intraday action still fits the pre-open scenario. |
| `pre_close_1335` | `close_snapshot_1335` | 13:35 | 收盤快照 / Close Snapshot | Preliminary close snapshot and hit-status view. |
| `post_close_1500` | `prediction_review_1500` | 15:00 | 盤後檢討 / Prediction Review | Forecast-vs-actual and decision quality feedback. |

## 13:35 Timing Alignment

The underlying runtime key remains `pre_close_1335` for compatibility with existing schedules and artifacts. The dashboard UI label is corrected to `close_snapshot_1335` / 收盤快照. The main UI copy no longer treats 13:35 as a risk-reminder window; it is a preliminary close snapshot that defers full prediction review to 15:00.

## Decision Intelligence Blocks

The shared UI preview includes:

- Executive Decision Intelligence Summary
- Official Source Admission Summary
- Source Credibility Cards
- Formal Integration Cards: FinMind, TWSE, yfinance
- Evidence Trace Summary
- Factor Rationale Cards
- Warning / Exclusion Cards
- Metadata-only Badges
- Advisory-only Badges
- Feedback Recommendation Cards
- Mutation Policy Summary

## Source Policy

MOPS / company announcements / financial statements / monthly revenue / investor conferences / IR materials are core evidence admission families. Industry supply chain and peer company context are contextual evidence. FinMind cannot replace official sources. yfinance/Yahoo cannot replace official sources. Google News RSS cannot be core forecast evidence. Broker target / analyst rating is metadata-only. Gemini / AI-generated analysis is not original evidence.

## Mutation And Delivery Policy

The preview explicitly shows:

- `recommendation_only=true`
- `human_review_required_for_any_mutation=true`
- `direct_rating_action_confidence_impact=false`
- `production_weight_changed=false`
- `production_confidence_changed=false`
- `production_rating_action_changed=false`
- `production_pipeline_modified=false`
- `delivery_behavior_modified=false`

AI-DEV-142 does not send LINE / Email, does not modify scheduler / cron / systemd / timer, does not execute production pipelines, and does not change rating/action/confidence.

## Preview Output

The deterministic builder produces:

- `templates/four_window_decision_intelligence_dashboard_artifact.example.json`
- `templates/four_window_decision_intelligence_dashboard_preview.example.html`

These are repo-side static preview artifacts. They are not production dashboard deployment and do not publish dashboard runtime.

## Follow-Up

Future work may connect this artifact to the formal daily report renderer, email renderer, LINE reminder summary, or production dashboard route through separate tasks with explicit delivery and scheduler gates.
