# AI-DEV-212 H2 Research Attribution, Finalized News Truth & Counter-Argument Closure V2

Task ID: AI-DEV-212-H2

Status: `IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION`

## Repository

- Starting main: `7f38122d60a32be74557d6f3780a028207375508`
- Branch: `ai-dev/212-h2-research-attribution-finalized-news-counter-v2`
- Implementation commits / PR / CI / merge main: recorded in the final post-merge handoff.
- Starting main/origin-main: `0/0`; open PRs: `0`.
- Existing runtime/generated state: 189 entries including ignored artifacts, fingerprint `7791c3df0265f082f4069fe258aadf1dd7157ceb0d8d63ba2379605bb78b2f08`; preserved and not staged.

## Controlled-QA root causes

1. `us_entity_attribution_v2` treated provider related-ticker metadata or a title alias too optimistically. A macro/index multi-ticker roundup could therefore become GOOGL company evidence.
2. RRE had a correct finalized selection, but `dashboard_card`, `bilingual_news_snippet` and other compatibility surfaces could still select directly from provider/material-news inputs. This produced different primary headlines and contradictory absence states.
3. presentation code inferred `STALE_ONLY` from normalized>0 and fresh=0 even when no stale rejection existed. SPCX discovered-but-filtered evidence was therefore mislabeled as stale.
4. the research ownership boundary was placed in `counter_argument`. It accurately constrained market context but did not test the company/event thesis mechanism.

The immutable controlled revision 3 (`dab332baa2b75f00a7957b31cfcf6b7155d8725d36e4985d2f9eb820776e0843`) was used only as pre-fix shape evidence and was not rewritten, republished, recaptured or claimed as post-H2 verification.

## Entity attribution V3

`us_entity_attribution_v3` records `PRIMARY_SUBJECT`, `MATERIAL_CO_SUBJECT`, `CONTEXTUAL_MENTION`, `MARKET_ROUNDUP`, `AMBIGUOUS` or `REJECTED`, plus reason, matched/competing entities, related-ticker metadata, primary subject, relationship type and quality.

- GOOGL + CPI/S&P/Nasdaq multi-ticker roundup: rejected as company evidence.
- GOOGL + Pixel/Gemini product event: primary subject retained.
- TSM + ASML capacity relationship: material co-subject retained.
- NVDA + Verizon partnership: material co-subject retained.
- summary-only ticker co-mention: rejected.

This closes the known false positive without eliminating deterministic supplier/customer/partnership recall.

## Finalized news source of truth

`finalized_current_news_projection_v2` owns selected items, primary item, counts, state, reason and PM label after bounded RRE selection. Dashboard, institutional research, material-news compatibility, bilingual snippet, Email and rendered artifacts consume or project from this contract. Compatibility values identify `compatibility_source = finalized_current_news_projection_v2`.

Semantic parity validation fails when canonical primary A becomes legacy primary B, `AVAILABLE` becomes no-news, or filtered evidence becomes stale-only. Compatibility consumers no longer reorder or select from raw provider inputs.

## Absence-state contract

The canonical distinctions are `AVAILABLE`, `NO_RELEVANT`, `RETRIEVAL_FAILED`, `STALE_ONLY`, `DISCOVERED_BUT_FILTERED`, `ADMITTED_NOT_SELECTED` and `SELECTED_NOT_RENDERED`. `STALE_ONLY` requires an actual stale rejection. SPCX-style attribution/quality filtering renders “有取得新聞，但未通過個股相關性／品質篩選,” not “僅有過期新聞.”

## Counter-argument architecture

The research boundary and counter argument are separate:

- boundary: market/sector context may confirm but cannot establish company direction;
- counter: tests the evidence mechanism and names its uncertainty.

Deterministic families cover earnings/guidance quality, regulatory remedies and timing, product/demand supply-side alternatives, contract/partnership revenue conversion, capex/supply-chain utilization, management/capital execution, filing materiality and material-event persistence. Every narrative includes event family, mechanism, uncertainty family and evidence reference. No artificial negative evidence is created.

Six-symbol replay confirms AAPL deal execution, NVDA partnership-to-revenue conversion, TSLA supply/scheduling alternatives, GOOGL product evidence over market roundup, SPCX filtered/no-relevant truth, and TSM capacity/utilization risks.

## Deterministic QA

The dedicated ACTIVE leaf validator covers cases A–W, including precision/recall, dual-truth mutations, stale-state invariants, event-specific anti-template checks, market-only direction, directionless 0/0 contribution, six-symbol replay, real-Chromium CJK PNG/PDF, coverage projection parity, Decision safety and AI-DEV-211 transport regression.

Existing AI-DEV-212 and AI-DEV-209 H3 validators pass after the contract change. Full registry, CI and post-merge execution counts are recorded in the final handoff.

## CJK and Decision safety

The existing Noto Sans CJK TC Chromium runtime, glyph diagnostics, PNG/PDF hash integrity and published-DOM immutability remain unchanged and pass regression. Research remains read-only: strategy, scoring, prediction weights, ranking, eligibility, Action, Entry, Stop, Target, sizing and execution are unchanged.

## Safety

- Production pipeline / controlled rerun: not executed.
- Publish / LINE / Email: not executed.
- Trading/orders: false.
- Scheduler/cron/systemd/nginx/firewall: unchanged.
- Secrets accessed: false.
- Production DB written: false.
- Immutable archive rewritten: false.
- Existing runtime/generated artifacts cleaned or staged: false.
- AI-DEV-211 transport architecture: unchanged.

## Controlled and natural verification

After merge, a fresh controlled US `us_pre_market_2000` revision must confirm GOOGL attribution, SPCX absence truth, canonical/legacy headline parity, differentiated counters, company-direction ownership, readable CJK artifacts, coverage parity and unchanged Decision output. Only a later eligible scheduled lifecycle can provide natural verification.

## Final status

`IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION`
