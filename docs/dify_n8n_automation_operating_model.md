# Dify n8n Automation Operating Model

## Purpose

This document defines the operating model for Dify and n8n as a broader AI-DEV
automation collaboration layer. The model is documentation-only and read-only
at this stage.

It exists to clarify how Dify, n8n, Codex, GitHub, ChatGPT, and the human
operator can share work without crossing into prohibited actions such as
trading, credential handling, secrets access, formal database writes, or
production-approved runner execution.

## Background

The project already uses an AI Dev closed-loop workflow for documentation,
validation, branch review, merge gating, post-merge closeout, and runtime
queue hygiene.

AI-DEV-029 established the inventory boundary for Dify and n8n. This document
extends that inventory into an operating model so future automation can be
planned in a controlled way instead of being improvised task by task.

The current assumption is that Dify and n8n can help orchestrate AI-DEV work,
but they do not gain permission to mutate production state, move money, trade,
or bypass human approval.

## Updated Automation Philosophy

The automation philosophy is:

1. Draft first.
2. Read-only by default.
3. Human approval before high-risk action.
4. Automation may assist, but it must not silently decide.
5. Repo mutation stays explicit and reviewable.
6. Production state remains outside the automation default path.

The goal is to use Dify and n8n to reduce coordination overhead while keeping
the safety boundary strict enough for research and governance work.

## Tool Role Definition

### Dify

Dify is the planning and document-assistance layer. It can help draft, organize,
and package AI-DEV work, but it must remain within read-only or human-gated
automation scope.

### n8n

n8n is the workflow and status-orchestration layer. It can gather status
signals, summarize progress, and assemble reports, but it must not create
unguarded production actions.

### Codex

Codex is the implementation and validation layer. It can edit repository files,
run local validation, commit, push, and prepare PRs, but only within the
approved task scope.

### GitHub

GitHub is the review and merge gate. It is the source of truth for PR state,
Actions state, mergeability, and merge closeout history.

### ChatGPT / User

ChatGPT and the user remain the architecture and governance decision makers.
They own final merge-gate judgment and all high-risk approvals.

## Allowed Automation Scope

The following work may be assisted by Dify or n8n, provided it remains read-only
or human-gated:

- task draft generation
- Codex prompt generation
- docs draft generation
- PR summary drafting
- CI summary drafting
- validation checklist generation
- closeout report draft generation
- dashboard progress payload drafting
- issue or PR comment draft generation
- roadmap tracking
- AI-DEV status summarization
- queue summary reporting
- closeout metadata summarization

## Human-Gated Automation Scope

The following actions can be prepared by automation, but a human must approve
them before execution:

- PR merge
- archive completed_by_pr
- branch cleanup
- repository mutation through Codex
- production pipeline change proposal
- notification workflow proposal
- dashboard deployment proposal
- changes that affect human review thresholds
- changes that alter the approval boundary

## Prohibited Automation Scope

The following actions remain prohibited:

- trading or order execution
- password or credential handling
- secrets, `.env`, or token read/write
- formal database writes
- production-approved runner execution
- auto PR merge without human approval
- large Gemini batch calls without approval
- paid data source connection without approval
- public dashboard exposure without approval
- silent production mutation
- silent scheduler mutation
- unreviewed notification delivery

## Dify Responsibilities

Dify may assist with:

- AI-DEV knowledge base drafting
- roadmap and runbook retrieval
- task draft generation
- Codex task package generation
- PR summary generation
- validation summary generation
- closeout summary generation
- acceptance checklist generation
- source doc draft generation
- schema doc draft generation
- report doc draft generation

Dify must not:

- create workflows that mutate production state without approval
- read secrets, `.env`, or credentials
- create or modify Dify KB content outside the approved documentation scope
- trigger trading or order execution
- perform formal DB writes
- bypass the human merge gate

## n8n Responsibilities

n8n may assist with:

- GitHub PR status tracking
- GitHub Actions status tracking
- changed files summary
- merge gate report generation
- progress tracking
- pending/completed queue summary
- daily dev status report drafting
- dashboard payload drafting
- triggering Dify workflows
- GitHub issue or PR comment draft generation

n8n must not:

- create workflows that auto-merge PRs without human approval
- create workflows that mutate repositories without Codex approval
- send LINE or email messages without explicit approval
- read secrets, `.env`, or credentials
- trigger trading or order execution
- write to the formal production database

## Codex Handoff Responsibilities

Codex is responsible for:

- repository implementation
- local validation
- commit creation
- push creation
- PR creation
- post-merge closeout commands

Codex must stay within the approved task boundary and must not be used to
smuggle in unrelated production changes, credential handling, or hidden
automation side effects.

## GitHub Integration Responsibilities

GitHub provides the governance spine for the operating model:

- PR state
- branch comparison
- mergeability
- Actions status
- checks summary
- review comments
- merge commit history
- branch cleanup evidence

Anything that claims progress or completion should be reconcilable against
GitHub PR state and the local read-only platform inspector.

## AI-DEV Workflow Integration

The intended AI-DEV workflow integration is:

1. Draft task in Dify or a related planning surface.
2. Reconcile task scope against roadmap and runbook.
3. Produce a Codex-ready task package.
4. Use Codex to implement and validate locally.
5. Publish a PR and let GitHub Actions validate it.
6. Use n8n or Dify to summarize PR, CI, and validation status.
7. Require human merge-gate judgment.
8. Perform post-merge closeout and archive only after the merge is real.

This integration is collaboration-oriented, not autonomy-oriented.

## Suggested Automation Levels

Automation levels are defined exactly as follows:

- Level 0: Manual only.
- Level 1: Draft assistance only.
- Level 2: Read-only status and summary assistance.
- Level 3: Human-gated workflow preparation.
- Level 4: Human-gated repo mutation and PR publication.
- Level 5: Human-gated post-merge closeout and archive support.

The current operating target is Level 1 to Level 3 for planning and
coordination, with Level 4 and Level 5 only available when a human explicitly
approves the action.

## Next Implementation Tasks

The next planned tasks are:

- AI-DEV-031 n8n GitHub PR Status Workflow Spec
- AI-DEV-032 Dify AI-DEV Knowledge Base Plan
- AI-DEV-033 n8n + Dify Merge Gate Assistant Prototype
- AI-DEV-034 AI-DEV Progress Dashboard Payload Workflow
- AI-DEV-035 Human-gated Closeout Assistant Plan

These are planning and design tasks only. They do not authorize production
execution or autonomous repo mutation.

## Acceptance Criteria

AI-DEV-030 is complete when:

- this document exists
- Dify responsibilities are explicitly listed
- n8n responsibilities are explicitly listed
- Codex responsibilities are explicitly listed
- GitHub responsibilities are explicitly listed
- ChatGPT / user responsibilities are explicitly listed
- allowed automation scope is clearly bounded
- human-gated scope is clearly bounded
- prohibited scope explicitly blocks trading, credentials, secrets, `.env`,
  DB writes, and production-approved runner usage
- the automation levels are defined exactly from 0 through 5
- the next implementation tasks are listed as AI-DEV-031 through AI-DEV-035
- the document remains documentation-only and does not enable any prohibited
  runtime action

