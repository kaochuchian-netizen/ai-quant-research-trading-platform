# Latest, Time, Outcome and LINE Correctness V1

## Root-cause matrix

- TW 13:35: delivery and public synchronization had no retained parity status in notification provenance. Latest resolution now orders by effective trading date, revision, then admitted time; generated time remains a legacy fallback.
- US 06:30: prediction-range coverage was reused as canonical trade outcome. Prediction evaluation and trade outcome are now separate contracts.
- TW 15:00: numeric exchange-local timestamps were interpreted as UTC before presentation. Source timezone and time-kind metadata are retained and presentation is source-aware.
- TW 07:00: unavailable news inherited direction/source defaults and ADR/RR text leaked provider vocabulary.
- LINE: canonical counts were preserved but symbol/action density was missing.

## TW 13:35 canonical Latest resolver

The resolver selects admitted immutable snapshots by effective trading date, revision, admitted time and deterministic snapshot ID. Public archive and active-market aliases are verified against market, window, date, snapshot ID, revision and payload hash. A publish mismatch remains a publish failure; it does not invalidate or rewrite the admitted snapshot.

Notification provenance retains public parity status plus expected and observed public identity. Operations cannot report full parity when synchronization verification fails.

## US prediction versus trade outcome

`prediction_range_result` is `hit`, `miss` or `pending`. `trade_outcome` retains `hit`, `fail`, `not_triggered`, `no_trade` or `pending`. A prediction hit does not prove entry, target, stop, MFE or MAE. Trade hit requires entry and target evidence; trade fail requires entry and stop/formal-failure evidence. Missing trade evidence remains pending.

All US 06:30 channels consume the same deterministic aggregate with separate prediction and trade counters. Old immutable payloads are normalized only while rendering; they are never rewritten.

## TW timestamp metadata

Observed records retain source timezone, source-record time kind and normalized timezone. Exchange-local values use their declared timezone. Date-only daily bars render a date and data granularity instead of a fabricated clock time. Reference-time sanity checks prevent double conversion.

## TW 07:00 fallback localization

RR threshold reasons and ADR context use field-aware formatting. Unavailable news renders unknown direction/source/confidence and does not modify technical ranking. Full detail is retained when present and explicitly marked unavailable otherwise.

## LINE decision density

LINE remains count-first and concise, then includes one canonical symbol/action line. Symbols come from the same groups/cards as Dashboard and Email; no channel recomputes outcomes.

## Controlled verification and publish

Controlled verification uses temporary targets, no-send formatters and deterministic fixtures. It must not mutate formal runtime, provenance or immutable history. Static publish is allowed only after merge, CI, post-merge gates, rollback backup and governance-safe worktree checks; it rebuilds presentation from resolver-selected snapshots only.

## Natural verification

AI-DEV-188 remains `IMPLEMENTED_PENDING_NATURAL_VERIFICATION` until natural TW 07:00, TW 13:35, TW 15:00 and US 06:30 prove the new contracts. AI-DEV-185/186/187 retain their independent natural-verification requirements.

## Rollback and known limitations

Rollback restores only the controlled static-publish backup. Immutable snapshots and runtime history are never rolled back or edited. Historical snapshots lacking new metadata use safe fallback semantics; they are not backfilled.
