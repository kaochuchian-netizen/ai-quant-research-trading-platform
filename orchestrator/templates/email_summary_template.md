# AI Orchestrator Stage Summary Email Template

Subject: [AI Orchestrator] Task <task_id> completed: <task_name>

## Task

- Task ID: <task_id>
- Task name: <task_name>
- Completed at: <completed_at>
- Commit hash: <commit_hash_or_not_created>
- Commit message: <commit_message_or_not_applicable>

## Changed files

- <path>

## Change summary

- <summary>

## Validation results

- <command_or_check>: <passed_failed_or_skipped>

## Safety checks

- Production side effect detected: none / detected / blocked
- Forbidden path changes: none / list paths
- DB / migration / cron / LINE / formal pipeline: none / detected / blocked
- Credentials / environment files: none / detected / blocked
- Blocked reason: <reason_or_none>

## Next suggested task

- Task ID: <next_task_id>
- Task name: <next_task_name>

## Approval actions

The following actions only decide whether the Orchestrator may continue to the next already-defined task or pause. They do not approve migration, LINE sending, cron changes, production DB changes, formal pipeline execution, credential changes, protected branch merge, or trading actions.

- ✅ 同意繼續進行下一個工作
- ⏸️ 同意，但下一個工作先暫緩

## Notes

This is a draft template only. It does not send email, generate approval tokens, or trigger any workflow.
