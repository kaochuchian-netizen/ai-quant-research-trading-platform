# AI-DEV-256C — 17:00 Learning Loop Deployment and Visibility

## Deployment scope

AI-DEV-256C deploys the bounded legacy frozen-evidence replay repair together
with a Dashboard-only presentation sidecar for the existing 17:00 entrypoint.
It does not alter the Asia/Taipei 17:00 cron entry, restore paused windows,
send LINE or email, mutate strategy/model/weights, or create an order.

## User-visible projection

The sidecar reads the exact immutable `DAILY_EVALUATION` value already produced
by the unified evaluator and renders:

```text
【每日策略檢討】YYYY-MM-DD

台股
預測成果：
策略檢討：
學習調整：

美股
預測成果：
策略檢討：
學習調整：

今日結論：
下一交易日調整：
```

The route is `/dashboard/daily-evaluation/latest/index.html`; each run also
receives an identity-bound static route under its report date. It is a
non-blocking sidecar: a presentation failure is recorded as
`PRESENTATION_FAILED` without invalidating the immutable evaluation artifact or
changing the 17:00 evaluator result.

The page is Traditional Chinese and mobile-first, including a 393px layout.
Internal enums, hashes, paths, raw evidence fields, validators, and technical
diagnostics are absent from the default view. A collapsed **詳細評估資料** section
states that the immutable artifact retains audit/replay evidence.

## Learning-language mapping

The presentation only translates existing evaluator facts. A mature
`DIRECTION_ERROR_OBSERVED` finding is shown as a direction judgement that did
not match the actual move and a conservative next-session handling instruction.
It does not claim a model/weight/strategy mutation. Unmatured outcome evidence
is described as pending, never as a miss or success.

## LINE readiness

`render_line_summary()` formats the same immutable evaluator output for a
future compact LINE delivery. It has no transport import or send operation.
Therefore this task leaves `LINE_ACTIVATED = NO`; enabling a real recipient or
delivery path requires a separate explicit production-notification approval.

## Acceptance plan

After merge and controlled code sync, only the next natural 17:00 run may
provide production acceptance. It must produce VALID TW and US evaluation,
an immutable daily artifact, a Dashboard sidecar, and a learning candidate
without `FROZEN_REPLAY` or `BLOCKED_INPUT`. No historical batch is rerun for
acceptance.
