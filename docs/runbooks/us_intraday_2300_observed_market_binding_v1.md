# US 23:00 Observed Intraday Market Binding V1

## Root cause

The natural 2026-07-17 US 23:00 runtime contained observed AAPL quote evidence (`last_price=333.1099`, `regular_market_open=331.98`, `previous_close=333.26`, `volume=20348939`, `market_state=REGULAR`). `dashboard_card()` copied only `price` and the pre-existing daily tactical summary. It did not produce an intraday structure. The Dashboard then hard-coded Gap and Volume as `待盤中量價確認`, while Email reused a generic research reason. The loss point was quote/strategy → Dashboard card, before snapshot admission; Archive faithfully preserved the incomplete card.

## Source of truth

`structured_intraday_cards[]` is the single US 23:00 decision payload. Runtime, immutable snapshot, Archive, active US Dashboard, Email, LINE, delivery provenance, and Operations derive counts and content from that collection. No channel owns a separate classifier.

## Session and freshness semantics

Session phase is resolved in `America/New_York`, so the Asia/Taipei 23:00 run follows US DST automatically. Phases are pre-market, regular session, after-hours, market closed, or unavailable. Weekends are closed; the natural runner's exchange data remains authoritative for exceptional closures. Quote time uses Yahoo `regularMarketTime`, not fetch time or file mtime. A regular-session observation older than 20 minutes is stale and cannot produce an actionable intraday state.

## Observed data and algorithms

- Current price: yfinance `fast_info.last_price`, then `regularMarketPrice`; a daily Close fallback is identified explicitly and cannot silently masquerade as a fresh regular-session quote.
- Gap open: `(regular open - previous close) / previous close`.
- Gap current: `(current price - previous close) / previous close`.
- Gap fill: bounded percentage of the opening gap retraced toward previous close. States distinguish up/down follow-through, partial/full fill, flat open, and unavailable.
- Volume: cumulative session volume divided by historical median daily volume prorated by elapsed regular-session minutes. This conservative fallback is explicitly named `daily_median_prorated_by_elapsed_session_minutes`; it is not described as a precise same-minute baseline.
- Trigger: `not_reached`, `inside_zone`, `triggered`, `passed_without_safe_entry`, `invalidated`, or `unavailable`.
- Stop/target distance: `(level - current) / current`, retaining sign.

## Tactical adjustment

The deterministic states are maintain watch, triggered hold, wait for volume, cancel chase, reduce risk, stop invalidated, target near, no trade, and data unavailable. The rule considers price versus entry, trigger, volume, gap/chase risk, stop and target distance, and event risk. Every result retains an observed reason. Generic `等待止穩` is not a valid structured result.

## Failure and admission safety

Cards are never dropped because one symbol fails. Missing symbols remain with `data_status`, missing fields, source, last available time, and a safe non-actionable explanation. During a regular session, a complete card requires current price, quote time, trigger state, and data status. If all tracked symbols are unavailable/stale/invalid, admission is rejected with `intraday_market_data_all_unavailable`; partial payloads retain all symbols. No cross-symbol, cross-window, prior-day, fixture, or validator fill is allowed.

## Three-window continuity

The 20:00 prediction snapshot now retains its tactical setup. The 23:00 card references that same-session setup and answers whether it was reached, triggered, invalidated, or unsafe to chase. The 06:30 canonical outcome remains owned by AI-DEV-183 and must consume the same setup identity without reclassifying pending as no-trade.

## Channel and Operations contract

Archive and Dashboard show current price/time, gap/fill, volume ratio/baseline method, trigger, stop/target distance, adjustment, reason, and data state. Email uses a short market summary plus per-symbol observations. LINE uses deterministic counts and Top 3 tactical changes. Delivery provenance retains immutable snapshot identity and source hash with separate presentation hashes. Operations retains tracking/structured/complete/unavailable/triggered/volume-confirmed counts and cannot report a green complete state when all cards are placeholders.

## Controlled verification

Validators use only temporary production-shape artifacts and temporary archives. They cover normal regular-session data, up-gap follow-through/full fill, entry zone, unsafe chase, partial/all-source failure, stale data, weekend closure, DST, channel source-hash parity, and the six non-target windows. They do not access `/var/www`, send notifications, trade, alter scheduler configuration, execute `main.py`, or rewrite production history.

## Natural verification

The next natural US 23:00 must prove scheduler trigger, observed quote time, complete tracking universe, structured cards, admission, public Archive/US alias identity, Email/LINE attempt provenance, and absence of generic placeholders when data is available. Until observed, status is `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`.

## Rollback

Revert the implementation commit through normal Git history and rebuild only from admitted immutable snapshots. Never rewrite historical snapshots. If current immutable history uses the old schema, keep its truthful legacy presentation or official unavailable state; do not fabricate observed values.

## Known limitations

The volume baseline is a documented conservative prorated daily-volume approximation because a reliable historical same-minute dataset is not yet retained. US exchange holidays beyond weekends depend on upstream market state rather than a bundled exchange calendar. Both limitations surface as explicit data-state evidence rather than invented intraday decisions.
