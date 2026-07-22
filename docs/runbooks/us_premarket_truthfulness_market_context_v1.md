# AI-DEV-189 — US 20:00 Premarket Truthfulness V1

## Root cause matrix

- Premarket quote fields existed only transiently in the Yahoo adapter. The dashboard card discarded them, so daily `last_price` and generic prose stood in for a real premarket contract.
- SPY/QQQ/SOXX context stored generic prices and was described as premarket context without an extended-hours availability marker.
- Decision Intelligence V4 computed the top-opportunity count from a confidence heuristic, while its list used a separate entry-ready ordering. Renderers and notifications then recomputed their own groups.
- Tactical setup levels were rendered with equal weight for actionable, watch-only, and no-trade symbols. Low confidence and weak reward/risk did not form a centralized gate.
- Earnings, SEC metadata, tactical risk, and news shared an `event risk` label. SEC fallback metadata could also occupy the news presentation slot.

## Canonical flow

`Yahoo extended-hours evidence → normalize_premarket_quote → build_premarket_card → summarize_premarket → immutable snapshot → Archive / Dashboard / Email / LINE / Operations`

Daily OHLCV is never accepted as premarket price or Gap. Missing or stale extended-hours evidence remains `unavailable` and prevents promotion.

## Data and freshness

Each card retains previous close, premarket price/change/change percent, Gap, volume when available, provider timestamp, provider name, freshness, and availability. SPY, QQQ, and SOXX use the same extended-hours rules. A missing timestamp is not replaced with fetch time.

## Eligibility and action gate

Canonical booleans are `candidate`, `entry_ready`, `top_opportunity`, `actionable`, `watch_only`, and `no_trade`. Summary counts and symbol lists are derived only from these records.

The V1 gate requires fresh premarket evidence, reward/risk at least 1.0, confidence at least 35, a bullish tactical direction, a stabilized setup, acceptable chase risk, and no high canonical event risk. A top opportunity must be actionable; actionable and no-trade are mutually exclusive.

Low-confidence or low-RR cards retain an observation zone but do not expose a formal Entry/Stop/Target plan. Re-evaluation wording lists the conditions that must improve.

## Event risk and SEC/news separation

`event_risk.canonical_level` is the only headline risk used by all channels. Earnings, SEC filing, news, and macro sub-risk remain inspectable evidence. An 8-K is not automatically high risk; materiality and item metadata are retained.

SEC evidence and real-time news have separate structures, timestamps, sources, and availability. Missing news is shown as unavailable and never copied from SEC metadata.

## Channel parity

Archive, Dashboard, Email preview, LINE preview, and Operations consume `premarket_summary` and card eligibility directly. Presentation may be shorter, but counts, symbols, event risk, snapshot identity, revision, source payload hash, and canonical URL must remain aligned.

## Controlled verification

The AI-DEV-189 validators use deterministic no-network fixtures for an actionable NVDA-like case, a low-confidence/low-RR TSM-like case, a GOOGL no-trade case, missing premarket evidence, SEC-without-news, risk parity, wording sanitation, and seven-window regression. They do not write production runtime/archive or attempt delivery.

## Controlled publish and rollback

Controlled static publish is allowed only after merge, CI, post-merge gates, no-send validation, governance-safe worktree classification, and rollback backup. It rebuilds presentation only from resolver-selected admitted immutable snapshots. It must not run the production pipeline, send notifications, create/backfill snapshots, or rewrite history. Roll back by restoring the publisher-created backup.

## Natural verification

Status remains `IMPLEMENTED_PENDING_NATURAL_VERIFICATION` until the next natural US 20:00 batch proves real premarket/SPY/QQQ/sector freshness, canonical eligibility parity, event-risk parity, and Dashboard/Email/LINE/Archive/Operations identity parity.

## Known limitations

Provider availability for extended-hours volume and timestamps varies. Missing fields remain unavailable and downgrade action eligibility rather than falling back to daily bars.
