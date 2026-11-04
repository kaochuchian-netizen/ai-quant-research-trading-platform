# AI-DEV-294 Technical-First Decision Architecture

Status: IMPLEMENTED_PENDING_NATURAL_VERIFICATION. No merge, deployment, notification, trading or production write is part of this change.

## Dependency and scope

This is a stacked change on AI-DEV-293 PR #372, commit `c7ff67f7eeda4869e2c1542a3f3991972522b07e`. The production baseline remains `3368cc50de2745800dff38ec8ce0c2ea56e7f3e4`. PR #372 is still open; this PR does not independently deploy its fixes. CI uses the actual PR base SHA and also runs for `ai-dev/**` targets. The historical AI-DEV-226 blanket strategy-path guard recognizes only the exact optional-news coverage exclusion authorized by AI-DEV-294: reversing that edit must produce an identical source AST to main. Any additional risk, weight, geometry or strategy change still fails; negative regression checks enforce this bound.

## Root cause and historical evidence

The November 2 snapshots are inspected as immutable evidence. No current Sheet, price or article is inserted into them.

| Market / symbols | Proven observation and cause | Unresolved evidence |
| --- | --- | --- |
| TW: 2330, 009816, 2337, 2353, 6873, 4743, 2305, 00878, 1409, 3293 | All frozen company names are blank. The original news path raises `ValueError` on missing identity before aggregation. Saved diagnostics report `AGGREGATION_FAILED` / `ValueError`, with no admitted article. The handler incorrectly claimed source attempts; later presentation incorrectly reduced failure to no relevant news. PR #372 repairs dynamic identity handling and acquisition reporting. | Original Sheet row/header evidence is absent. The upstream reason names were blank remains UNKNOWN. Individual publisher fetch, robots, parser or Selenium failures cannot be inferred from this batch. |
| US AAPL | 28 discovered / 17 metadata-admitted: 4 `NewConnectionError`, 13 article-budget failures | Underlying network errno/traceback not retained |
| US NVDA | 30 / 19: 11 connection failures, 8 budget failures | Same |
| US TSLA | 30 / 12: 7 connection failures, 5 budget failures | Same |
| US GOOGL | 24 / 6: 4 connection failures, 2 budget failures | Same |
| US SPCX | 9 / 0: metadata filtered; no qualifying saved article | Body attempts on filtered candidates unverified |
| US TSM | 28 / 1: 1 budget failure | No qualifying body |

US totals: 149 RSS candidates, 55 surviving metadata admission, 26 recorded connection errors and 29 exhausted body budgets. CNYES and Yahoo discovery each recorded zero candidates for all six symbols. This is not evidence of a robots, TLS, browser, DOM or publisher-ban cause. AI-DEV-294 moves metadata rejection ahead of the existing bounded body budget and preserves discovery/fetch/parse/admission/publish records even for rejected candidates. It does not bypass robots, rate limits or access restrictions. Network reliability and future natural discovery coverage remain unverified.

Snapshot file SHA-256:

- TW: `299ce59eddaa8d1cf9da84c5c7b23b3484a5e69e5cd9665a69b6773d02d42945`; snapshot ID `1e2258e755eba7f64e96c8cfab4ba76324af79ccfbf0224743ea23aafe777884`.
- US: `4de98e4bb4746c9461d5e03c2e9de7bdd159c2372fbc9eea0be22cbef902e96c`; snapshot ID `0c5cb3380ca711de73cec8f266dc747392bcecb2b82fcc74d12ed48aa0d52d23`.

Detailed per-symbol stage evidence, JSON pointers and file hashes are in the task workspace's `audit-evidence/ai-dev-294/ROOT_CAUSE.json`.

## Decision contract

`app/prediction/technical_first.py` defines three pure boundaries and the versioned `technical_first_decision_v1` record. Native market adapters remain responsible for indicators and existing action gates.

| Boundary | Contract |
| --- | --- |
| Technical Base | Stores symbol, market, as-of, target session, market-data timestamp, indicator values, native prediction, confidence, Entry/Stop/Target, RR and eligibility. `base_id` hashes the complete immutable base. No optional news score enters this calculation. US normalizes the existing technical/market/volatility weights; TW uses native price/MA/ATR and technical completeness. |
| News Adjustment | Requires persisted substantive body, hash, at least two attributable facts, frozen company identity, publication/update timestamps and the market-specific as-of window. Headline, wrong-company, stale/future and unverified content stays rejected. Records evidence independently of technical usability. |
| Final Decision | `DATA_BLOCKED` if technical inputs fail. Otherwise `TECHNICAL_ONLY` without qualified articles or `TECHNICAL_PLUS_NEWS` with them. Base remains unchanged. No calibrated news effect exists yet: direction, range and confidence are unchanged. A qualified explicit high-risk event may veto a plan; it cannot create a plan. |

