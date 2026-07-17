# TW 07:00 Structured Decision Payload V1

## Purpose

AI-DEV-184 makes the admitted TW `pre_open_0700` snapshot the single immutable source for Archive Latest, the active TW Dashboard alias, Email, LINE provenance, and Operations diagnostics. It does not alter scheduler cadence, approval, archive revision semantics, or any other window.

## Root cause

The Google Sheet universe and `app/pipelines/pre_open_pipeline.py` produced nine per-stock analyses and legacy report text, but the producer did not persist `artifacts/runtime/tw_window_decision/pre_open_0700_latest.json`. `approved_pre_open_delivery.py::_window_runtime()` therefore returned an empty object because no market/window/run-id-matched window runtime existed. Snapshot construction inferred `cards=[]` and `tracking_stock_count=0`; admission accepted that provenance-valid but content-empty payload. The renderer correctly displayed an official empty state. The loss occurred between the producer and window runtime, before admission and rendering.

## Source of truth

The production producer writes one atomic `tw_pre_open_decision_runtime_v1` artifact. Its authoritative collection is `structured_pre_open_cards[]`; `cards` is a compatibility view of the same list, not an independently built collection. The scheduled wrapper copies this collection and its deterministic summary into the immutable snapshot. Renderers and notification formatters consume the resolver-selected admitted snapshot payload.

## Card schema

Each card preserves `symbol`, `name`, `market`, `window`, `trading_date`, rating/score/action, market/overnight/ADR context, entry readiness/condition/zone, stop/target/risk-reward, chase/gap/event risk, technical/chip/news/fundamental summaries, reasoning, risk and no-trade reasons, availability, missing fields, data freshness, deterministic ranking fields, and a per-card source hash.

No entry, stop, target, fundamental, gap, event, or freshness value is invented. When the existing producer has no safe value, the field explicitly says it is unavailable or awaiting confirmation.

## Partial and unavailable data

Optional source loss retains the stock identity and card. A card is `partial` when basic market data exists but named enrichment is unavailable. It is `unavailable` when basic market data cannot support a safe decision. Missing CSV or analysis failure creates an unavailable card with a sanitized reason; it does not remove the symbol from the tracking universe. Cross-window and prior-runtime fill are prohibited.

## Admission invariants

For a structured TW 07:00 payload:

- `tracking_stock_count == len(tracking_symbols)`
- tracking count equals structured and rendered card counts
- card symbol order equals tracking symbol order
- symbols are unique
- every card is `TW / pre_open_0700`

Any structured payload that violates these rules is rejected with `structured_pre_open_payload_invalid`. In particular, `tracking_stock_count > 0` with zero cards cannot become a successful snapshot. Existing immutable history is never rewritten.

## Ranking and summary

Summary counts and groups are recomputed only from structured cards. Ranking is deterministic: entry readiness, risk-adjusted score, event risk, chase risk, then symbol. Groups are Top opportunities, Watch/wait, No-trade, High chase risk, and Unavailable. Email, LINE, Archive, and Dashboard use these same groups and ordering.

## Data freshness

Each card keeps separate market-data, technical, news, chip, ADR, fundamental-period, and report-generation timestamps. A missing source timestamp remains unavailable; report generation time is never substituted for source time. Python date/datetime representations are normalized before presentation.

## Dashboard, Email, LINE, and Operations parity

Archive and the active TW Dashboard render the resolver-selected immutable payload. The 07:00 page leads with decision summary and nine cards; provenance and revision remain secondary immutable metadata. Email presents market context, Top 3, avoid/chase risk, freshness, and the canonical archive URL. LINE is a concise projection of the same summary. Delivery provenance retains snapshot ID, revision, source payload hash, separate presentation hash, result, and anonymous recipient count. Operations adds tracking, structured, rendered counts and `structured_payload_status` for this window only.

## Cross-window isolation

The new producer/builder and renderer mapping are restricted to `TW / pre_open_0700`. The shared admission and Operations helpers are conditional on that exact identity. TW 13:05, 13:35, 15:00 and all US windows keep their schemas, routes, outcome rules, renderers, and notification contracts. Existing seven-window, archive, manual-revision, runtime-budget, outcome-exclusivity, Landing, and URL gates remain mandatory.

## Controlled verification

Validators create a temporary nine-symbol production-shape payload, temporary archive, immutable Archive HTML, and TW renderer output. They format Email/LINE and delivery provenance with no send. Cases cover partial data, zero cards, duplicate/wrong symbols, fixture rejection, and six non-target admissions. They do not run the production pipeline, publish `/var/www`, send notification, write production archive, trade, or execute `main.py`.

## Natural verification

The next natural 07:00 run must prove scheduler trigger, pipeline completion, nine tracked symbols, nine structured cards, runtime persistence, admission, public Archive/TW alias identity parity, and Email/LINE source-hash parity. Until then the closure state is `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`. The following natural runs of the other six windows must also be observed for title, counts, identity, canonical URL, and delivery provenance stability.

## Controlled publish

Static publish is allowed only after merge, CI, post-merge validation, and controlled no-send gates. It may rebuild only from an already admitted valid snapshot and requires rollback backup and public identity verification. The current legacy empty 07:00 snapshot must not be fabricated, backfilled, mutated, or presented as nine cards; if no valid structured snapshot exists, skip the 07:00 publish and wait for the natural batch.

## Rollback

Revert the implementation commit and rebuild static pages from the last admitted immutable snapshots. Do not delete or rewrite archive history. If the producer fails after rollback, preserve the failure/runtime evidence and retain the last verified public identity rather than publishing a partial snapshot.

## Known limitations

The existing pre-open analysis produces several decision fields only as narrative text, so fields without safely structured upstream values remain explicit unavailable/confirmation-required values. This task does not introduce a new entry/stop/target algorithm or backfill historical snapshots. Full production closure requires the next natural 07:00 observation.
