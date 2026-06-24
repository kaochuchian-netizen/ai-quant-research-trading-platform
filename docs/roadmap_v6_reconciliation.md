# V6 Roadmap Reconciliation

## 1. Purpose

This document reconciles the project roadmap for V6 and records the current
governance boundary for the active AI Dev workflow.

V6 is the latest active roadmap. V5 is the historical baseline that led to the
current closed-loop validation and post-merge workflow. AI-DEV-027 is the
governance bridge from the V5 implementation sequence into the V6 roadmap
sequence.

## 2. Current Project Baseline

- AI-DEV-027 is completed_by_pr and merged.
- The repository state is managed through the AI Dev closed loop.
- The current workflow already includes read-only platform inspection,
  branch-level validation, post-merge validation, and completed-task archiving.
- The GCP VM already has Dify and n8n available as infrastructure, but they are
  future automation control plane components only.

## 3. Why V6 Is Needed

V5 established the operational base for source governance, validation, and
post-merge control. V6 is needed to turn that base into a coherent roadmap that
can support:

- source inventory reconciliation
- company and industry intelligence layers
- credibility and cost governance
- forecast and review contracts
- report and dashboard output paths
- later controlled automation expansion

## 4. V6 Core Objective

V6 defines the next active roadmap as a layered, governed research and
reporting system that can eventually support production controls without losing
read-only discipline during the design phase.

The active V6 objective is to keep all new work:

- reviewable
- auditable
- read-only by default
- explicit about high-risk boundaries
- compatible with the existing AI Dev validation and closeout workflow

## 5. V6 System Layers

V6 is organized into the following layers:

1. Layer 1 Source Registry / Data Source Governance
2. Layer 2 Company Intelligence
3. Layer 3 Industry Intelligence
4. Layer 4 Source Credibility Scoring
5. Layer 5 Gemini Cost / Token / Cache Governance
6. Layer 6 Forecast / Prediction Review / Actual Outcome Evaluation
7. Layer 7 Report / Email / Dashboard / Production Gate

## 6. ChatGPT + Codex Hybrid PM-Developer Mode

V6 assumes a hybrid operating model:

- ChatGPT acts as the planning and governance partner.
- Codex acts as the implementation and validation partner.
- The operator role remains explicit for merge, archive, and closeout.

This mode is intended to keep the roadmap usable for iterative design while
still leaving all high-risk actions behind a human-reviewed gate.

The hybrid mode should remain:

- draft-first
- checklist-driven
- validation-aware
- readable by both human operators and automated reviewers

## 7. Existing Automation Infrastructure: Dify and n8n

The GCP VM already has Dify and n8n available. In V6 they are treated as future
automation control plane infrastructure, not as an immediately active
production-facing workflow.

Initial V6 usage boundaries:

- read-only inventory of what is installed
- draft-only workflow design
- checklist-only operational planning
- no automatic production mutation
- no automatic merge behavior
- no automatic notification behavior

Any future Dify/n8n control plane use must remain reviewed, explicit, and
aligned with the same safety boundaries as the rest of the AI Dev loop.

## 8. V6 Task Reconciliation

The roadmap task sequence is reconciled as follows:

- AI-DEV-028 V6 Roadmap Reconciliation
- AI-DEV-029 Dify n8n Automation Infrastructure Inventory
- AI-DEV-030 Source Inventory Registry Alignment
- AI-DEV-031 Company Intelligence Collection Plan
- AI-DEV-032 Industry Intelligence Collection Plan
- AI-DEV-033 Company Intelligence Sample Records and Validator
- AI-DEV-034 Industry Intelligence Sample Records and Validator
- AI-DEV-035 Source Credibility Scoring Prototype
- AI-DEV-036 Gemini Token Budget and Cache Guard Prototype
- AI-DEV-037 Daily Report Data Contract
- AI-DEV-038 Email Report Payload Prototype
- AI-DEV-039 Dashboard Data Payload Prototype
- AI-DEV-040 Report Metadata and Archive Plan
- AI-DEV-041 Forecast Generation Interface Design
- AI-DEV-042 Forecast Dry-run Pipeline Prototype
- AI-DEV-043 Forecast Evaluation Dry-run Integration
- AI-DEV-044 Prediction Review Auto-update Dry-run Prototype
- AI-DEV-045 Forecast Quality Summary Export
- AI-DEV-046 through AI-DEV-052 Dashboard MVP
- AI-DEV-053 through AI-DEV-060 Productionization and Automation Upgrade

AI-DEV-028 is a documentation-only reconciliation task. AI-DEV-029 is the next
task and must not be executed as part of AI-DEV-028.

## 9. High-risk Boundaries

The following actions remain high-risk and out of scope for this roadmap
reconciliation task:

- trading/order execution
- LINE/Email/notification sending
- cron/systemd/timer changes
- production pipeline changes
- formal DB writes
- secrets/credentials/.env changes
- production-approved runner
- large Gemini batch calls
- paid data source integration
- public dashboard exposure
- automatic PR merge by Dify/n8n
- automatic repo mutation by Dify/n8n

## 10. AI-DEV-028 Acceptance Criteria

AI-DEV-028 is complete when:

- `docs/roadmap_v6_reconciliation.md` exists
- the document defines V6 as the latest active roadmap
- V5 is clearly described as the historical baseline
- AI-DEV-027 is described as the V5 to V6 governance bridge
- the V6 system layers are listed in order
- Dify and n8n are described as future automation control plane components
- the task reconciliation list includes AI-DEV-028 through AI-DEV-060
- all high-risk boundaries are explicitly listed
- the document remains documentation-only and read-only in scope

## 11. Local Validation

Use the standard docs-only validation set:

```bash
git diff --check
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
python3 scripts/orchestrator/validate_post_merge_status.py --pretty --simulate-post-merge-success
git status --short
```

For this task, also confirm the diff only touches
`docs/roadmap_v6_reconciliation.md`.

## 12. Post-Merge Closeout Requirement

After the PR merges, treat post-merge validation as a mandatory closeout step:

```bash
cd ~/stock-ai
git checkout main
git pull --ff-only
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
python3 scripts/orchestrator/validate_post_merge_status.py --pretty
```

The closeout must confirm:

- inspector_ok is true
- post_merge_validator is true
- main_in_sync is true
- git_status_clean is true
- pending queue is 0

This closeout step is read-only. It does not authorize production execution,
notifications, trading, or scheduler changes.
