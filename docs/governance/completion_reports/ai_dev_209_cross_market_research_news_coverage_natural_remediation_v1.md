# AI-DEV-209 Cross-Market Research & News Coverage Natural Remediation V1

Status: `IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_NATURAL_VERIFICATION`

## Repository

- Starting main: `0de572c62adccb9201f477e53604bb229fb8f18c`
- Feature branch: `ai-dev/209-cross-market-research-news-coverage-remediation-v1`
- Issue: #260
- Implementation commit: `42f4a9f` (report reconciliation commit follows)
- PR: #261
- Pre-PR branch gate: PASS — 22 selected, 21 leaves executed/passed, 1 recursion guard, 0 failed, 0 unexplained skips
- Merge / CI: pending at report reconciliation time; final identities are recorded in the Codex handoff.

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

Validation commands completed before PR:

- `./venv/bin/python -m py_compile <all changed Python modules>` — PASS
- `./venv/bin/python scripts/orchestrator/validate_ai_dev_209_cross_market_research_news_coverage_v1.py --pretty` — PASS (15/15)
- `./venv/bin/python scripts/orchestrator/validate_ai_dev_207_tw_research_evidence_coverage_news_visibility_v1.py --pretty` — PASS
- `./venv/bin/python scripts/orchestrator/validate_ai_dev_201_us_research_intelligence_v2.py --pretty` — PASS
- `./venv/bin/python scripts/orchestrator/validate_ai_dev_202_tw_production_intelligence_v1.py --pretty` — PASS (18 checks)
- `./venv/bin/python scripts/orchestrator/validate_ai_dev_208_visual_evidence_archive_v1.py --pretty` — PASS
- `./venv/bin/python scripts/orchestrator/audit_source_inventory_registry.py --pretty` — PASS
- `./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty` — PASS
- `git diff --check main...HEAD` — PASS

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
