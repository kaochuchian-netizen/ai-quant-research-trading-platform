# AI-DEV-293 QUALITY_MATRIX

Status: IMPLEMENTED_PENDING_NATURAL_VERIFICATION. One feature branch/PR; no merge or production deployment authorized. Baseline: `3368cc50de2745800dff38ec8ce0c2ea56e7f3e4` (GitHub main and read-only Production HEAD). Code acceptance, deployment state, provenance, natural-batch acceptance and channel delivery are independent.

## Immutable incident and root cause

2026-11-02 TW 07:00 snapshot `1e2258e755eba7f64e96c8cfab4ba76324af79ccfbf0224743ea23aafe777884`, file SHA256 `299ce59eddaa8d1cf9da84c5c7b23b3484a5e69e5cd9665a69b6773d02d42945`. Ordered symbols: 2330, 009816, 2337, 2353, 6873, 4743, 2305, 00878, 1409, 3293.

All ten frozen identities have empty name/English name/aliases. `analyze_news(company=...)` raises before calling the aggregator, so the common failure is unresolved identity, not ten proven publisher-body failures. The handler erased the reason to ValueError/AGGREGATION_FAILED and falsely listed RSS/CNYES as attempted. The presentation failure-code set then omitted AGGREGATION_FAILED and displayed NO_RELEVANT. Per-symbol evidence for all ten is retained in the local incident report and new machine audit. No candidates, URLs, HTTP results or bodies were saved; publisher blocks, robots, timeout, Selenium, lazy-load and parser failures **cannot be attributed to that historic attempt**.

The raw historical Sheet rows/header revision were not retained. Whether names were absent upstream or used an unsupported header remains UNKNOWN. The parser omitted `stock_name`; adding that alias repairs a reproducible parser defect, not proof of the historical Sheet header. Future reads retain header names, normalized enabled/disabled entries and raw-row digest. Missing TW identities can use the already authorized Shioaji instrument contract with exact symbol match, observed time and response hash before freezing. Local hardcoded display-name maps are explicitly rejected for research identity. Historical readers never call this resolver.

## Defect and acceptance matrix

| Module | Observed status | Confirmed root / scope | Repair and acceptance evidence |
|---|---|---|---|
| TW Sheet identity | FAIL, P1 | Frozen identities empty; `stock_name` unsupported; raw history absent | Aliases, headers, disabled rows, source digest; authoritative contract-only missing identity resolution; tests 293 |
| US Sheet2 | UNKNOWN natural | Shared normalization supports enabled/market/aliases; actual current rows not read | Existing 292 dynamic universe tests; no static universe replacement |
| Historical snapshot universe | FAIL, P1 | Nested `stock_universe_evidence.batch_universe` overlooked by historical reader/fallback | Prefer exact nested frozen universe; never infer names from later display cards |
| TW acquisition diagnostics | FAIL, P1 | Pre-query identity error collapsed and falsely reported as source attempts | Explicit identity stage, zero attempted providers; ALL_SOURCES_FAILED retained |
| TW failure presentation | FAIL, P1 | AGGREGATION_FAILED omitted from failure states | RETRIEVAL_FAILED propagates; no false no-news claim |
| Shared TLS transport | FAIL, P1 | Pinned urllib3 transport omitted requests CA trust bundle; live SSLError | Explicit verified CA bundle, hostname/SNI and IP pinning retained; real CNYES bodies retrieved |
| HTML body | FAIL, P1 | Meta description counted as body | Metadata excluded; headline-only regression |
| TW article gate | FAIL, P1 | Prior TW relevance gate did not require shared attributable factual evidence | Current publisher body/time fetched under bounded robots policy, same factual gate, immutable historical refetch forbidden; candidate rejection survives formal contract |
| Source access / robots | FAIL, P1 | TW HTTP and production Selenium navigation lacked robots permission guard | Cached public robots permission; production browser guard; deny-before-navigation test; no auth/paywall evasion |
| US article freshness | FAIL, P1 | Shared assess only checked future cutoff | 96h maximum age plus existing market window gates; stale/future rejection tests |
| AI research | UNKNOWN quality | Historic batch skipped all research; no admitted articles | Only qualified article facts enter prompt; bounded excerpts/hashes retained. Actual subsequent model synthesis quality still requires natural evidence |
| US prediction | FAIL, P1 | Event multiplier applied twice in next-session width | Apply once; numerical regression (100 price, 2% range, high event =>102.78 upper bound); scoring/risk thresholds preserved |
| TW prediction | PASS limited / UNKNOWN quality | Prior-close OHLCV direction/range align across frozen/public surfaces; news unavailable | Existing 292 incident comparison, frozen inputs only. Accuracy/confidence calibration not proven by parity |
| Entry/Stop/Target | PASS preservation / UNKNOWN efficacy | Existing RR/setup/ATR/gap rejections remain | No threshold changed; historical six-US-card 292 parity regressions retained |
| TW15 / US0630 origins | PASS code / UNKNOWN natural | Review must resolve immutable origin, not current Sheet | Existing 283–292 tests and read-only historical input copies; no rerun or synthetic natural acceptance |
| 17:00 learning | UNKNOWN improvement | Prior immutable artifact records abstention controls; no evidence of improved out-of-sample accuracy | Future capture failures now retain sanitized prerequisite category; learning policy/weights unchanged |
| Dashboard | PASS TW07 identity | Actual saved public HTML identity/order/direction/range matched ten cards | Original real report retained; later repaired release still pending natural verification |
| TW07 Email/LINE receipts | FAIL, P1 | Sender invoked without shared receipt root; recipient outcomes discarded | Per-recipient masked transport receipts retained; outer legacy suppression preserved; sent never proves final delivery |
| LINE quota | BLOCKED_BY_QUOTA | Supplied exhaustion constraint; no current authenticated quota probe performed | No resend, token change, plan change or bypass; old 200/200 not asserted as current measurement |
| Scheduler / locks | PASS schedule observation / UNKNOWN full resources | Existing five cron windows observed; no scheduling mutation | Read-only preflight; lifecycle/overlap tests. Full runtime resource coverage cannot be inferred from static cron |
| Natural acceptance | FAIL TW07 / UNKNOWN later windows | Missing body and research evidence cannot be recreated | New read-only machine auditor reports per-symbol reasons, counts, factor/receipt unknowns; nonzero on FAIL/UNKNOWN |
| Provenance governance | UNKNOWN | External 10/31 07:22:58 ff-only identity/authorization linkage unproved | Independent event retained; no reclassification |
| Historical integrity | UNKNOWN | Original pre-sync hashes absent | HISTORICAL_INTEGRITY_UNVERIFIABLE retained; new hashes are not old-baseline proof |

