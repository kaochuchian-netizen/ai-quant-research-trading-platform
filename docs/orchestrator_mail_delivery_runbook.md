# AI DevOps Orchestrator Mail Delivery Runbook

This runbook explains how to configure the Orchestrator notification adapter safely on the VM.

The current adapter is `scripts/orchestrator/notify_stage_report.py`.

## Current state

The adapter supports two modes:

- Preview mode: default. It prints a JSON preview and does not deliver anything.
- Send mode: enabled only when `--send` is explicitly provided and required environment variables exist.

Preview mode is the required validation step before any live delivery test.

## Safety rules

Do not commit local mail settings to Git.
Do not paste account credentials into project files.
Do not store account credentials in docs, templates, or source code.
Do not use the Orchestrator mail adapter as an approval endpoint.
Do not use notification delivery as permission to run migration, LINE delivery, cron changes, database changes, formal pipeline execution, credential changes, or trading actions.

## Environment variables

The adapter reads these variables from the shell environment:

```bash
ORCH_MAIL_HOST="smtp.example.com"
ORCH_MAIL_PORT="587"
ORCH_MAIL_USER="your-account@example.com"
ORCH_MAIL_PASS="use-a-provider-app-password-or-vault-value"
ORCH_MAIL_FROM="your-account@example.com"
ORCH_MAIL_TO="recipient@example.com"
```

`ORCH_MAIL_PASS` must be treated as sensitive. Prefer a provider app password or a value loaded from a local secret manager.

## Local-only setup option

Create a local file outside the repository, for example:

```bash
mkdir -p ~/.config/stock-ai-orchestrator
nano ~/.config/stock-ai-orchestrator/mail.env
chmod 600 ~/.config/stock-ai-orchestrator/mail.env
```

Then put the environment exports in that local file:

```bash
export ORCH_MAIL_HOST="smtp.example.com"
export ORCH_MAIL_PORT="587"
export ORCH_MAIL_USER="your-account@example.com"
export ORCH_MAIL_PASS="use-a-provider-app-password-or-vault-value"
export ORCH_MAIL_FROM="your-account@example.com"
export ORCH_MAIL_TO="recipient@example.com"
```

Load it only in the terminal session that will run the adapter:

```bash
source ~/.config/stock-ai-orchestrator/mail.env
```

## Preview validation

Generate a notice and preview it before using send mode:

```bash
cd ~/stock-ai

python3 scripts/orchestrator/collect_validation_snapshot.py \
  --python-file scripts/orchestrator/notify_stage_report.py \
  --pretty > /tmp/orchestrator_validation_snapshot.json

python3 scripts/orchestrator/render_notice_from_template.py \
  --template orchestrator/templates/email_summary_template.md \
  --task-state orchestrator/templates/task_state.example.json \
  --validation-snapshot /tmp/orchestrator_validation_snapshot.json \
  --output /tmp/orchestrator_notice.md

python3 scripts/orchestrator/notify_stage_report.py \
  --notice /tmp/orchestrator_notice.md
```

Expected preview behavior:

- `send` is `false`.
- `subject` is populated.
- `configured_to` is populated only after local environment variables are loaded.
- `configured_from` is populated only after local environment variables are loaded.

## Live delivery test

Only after preview is correct, run:

```bash
python3 scripts/orchestrator/notify_stage_report.py \
  --notice /tmp/orchestrator_notice.md \
  --send
```

A successful delivery prints:

```text
sent
```

## Troubleshooting

If configuration is missing, the adapter reports missing fields and does not send.
If authentication fails, verify the provider app password or SMTP settings.
If the provider blocks SMTP, use that provider's documented app-password or SMTP enablement process.

## Git checks

After any mail setup work, verify no local secret file is inside the repository:

```bash
cd ~/stock-ai
git status
```

Expected result:

```text
nothing to commit, working tree clean
```