No news means `UNAVAILABLE` (failed or unverified acquisition) or `NO_RELEVANT_NEWS` (completed acquisition without qualifying content), with `event_risk=UNKNOWN`. Qualified body evidence without quantified risk means `UNQUANTIFIED`, never zero risk. Confidence is a technical heuristic, not a calibrated probability.

`technical_research_usable`, `news_evidence_usable` and `combined_research_usable` are independent. Combined requires both; news failure continues to fail the news evidence check while technical analysis can pass. The natural acceptance auditor exposes these separately and rejects altered decision hashes.

Existing price freshness, native premarket age, direction/setup, chase/Gap, confidence and RR thresholds remain. Invalid technical data clears executable geometry and forecast outputs. News exceptions in acquisition/research cannot erase valid OHLCV. All channel formatters share the same status renderer. TW aggregate confidence uses the new technical bases when present, so optional news absence cannot reduce that score.

Later US windows retain immutable origin decisions; current technical observations are stored separately and do not replace an inherited trade plan. Postclose ablation requires the selected admitted 20:00 archive hash, exact symbol/session, complete outcome, and outcome time after forecast cutoff. TW observed windows retain the frozen 07:00 decision. The 17:00 learning artifact stores paired technical/final metrics without changing weights.

## Verification and limitations

| Area | Result / evidence |
| --- | --- |
| Four fault scenarios | Synthetic regression runs native US builder and three channel previews for valid news, no news, news failure and stale prices. Separate TW builder tests prove optional-news invariance and stale-price blocking. Synthetic tests are never natural acceptance evidence. |
| Frozen real-input replay | `scripts/orchestrator/verify_technical_first.py` validates snapshot/observation hashes, uses native TW tactical/card and US premarket builders, and writes only a fresh isolated directory. Socket/subprocess access and writes outside that directory are denied. `rerun-003/REPORT.json` records ordered universe and exact decision-status parity for all 16 stocks. |
| Replay result | TW 10/10 technical usable, news unavailable; US 6/6 technical usable, five unavailable and SPCX no relevant news. No stock has qualified historical news; combined research remains false. This does not mean all stocks have an executable trade plan. |
| Replay limits | TW starts from frozen technical features, not original raw OHLCV. US frozen observations contain high/low/close but no volume; volume remains unavailable. Provider acquisition and formal delivery were not replayed. Forecast outputs are counterfactual isolated calculations, not original delivered predictions. |
| Live source probe | On 2026-11-03, current read-only CNYES probe retrieved TW 6438: 680 body characters, published 2026-11-02 12:48:55Z, and US AAPL: 1,942 characters, published 2026-11-03 02:00:09Z. Both retained company-attributed facts and passed article admission. TW 2330 returned `ReadTimeoutError`. `live-probe-network.json` contains URLs, titles, timestamps, body hashes and facts. These are probe cases, not Sheet universe coverage, and are not inserted into the November 2 replay. |
| Backtest / learning gain | UNKNOWN. The old snapshots have no separately frozen base/final pairs. New evaluator supports paired range error, native direction horizon and frozen-cutoff holdout. It refuses missing identity, changed hashes, wrong sessions, incomplete/early outcomes and calibration overlap. US one-month direction is not scored against one day. No improvement, win rate or causal news gain is claimed. |
| Channels | Preview parity is checked. Formal LINE/Email delivery is not exercised; no receipt or delivery success is inferred. LINE quota restrictions remain external blockers and are not bypassed. |
| Governance incidents | `PROVENANCE_GOVERNANCE=UNKNOWN` and `HISTORICAL_INTEGRITY_UNVERIFIABLE` remain independent. A new baseline cannot prove old artifact integrity. |

Live probe references: [TW 6438](https://news.cnyes.com/news/id/6644200), [US AAPL](https://news.cnyes.com/news/id/6644734), [TW 2330 timeout](https://news.cnyes.com/news/id/6641359). These references establish only what was observed at probe time, not future availability or independently verified financial claims.

## Natural acceptance after separately approved deployment

For each TW/US frozen universe entry, verify base/decision hashes, price timestamp and native risk reasons; article stage counts and evidence; separate technical/news/combined usability; unchanged base under optional-news failures; identical final decision across Dashboard/Email/LINE; immutable originating session for postclose metrics; and the same pairs recorded by 17:00 learning. Receipts must distinguish transport acceptance, recipient acceptance and delivered/unknown. Insufficient LINE quota remains blocked, with no resend. Accumulate untouched future sessions under a policy frozen before the holdout cutoff before making an out-of-sample improvement claim.

Local test/validator logs and evidence manifest are retained in `audit-evidence/ai-dev-294/`; see that directory's `REPORT.md` for final commit, CI, hashes and unresolved checks.
