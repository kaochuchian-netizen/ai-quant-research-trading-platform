# TW 15:00 Structured Review Payload Consistency V1

## Incident and root cause

The scheduled 15:00 runner admitted the window snapshot before it built the formal prediction-review runtime. Email was then composed after that build from the mutable formal review artifact, while archive and market Dashboard rendered the earlier immutable payload. A legacy report normalizer also inserted a 2330 contract sample when cards were absent. The result was a nine-stock Email aggregation and a one-card sample archive page.

## Source of truth

`formal_prediction_review_runtime_latest.json` is joined only with the matching `tw_window_decision/post_close_1500_latest.json`. The resulting `tw_post_close_structured_review_v1` payload contains `structured_review_cards`, outcome counts, tracking/rendered counts, review content hash, effective batch time, source-data time, and generated time. It is copied into the immutable snapshot before admission. Email, LINE preview, archive Latest, market Dashboard alias, and Operations identity use that admitted snapshot.

Each card preserves stock ID/name, Outcome, Direction, Trigger, Stop, Target, Result, Review, Next Action, review evidence, and the matching daily tactical context. Missing review values remain pending; no other window is queried.

## Production ordering

For a successful `post_close_1500` run the approved runner now performs: pipeline completion, formal review build, structured review projection, snapshot admission, route/dashboard publication, then delivery formatting. The later artifact-wiring stage does not rebuild the review artifact a second time. Other six windows retain their existing flow.

## Rendering and empty state

The 15:00 renderer reads only `structured_review_cards`. A snapshot without that field displays the official empty state: the formal Review Payload has not been established, no cross-window value is used, and no example/test data is rendered. Historical immutable snapshots are not rewritten. Production archive pages must never synthesize a sample card.

`tracking_stock_count` must equal both `rendered_review_card_count` and the number of review-card DOM nodes. A mismatch is a merge-gate failure.

## Email, LINE and ranking

Email and LINE counts are recomputed from the structured cards. Representative rows are ordered by Hit, Pending, Fail, Not Triggered, then No Trade; rating and score are not 15:00 primary ranking inputs. Delivery links use `/dashboard/archive/tw/post_close_1500/latest/index.html`.

Time labels are separate: effective trading date, effective 15:00 batch time, market-data time, and report-generated time. A mutable global runtime timestamp or file mtime is never presented as market-data time.

## Identity and validation

Snapshot ID, revision and payload hash are emitted by both the market Dashboard alias and archive route. Operations rows expose the same identity markers. The deterministic validator creates two temporary admitted trading dates, verifies nine cards with Hit 2 / No Trade 5 / Pending 2, builds all routes, executes the scheduler-equivalent dry-run entrypoint, and deletes its temporary archive.

Run `python scripts/orchestrator/validate_tw_post_close_review_payload_consistency_v1.py --pretty` plus the repository regression matrix. Controlled verification must keep Email and LINE unsent, trading false, scheduler unchanged, and must not execute `python3 main.py`.

## Rollback

Rollback the implementation commit and perform the normal controlled static publish from the prior source revision. Do not delete or rewrite runtime/archive evidence. A historical snapshot lacking structured cards remains an explicit official empty state until a subsequent successful scheduled 15:00 batch naturally creates the first structured snapshot.

## Known limitation

Existing immutable snapshots are intentionally not backfilled. Their archive pages become honest empty states rather than sample content. Full Review Cards begin accumulating with the first successful production 15:00 batch after deployment.
