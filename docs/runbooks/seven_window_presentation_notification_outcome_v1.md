# Seven-Window Presentation, Notification and Outcome V1

## Root causes

Presentation formatting had grown independently in Dashboard and notification modules. Raw canonical enums, provider timestamps and signed distances therefore leaked to users. TW 13:35 read only a payload-level timestamp even when all structured cards had observed timestamps. US 06:30 presentation inferred review success/no-trade from generic tactical/research state instead of canonical cards with actual evidence.

## Shared presentation normalization

`app/reports/presentation_normalization.py` is the field-aware boundary for enum localization, safe missing values, timestamps, directional distance text, next actions and concise news summaries. Canonical payload values remain machine-readable. Public renderers must not use blind global replacement.

Epoch seconds, milliseconds, microseconds and nanoseconds are accepted. Standard epochs are converted by timezone. TW provider values that encode a local wall clock as epoch-ns are reinterpreted only when the normal conversion is implausibly later than the same card's fetched/normalized timestamp. Invalid values render `尚未取得`.

Target and stop distances retain signed canonical values but render directional semantics such as `已高於目標 2.31%` or `距停損仍有 6.38%`.

## News two-level UX

TW 07:00 primary cards contain a concise direction, reason, strategy impact, source-quality and confidence summary. Full research remains in a details section. Official disclosure, exchange/regulator and company IR take priority; social/unverified evidence cannot independently raise entry readiness.

## TW 13:35

The summary market-data time is the latest valid canonical card timestamp. Priority is a deterministic subset of `reduce`, `avoid_overnight` and `hold`; no-trade/unavailable symbols remain in detailed cards but are not priority. Next-session wording is derived from holding, trigger, target and stop states.

## TW 15:00

Presentation is outcome-first. `hit`, `fail`, `not_triggered`, `no_trade` and `pending` map to deterministic next actions. Null review text never renders as `None`.

## US 06:30 canonical semantics

Only `structured_review_cards[]` feed `aggregate_outcomes()`. Hit/fail require actual high, low and close, a prediction snapshot reference and explicit range evidence. Not-triggered requires complete actual data and an explicit non-trigger. Canonical no-trade requires formal no-trade evidence. Research/tactical avoidance alone remains pending.

`review_card_count` counts cards; `completed_review_count` counts non-pending canonical outcomes; `pending_review_count` counts pending cards. Email, LINE and Dashboard consume those same totals. Unmapped outcomes fail validation and never render an `其他` bucket.

US presentation separates the US trading date, America/New_York market time and Asia/Taipei report time.

## Cross-channel parity

Archive, active market Dashboard, Email preview, LINE preview and Operations retain snapshot ID, revision, source payload hash, symbol set and canonical counts. Presentation hashes may differ. Formatters must not independently classify outcomes.

## Controlled verification and publish

Validators use deterministic temporary artifacts and no-send formatters. They do not modify formal runtime, archive, provenance or public roots. Controlled publish is permitted only after merge, CI, post-merge gates, artifact hash stability and rollback backup. It rebuilds presentation from resolver-selected admitted immutable snapshots and never backfills history.

## Natural verification

AI-DEV-187 remains `IMPLEMENTED_PENDING_NATURAL_VERIFICATION` until natural TW 07:00/13:05/13:35/15:00 and US 06:30 runs prove the presentation and notification contracts. AI-DEV-185 and AI-DEV-186 retain their separate natural-verification requirements.

## Rollback and limitations

Use the controlled publisher's recorded rollback directory to restore static presentation. Do not rewrite immutable snapshots. Historical pages may retain historical wording; latest presentation can be rebuilt safely from the immutable payload. Missing actual evidence remains pending rather than being inferred.
