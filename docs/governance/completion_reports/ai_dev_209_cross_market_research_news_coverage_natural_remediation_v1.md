# AI-DEV-209 Cross-Market Research & News Coverage Natural Remediation V1

Status: `IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_NATURAL_VERIFICATION`

## Repository

- Starting main: `0de572c62adccb9201f477e53604bb229fb8f18c`
- Feature branch: `ai-dev/209-cross-market-research-news-coverage-remediation-v1`
- Issue: #260
- Implementation commits / PR / merge / CI: recorded in the final Codex handoff after governed completion.

## Root causes

The US adapter swallowed news retrieval exceptions and only parsed legacy flat Yahoo fields; the current provider response is nested under `content`. The pre-fix natural artifact therefore retained zero news and no diagnostic evidence explaining whether retrieval or parsing failed. TW compatibility projection allowed stale legacy card news to appear as current admitted/RRE evidence even though the research direction gate correctly refused to derive direction from it. US LINE and per-card Research also used different coverage contracts.

Exact pre-fix evidence and `UNKNOWN_NOT_PERSISTED` boundaries are recorded in `docs/governance/audits/ai_dev_209_2026_08_12_natural_root_cause_audit.{md,json}`.

## Architecture

- `cross_market_research_news_funnel_v1` carries exact discovery, retrieval, normalization, attribution, quality, freshness, relevance, materiality, dedupe, admission, RRE-use and render counts.
- Retrieval, parser, attribution, stale and downstream selection losses have deterministic reason/state semantics.
- US normalization supports nested and legacy provider shapes, preserves URLs/timestamps/publishers, and performs entity attribution before admission.
- Direction defaults to `unavailable / NOT_EVALUATED`; news visibility does not grant directional authority.
- TW compatibility evidence is rechecked against the current 72-hour window before RRE use.
- Effective weighted V2 coverage is the canonical Dashboard/LINE contract; legacy coverage remains explicitly named.
- Official/SEC/IR/company-newsroom source priority is explicit; SEC remains a separate official evidence class.

## Deterministic acceptance

The dedicated AI-DEV-209 validator covers nested provider admission, no-result, retrieval failure, attribution filtering, stale-only exclusion, admitted→RRE→render traceability, directionless evidence safety, TW official current evidence, TW stale compatibility exclusion, coverage parity, LINE parity and absence-state partitioning. It is registered ACTIVE/leaf and required in branch and post-merge gates.

## Safety

- Production pipeline executed: false
- Controlled/public publish: false
- LINE / Email attempted: false / false
- Trading/orders: false
- Strategy/scoring/prediction/ranking/eligibility/action/entry/stop/target/position sizing changed: false
- Scheduler/notification runtime changed: false
- Secrets accessed: false
- Production DB written: false
- Immutable history rewritten: false
- Pre-fix artifacts rewritten: false

## Natural verification

Deterministic fixtures and the controlled provider-shape probe are not natural verification. The next eligible post-merge TW four-window and US three-window lifecycles must demonstrate real exact funnels, current qualified evidence visibility, stale exclusion, Dashboard/LINE coverage parity, channel identity parity and unchanged Decision behavior.
