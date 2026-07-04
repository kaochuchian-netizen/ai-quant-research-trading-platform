# AI-DEV-135: Codex Workspace Governance & Single-Repo Operating Rule V1

## Purpose

AI-DEV-135 establishes the workspace governance rule for future AI-DEV work. It prevents confusion between historical local workspaces and the formal execution repository.

## Source Of Truth

GitHub is the only source of truth for repository state, pull requests, review history, merge history, and release state.

The formal repository is:

- `kaochuchian-netizen/ai-quant-research-trading-platform`

## Formal Execution Workspace

The formal execution workspace is the GCP VM repository:

- host alias: `stock-ai-gcp`
- path: `~/stock-ai`

All AI-DEV repo operations must start by connecting to the GCP workspace and entering the repo:

```bash
ssh stock-ai-gcp
cd ~/stock-ai
```

Codex App's `stock-ai` workspace is the formal AI-DEV coordination workspace for prompts, repo-oriented planning, validation relay, and review summaries. It must not be confused with historical local folders.

## Deprecated / Historical Workspace

The `wimac` workspace is retained only for historical chats, attachments, and reference context. It must not be used as the workspace for new AI-DEV repo mutation tasks.

Future AI-DEV work must not modify MacBook or iPhone local workspace copies unless a task explicitly authorizes that local workspace as the target.

## Standard AI-DEV Task Opening Rule

Every future AI-DEV task should begin with this operating rule:

1. SSH to `stock-ai-gcp`.
2. `cd ~/stock-ai`.
3. Confirm branch and git status.
4. Perform repo work only in GCP `~/stock-ai`.
5. Do not modify MacBook / iPhone local workspaces.
6. Treat GitHub PR state and GitHub Actions as the source of truth for merge gates.

## Workspace Responsibility Matrix

| Workspace | Role | Allowed Use | Forbidden Use |
| --- | --- | --- | --- |
| GitHub repo | Source of truth | PRs, checks, merge history, branch state | Direct bypass of PR governance |
| GCP `~/stock-ai` | Formal execution workspace | Branch, implementation, validation, commit, push, PR closeout | Secrets access, production runtime unless explicitly approved |
| Codex App `stock-ai` | Formal AI-DEV coordination workspace | Task planning, SSH relay, summary, local non-mutating context | New repo mutation outside GCP unless explicitly authorized |
| `wimac` historical workspace | Archive/reference | Old chats and attachments | New AI-DEV repo mutation |

## Safety Boundary

This governance task is documentation and deterministic artifact only. It does not call external APIs, read secrets, modify scheduler/runtime infrastructure, send LINE/Email, publish dashboards, write databases, access brokers, place orders, trade, or change production logic.

Required safety statements for future AI-DEV workspace governance:

- No external APIs.
- No secrets.
- No LINE/Email.
- No production logic changes.
- No scheduler, database, dashboard publish, broker, order, or trading changes.

## Validation

Run:

```bash
./venv/bin/python -m py_compile scripts/orchestrator/validate_codex_workspace_governance_v1.py
./venv/bin/python scripts/orchestrator/validate_codex_workspace_governance_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Future Use

Future AI-DEV task prompts should reference this rule when there is any ambiguity about local MacBook, iPhone relay, Codex App, GCP VM, or GitHub repository state.
