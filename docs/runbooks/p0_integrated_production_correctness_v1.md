# P0 Integrated Production Correctness V1

## Incident and evidence boundary

AI-DEV-182 found three P0 defects: the 2026-07-17 TW 13:05 child pipeline exceeded its 600-second guard; admitted TW snapshots were not propagated to public Latest; and US 06:30 pending cards were counted as No Trade and Reviewed. The historical 13:05 artifact contains only wrapper output and two Shioaji initialization messages. It does not identify the exact internal blocking stage. The defensible root cause is the uninstrumented nine-stock serial critical path with repeated optional external I/O, inconsistent timeout/retry bounds, and buffered child output. The last visible activity is Shioaji session/contracts initialization, not proof that it was the blocking stage.

## TW 13:05 stage budget

The hard budget remains 600 seconds. It was not increased. The contract uses a 90-second stage soft budget, 12-second external request timeout, at most one retry with 0.5-second backoff, and 15-second heartbeat interval. These bounds derive from the existing 378-second nine-stock pre-open timing evidence and the former 15-second external-source policy. Google News is bounded to eight seconds; Gemini uses one cached process client, a 12-second request timeout, and two total attempts.

Stages are `entrypoint`, `market_data`, `technical`, `news`, `fundamentals`, `chip`, `adr`, `strategy`, `prediction`, `formatter`, `runtime_write`, `snapshot_admission`, `archive_build`, `publish`, `notification_format`, and `delivery`. The pipeline persists start, completion, elapsed time, status, heartbeat, and sanitized error data. Optional enrichment fails soft with an explicit unavailable reason. A required runtime with zero valid cards fails closed.

## Timeout and failure artifact

Timeouts persist `stage_timeout`, the last observed stage, last completed stage, last heartbeat, retry count, and sanitized reason. Failure evidence explicitly records that runtime persistence, snapshot admission, public publish, Email, and LINE did not occur. No previous runtime is promoted. A failed 13:05 run cannot become a same-day 13:35 comparison baseline; diagnostics distinguish failed, missing, rejected, and available states.

## Admission-to-public transaction

The admitted archive resolver is the sole Latest authority:

`admission -> resolve admitted Latest -> build canonical Latest -> build active market alias -> publish -> verify identity`

Scheduled TW and US runners execute this transaction after a successful snapshot write. Manual rerun remains on its existing latest-only targeted path. Previous remains the prior effective trading date's highest revision; a same-day older revision and an older historical snapshot cannot replace Latest.

Public verification compares market, window, effective trading date, snapshot ID, revision, and source payload hash on both the canonical archive route and active market Dashboard. A successful file copy with a marker mismatch is `failed_verification`; the runner is not fully successful. Transaction diagnostics retain expected identity, observed identity, mismatch fields, and verification time.

## US canonical outcomes and reviewed semantics

The only outcomes are `hit`, `fail`, `not_triggered`, `no_trade`, and `pending`. A card has exactly one. Pending means evidence is incomplete and can never be inferred as No Trade from tactical action text. No Trade requires an explicit strategy decision not to establish a setup.

All aggregates are recalculated from `structured_review_cards[]`:

- `review_card_count`: rendered review cards
- `completed_review_count`: hit + fail + not_triggered + no_trade
- `pending_review_count`: pending
- `review_universe_count`: completed + pending

Six pending cards therefore mean cards 6, completed 0, pending 6, No Trade 0. Runtime, snapshot, archive, Dashboard, Email, LINE, and Operations consume this aggregate rather than maintaining independent totals.

## Notification provenance

Each channel persists a non-sensitive artifact containing market, window, trading date, snapshot ID, revision, source payload hash, channel presentation hash, canonical URL, format time, attempt/result/time, anonymous recipient count, and message length. Valid results are `sent`, `failed`, `suppressed`, `dry_run_not_sent`, and `not_attempted`. Email addresses, LINE IDs, tokens, and authorization headers are forbidden.

Source payload hashes compare source identity only. Email, LINE, archive, and Dashboard presentation hashes remain separate because their serialized forms intentionally differ.

## Financial and date normalization

Financial reference fields retain raw value, unit, currency, scale, normalized value/unit/currency, source, period end, and filing date. Values without a provable unit/currency/scale render as `正式資料尚無法安全標準化`; they are not guessed. Dates use ISO form. Datetimes retain timezone offsets. Python `date`/`datetime` repr is never user-facing.

## Controlled verification

Validators use temporary stage artifacts, temporary public roots, deterministic review cards, and non-sensitive delivery payloads. They do not run a production pipeline, touch `/var/www`, write production snapshots, send notifications, trade, change scheduler configuration, or call `main.py`.

## Rollback

Source rollback reverts the implementation commit through normal Git history. Static publish rollback uses the controlled publisher's backup. Immutable snapshots are never rewritten or deleted. If identity verification fails, retain both expected and observed evidence and stop downstream success classification.

## Natural production observation

After merge, observe the next natural TW 13:05 for complete stage timing, runtime within budget, admission, canonical Latest, TW active alias, delivery attempts/provenance, and a usable same-day 13:35 baseline. Observe the next natural US 06:30 for card/aggregate/channel parity and an empty pending/no_trade intersection. Observe each next successful TW window for admitted/public identity parity.

Until those observations pass, AI182-P0-001, AI182-P0-002, and AI182-P0-003 must be `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`, never `CLOSED`.
