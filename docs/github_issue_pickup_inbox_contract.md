# GitHub Issue Pickup Inbox Contract

## Purpose

AI-DEV-057 defines a mobile-friendly GitHub Issue pickup inbox for future
AI-DEV task intake. The user can create an Issue from the GitHub mobile app or
mobile web, apply approved labels, and let a future GCP resident runner identify
eligible requests.

This task is repo-side contract, template, validator, and dry-run helper work
only. It does not create, edit, label, comment on, close, or poll real GitHub
Issues.

## Mobile Workflow

1. Open GitHub mobile app or GitHub web on a phone.
2. Create a new Issue in the project repository.
3. Use a clear task title, preferably:

   ```text
   AI-DEV: <short task title>
   ```

4. Add the required labels:

   ```text
   ai-dev
   gcp-pickup
   dry-run
   ```

5. Describe the requested repo-side or dry-run orchestration work.
6. Never paste secrets, tokens, credentials, `.env` contents, private runtime
   payloads, production config values, account identifiers, or raw workflow
   exports.
7. A future GCP resident runner may pick up the Issue and produce a sanitized
   decision/result. Comment-back is a future task, not part of AI-DEV-057.

## Required Labels

An Issue is eligible only when all required labels are present:

- `ai-dev`
- `gcp-pickup`
- `dry-run`

The Issue must also be open.

## Optional Labels

Optional labels may refine routing without granting runtime permission:

- `docs`
- `contract`
- `validator`
- `template`
- `repo-only`
- `needs-review`
- `low-risk`

Optional labels must not override blocked task classes or safety gates.

## Allowed Task Classes

The inbox is intended for safe, repo-side or dry-run requests:

- documentation updates
- contracts and runbooks
- sanitized example templates
- validators
- dry-run helper scripts
- issue-to-plan conversion
- branch cleanup after confirmed merged PRs
- local AI-DEV queue closeout using existing tools and explicit approval

Allowed task classes still require normal branch, PR, validation, review, and
merge gates before tracked repo changes land.

## Blocked Task Classes

The pickup contract must reject or require manual review for requests involving:

- secrets, tokens, credentials, `.env`, private keys, or production config values
- Dify runtime calls
- OpenAI or ChatGPT API calls
- LINE, Email, webhook fanout, or notification delivery
- trading, order placement, or portfolio mutation
- production database mutation
- production n8n startup, shutdown, mutation, or credential inspection
- cron, systemd, timers, or background service mutation
- production pipeline execution
- private runtime payload inspection
- real GitHub Issue mutation by the dry-run helper

The dry-run helper uses conservative text pattern detection and emits sanitized
rejection reasons without preserving raw sensitive values.

## Pickup Eligibility Rules

A future GCP resident pickup runner may treat an Issue as eligible only when:

- `state` is `open`
- required labels are present
- the title/body contains no blocked action patterns
- the issue fixture validates as a JSON object
- no sensitive value pattern is detected
- no duplicate terminal pickup result exists for the idempotency key

When the request is ambiguous but not explicitly blocked, the decision should be
`needs_manual_review`.

## Dry-Run Default Behavior

AI-DEV-057 dry-run behavior is:

- read an issue fixture JSON
- evaluate state and labels
- scan title/body for blocked action patterns
- write a sanitized result artifact
- report no mutations and no runtime action

The helper must not:

- call GitHub APIs
- comment on Issues
- add or remove labels
- close or reopen Issues
- start a polling daemon
- call n8n, Dify, OpenAI, ChatGPT, LINE, Email, trading, production DB, cron, or
  systemd

## Approval Boundaries

Issue labels only make a request visible to future pickup logic. They do not
authorize runtime execution, production mutation, external delivery, trading, or
secret access.

Any future implementation that mutates GitHub Issues or posts comments must be a
separate reviewed task with its own validator and safety gates.

## Idempotency Policy

The idempotency key is:

```text
issue_number + issue_url + normalized required labels + task_class
```

A future runner should skip duplicate terminal results instead of reprocessing
the same Issue. Duplicate detection state must not include sensitive body text.

## Result And Comment-Back Contract

The dry-run result artifact records:

- issue identity
- labels seen
- required labels present
- eligibility
- decision
- reasons
- blocked terms detected
- task class
- dry-run and mutation flags
- sanitized summary
- next-step recommendation

A future comment-back workflow may post only the sanitized summary and next-step
recommendation. It must never echo raw secrets, private payloads, credentials,
or unsafe instructions.

## Closeout Rules

Closeout is complete when:

- dry-run helper output validates
- no real GitHub Issue mutation occurred
- no runtime action occurred
- repo changes pass normal AI-DEV validation
- any future comment-back is handled by a separately approved task

AI-DEV-057 itself does not implement a daemon, webhook, issue mutator, or
comment-back worker.

## Validation

Run:

```bash
python3 -m py_compile scripts/orchestrator/github_issue_pickup_dry_run.py scripts/orchestrator/validate_github_issue_pickup_result.py
python3 scripts/orchestrator/github_issue_pickup_dry_run.py --input templates/github_issue_pickup_request.example.json --output /tmp/github_issue_pickup_result.example.json --pretty
python3 scripts/orchestrator/validate_github_issue_pickup_result.py --input templates/github_issue_pickup_result.example.json --pretty
python3 scripts/orchestrator/validate_github_issue_pickup_result.py --input templates/github_issue_pickup_rejected.example.json --pretty
python3 scripts/orchestrator/validate_github_issue_pickup_result.py --input /tmp/github_issue_pickup_result.example.json --pretty
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
python3 scripts/orchestrator/validate_ai_branch.py --pretty
git diff --check main...HEAD
```