## Real live source coverage

Current read-only probes are separate from historical predictions. CNYES robots permission was checked; request/time/size/TLS limits retained. No current article was inserted into a historical snapshot.

- TW `https://news.cnyes.com/news/id/6631156`: 466 body characters, 2026-10-15 publication, OUTSIDE_NEWS_WINDOW.
- US `https://news.cnyes.com/news/id/6552521`: 2,560 body characters, 2026-07-31 publication, OUTSIDE_NEWS_WINDOW.
- TW `https://news.cnyes.com/news/id/6641359`: 1,456 body characters, 2026-10-30 publication, INSUFFICIENT_ATTRIBUTABLE_EVENT_FACTS. Body availability is not research acceptance.
- US `https://news.cnyes.com/news/id/6641299`: 1,748 body characters, 2026-10-30 publication, ATTRIBUTABLE_FACTS_VERIFIED for Intel identity. This probe company is not asserted to be in the formal Sheet universe.

Exact titles, timestamps, URLs, factual excerpts, locators, content hashes and rejection reasons are in `audit-evidence/ai-dev-293/live-probe.json` in the audit workspace. These four bounded probes do not establish exhaustive TW/US/Yahoo/RSS/IR/SEC coverage. Google opaque redirect, publisher restrictions and unavailable official evidence remain explicit external coverage gaps; no bypass was added.

## Verification and evidence

Audit workspace sibling `audit-evidence/ai-dev-293/`: `preflight.txt`, `readonly-inputs.tar.gz`, `readonly-inputs/`, `tw-natural-quality.json`, `historical-window-quality.json`, `live-probe.json`, `final-tests.txt`, `new-tests.txt`, `governance.json`, `source-inventory.json`, branch validation logs and final hash manifest. Historical incident references: `audit-evidence/ai-dev-292-acceptance/observations/20261102T083051/REPORT.md`, `per-symbol.json`, `NOV02-NATURAL-ACCEPTANCE.md`.

Existing 180 CI unit/integration tests passed including isolated browser/HTTP E2E; ten new regression cases added. Governance and source-inventory audit pass. Full branch/remote CI results are recorded after the final commit; local macOS-only fixture/path/process differences are not represented as production faults. Two old protected-function validators now permit exactly the duplicated-multiplier removal while retaining all other AST protection. A parser fixture gained actual body text after removal of its metadata length subsidy; the content threshold was not lowered.

## Required natural acceptance after separately approved deployment

Verify unchanged approved source SHA and immutable universe hash/order. For every enabled symbol retain discovery attempts and source-specific failures, publisher publication/update times, content hash/length, attributable facts and gate reasons. Research must cite admitted facts; prediction factor IDs must point to those facts, or explicitly declare technical-only degradation. Preserve original Entry/Stop/Target gate reasons across all previews and actual channel content. Store immutable source and outcome/learning references; prohibit future/current-news backfill. Check actual Dashboard bytes and per-recipient transport receipts separately from final delivery. Missing evidence is UNKNOWN/FAIL. No test fixture or recreated notification substitutes for a real natural batch.
