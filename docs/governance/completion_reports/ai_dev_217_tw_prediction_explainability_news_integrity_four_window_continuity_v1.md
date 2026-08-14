# AI-DEV-217 — TW Prediction Explainability, News Integrity & Four-Window Decision Continuity V1

## Repository

- Starting main: `4525b035a5912ff58f4b73ac1a2795498cb50ffb`
- Branch: `ai-dev/217-tw-prediction-news-continuity-v1`
- Implementation commits: recorded in the final governance reconciliation after merge
- PR / CI / merge main: recorded in the final governance reconciliation after merge

## Root-cause audit

The 2026-08-14 immutable TW snapshots were inspected read-only. They confirmed six integrated defects:

1. Prediction data existed in `prediction_snapshot_v2`, but later-window cards had no canonical PM projection of progress, deviation, scenario status or lineage.
2. The 13:05 and 13:35 renderers short-circuited `watch` / `no_trade` cards into operational metadata, hiding research-only tactical expectations.
3. Prediction evaluators accepted a reversed interval (`2337: 135.0–126.25`) because they checked presence but not ordering.
4. Technical direction, tactical direction and free-text reasons were not horizon-aware, allowing the same-horizon 2337 bullish/bearish contradiction.
5. RRE independently consumed raw `news_evidence`, while Decision coverage and UI used separate availability logic, producing the observed 0/9 versus selected-news dual truth.
6. CMoney community content inherited a generic source tier and could enter the substantive Research path despite being sentiment-only.

## Prediction contract

`tw_prediction_presentation_v1` now projects one 07:00 prediction identity through 13:05, 13:35 and 15:00. It exposes direction, expected path, today/next-session intervals, support/resistance, bullish/bearish scenario switches, confidence score/band, evidence classes, current progress, close expectation and change from the prior window.

Research/Position and Daily Tactical remain explicitly separate horizons. A cross-horizon difference is allowed and explained; an unlabelled same-horizon bullish/bearish contradiction fails closed. Both legacy and V2 evaluators reject reversed or incomplete intervals before evaluation. The 15:00 aggregate includes deterministic best/worst prediction, largest range/direction error, missed-evidence prompt and tomorrow carry-forward question.

## News contract

`tw_finalized_news_projection_v1` is the shared source for TW RRE and Decision coverage. Source classes are Tier 1 official, Tier 2 reputable media, Tier 3 general/context and Tier 4 sentiment-only. Tier 4 items remain visible as context but have `direction_status=NOT_EVALUATED`, contribute 0 bullish/0 bearish authority and cannot become institutional company evidence.

ETF symbols use ETF-specific event types for constituent changes, rebalances, flows, distributions and index/macro exposure. Official company/MOPS/TWSE evidence and reputable material company news remain eligible, preventing recall collapse.

## Four-window lifecycle

- 07:00 creates the prediction identity, range, path, key levels, scenarios and confidence.
- 13:05 references that identity and reports `on_track`, deviation, breakout/breakdown or invalidation.
- 13:35 preserves the identity, states whether the morning expectation remains valid and explains the change since 13:05.
- 15:00 evaluates the same snapshot, preserves deterministic evaluation ownership and adds quality-review interpretation.

The renderer places prediction direction/path, range, confidence, support/resistance, scenario switches, progress, action ownership and reason ahead of secondary operational metadata. Research-only tactical expectations remain visible when no formal trade plan exists. LINE summary remains compact while adding directional opportunities, strongest bearish risk, largest prediction deviation and meaningful-news count.

## Deterministic and product QA

The dedicated required leaf covers:

- exact 2337 reversed-range rejection;
- 2337 same-horizon trend contradiction rejection and explicit cross-horizon conflict acceptance;
- coherent 6873 range/watch hierarchy;
- full 2337 and 6873 07:00 → 13:05 → 13:35 → 15:00 production-shaped lineage;
- intraday progress, pre-close expectation and post-close evaluation;
- CMoney `準備噴` and `同學風向` Tier-4 restrictions;
- official-news and ETF constituent-change positive recall;
- Decision/RRE news parity mutation rejection;
- post-close quality review;
- real Chromium 1440px full-page PNG and browser PDF with Noto Sans CJK TC glyph diagnostics.

Dedicated fixture result: all checks PASS. Generated visual evidence lived only under a temporary validator root and was removed automatically; no production archive was changed.

## Regression matrix

- AI-DEV-217 dedicated: PASS
- AI-DEV-216: PASS
- AI-DEV-212 H3: PASS
- AI-DEV-207: PASS
- Changed Python compile: PASS
- `git diff --check`: PASS
- Full executable registry / CI / post-merge registry: recorded after workflow completion

## Safety

- Strategy, scoring, ranking, eligibility and action rules: **NO CHANGE**
- Prediction model weights: **NO CHANGE**
- Entry / Stop / Target generation and sizing: **NO CHANGE**
- Trading / order execution: **NO CHANGE**
- Production or controlled rerun: **false**
- LINE / Email sent: **false**
- Scheduler / cron / systemd / nginx changed: **false**
- Secrets accessed or changed: **false**
- Production DB written: **false**
- Immutable archive rewritten: **false**

## Verification status

The 2026-08-14 snapshots are pre-fix root-cause evidence only. They are not post-merge verification. After merge the task remains:

`IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION`

The next eligible verification is a PM-authorized controlled TW four-window lifecycle. Codex did not execute it during this task.
