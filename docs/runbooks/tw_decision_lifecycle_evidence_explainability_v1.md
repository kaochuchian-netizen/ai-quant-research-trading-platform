# TW Decision Lifecycle Evidence & Public Explainability V1

## Scope

AI-DEV-194 fixes lifecycle ownership, evidence admission and public explanation for the TW 07:00 → 13:05 → 13:35 → 15:00 chain. It does not change strategy, factor weights, scoring, entry rules or ranking.

## Root causes

- The observed-card adapter inferred `active` from the presence of Entry/Stop/Target levels, so a 07:00 watch card could be promoted at 13:05.
- Price-zone contact was mapped to `triggered` before volume, eligibility, direction and risk evidence were admitted.
- Proximity could map a pre-entry card to `reduce`, even though no position existed.
- Each producer copied an existing timeline and appended the prior window again, producing duplicate 13:05 and 13:35 transitions.
- The 15:00 renderer used the legacy pending outcome for next-action text even when the canonical trade outcome was `open_at_close`.
- Prediction rendering exposed only the enum and actual range, without the predicted range or deterministic reason.

## Source-plan ownership

Only the admitted 07:00 snapshot creates a plan. `canonical_plan_owner` preserves its window, effective date, snapshot ID, revision, hash and plan status. Later windows may observe an active plan, but may not promote `watch` or `no_trade`. Watch cards retain a monitoring range and do not expose formal Entry/Stop/Target fields.

## Trigger evidence gate

`trigger_evidence` contains price, volume, eligibility, direction and risk components. `trigger_evidence_complete` is true only when all five components are complete. Price contact without all evidence remains a waiting state (`wait_volume`, `wait_event`, `wait_confirmation`) and is not a formal trigger.

## Pre-entry action

Before a formal trigger, the allowed public lifecycle actions are wait, cancel, wait for volume, wait for event evidence and recheck. Reduce-risk wording is reserved for an entered position.

## Transition evidence and timeline

Entry, stop, target, invalidation and exit evidence preserve time, source window, source revision, evidence provider and source snapshot identity. Timeline projection keeps at most one transition per window and prefers an admitted snapshot identity over an awaiting-admission placeholder.

## Open at close

With complete evidence and neither target nor stop reached, `open_at_close` means the trade is still active at the close. Public wording states that the trade continues, that target and stop remain untouched, and that tracking continues the next day. It is not described as missing data.

## Prediction explainability

Each review projects predicted range, actual range, localized result and a deterministic overlap reason. Machine-readable enums remain in the canonical payload but are localized at presentation boundaries.

## Market time

Public cards distinguish market-evidence time, provider update time and the exchange close time. This prevents a provider timestamp from being mistaken for the exchange session boundary.

## Channel parity

Dashboard, Email, LINE, Archive and Operations consume the canonical lifecycle card and aggregate. Formatters do not infer a different plan status or trigger count.

## Controlled verification

The AI-DEV-194 deterministic validator covers watch non-promotion, full trigger evidence, pre-entry action, traceable transitions, open-at-close wording, prediction explanation, timeline deduplication, localization and market-time labels. Natural snapshots are replayed read-only; production artifacts and immutable history are not changed.

## Natural verification

The task remains `IMPLEMENTED_PENDING_NATURAL_VERIFICATION` until the next natural TW 07:00, 13:05, 13:35 and 15:00 chain confirms ownership, evidence, transitions and five-channel identity parity.

## Rollback

Revert the AI-DEV-194 implementation commit through the normal branch/PR process and rebuild presentation only from resolver-selected admitted snapshots. Never rewrite immutable snapshots.

## Known limitations

The current transition records bind to the admitted source snapshot available when the downstream card is built. The current window records `awaiting_snapshot_admission` until immutable admission assigns that window's external snapshot identity.
