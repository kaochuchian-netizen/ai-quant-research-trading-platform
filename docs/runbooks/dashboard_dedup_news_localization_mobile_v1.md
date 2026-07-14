# Dashboard De-duplication, News Localization, and Mobile Hotfix

## Background

AI-DEV-177A is a presentation-only hotfix for the multi-market Dashboard. It
does not change strategy engines, scoring, tactical levels, predictions,
runtime calculation, scheduler cadence, notification triggers, trading logic, or
secrets.

## De-duplication Rules

The stock card main surface should show decision information only:

- 今日結論
- 每日短線策略
- 預測
- 中長期研究
- 主要依據
- 主要風險
- 近期新聞與事件
- 策略檢討摘要

Engineering information belongs in collapsed `技術與系統細節`, including
strategy IDs, factor versions, source freshness, score components, factor
coverage, batch window, delivery readiness, and system data status.

If a block only says `資料待接`, `資料不足`, or a metadata phrase, do not render
it as a standalone main card. Fold it into data status or the collapsed
technical section.

## News Layering

Each US card renders `近期新聞與事件` with three layers:

- `重大官方事件`: SEC, company IR, earnings, guidance, official announcements.
- `近期市場新聞`: verified market-reference news from existing runtime fields.
- `新聞資料狀態`: official-event status, market-reference count, and source quality.

The presentation layer must not fabricate news. If no safe headline exists,
state that no safe market-news headline was available and rely on official
filings, earnings, and price data.

## SEC Presentation

SEC forms must be human-readable:

- `10-Q 季報`
- `10-K 年報`
- `8-K 重大事件公告`
- `6-K 海外公司公告`

Raw form codes may appear only as part of these human labels.

## Localization

Dashboard main labels are Traditional Chinese. English is allowed for tickers,
company names, and common finance abbreviations such as SEC, EPS, ETF, ADR,
RSI, MACD, ATR, VIX, SPY, QQQ, AI, and USD.

## Mobile Contract

Mobile layout requires:

- left/right padding at least 16px
- safe-area padding with `env(safe-area-inset-left/right)`
- card padding at least 16px
- grid gap at least 16px
- single-column layout on narrow screens
- `overflow-x:hidden`
- long-text wrapping via `overflow-wrap` and `word-break`

## Email and LINE

Email uses the shared presentation helper and can include detailed Research,
Daily Tactical, Prediction, and news/event summaries.

LINE stays short: research summary, tactical summary, prediction summary, and
Dashboard URL. It should not render the full Entry / Stop / Target / SEC /
News detail set.

## Validators

Run:

```bash
./venv/bin/python scripts/orchestrator/validate_dashboard_dedup_news_localization_mobile_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_decision_data_completeness_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_decision_presentation_uniqueness_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_runtime_to_dashboard_mapping_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_decision_presentation_v2.py --pretty
./venv/bin/python scripts/orchestrator/validate_decision_intelligence_ux_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_multi_market_dashboard_v2_us_link_isolation_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_shared_navigation_ui_consistency_v1.py --pretty
```

## Controlled Publish

Publish only after merge from `main`:

```bash
./venv/bin/python scripts/orchestrator/publish_multi_market_dashboard_v2.py --apply --pretty
```

The publish result must keep:

- `notification_sent=false`
- `production_pipeline_executed=false`

## Rollback

Use the rollback command returned by the publish manifest. Rollback restores
HTML only and does not change scheduler, formulas, secrets, or notifications.

## Known Limitations

When runtime does not provide safe market-news headlines, the Dashboard shows a
clear market-news data status instead of generating fake headlines. This is
intentional.
