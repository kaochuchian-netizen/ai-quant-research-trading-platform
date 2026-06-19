#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/stock-ai}"
RUNTIME_DIR="${RUNTIME_DIR:-$HOME/.local/state/stock-ai-orchestrator}"
PLAN_JSON="$RUNTIME_DIR/ai_task_branch_plan.json"
PR_BODY_MD="$RUNTIME_DIR/ai_task_pr_body.md"

cd "$REPO_DIR"
mkdir -p "$RUNTIME_DIR"

echo "== AI task branch launcher =="
echo "Repository: $REPO_DIR"
echo "Runtime:    $RUNTIME_DIR"
echo

python3 scripts/orchestrator/prepare_ai_task_branch.py \
  --repo-root "$REPO_DIR" \
  --runtime-dir "$RUNTIME_DIR" \
  --pretty

if [[ ! -s "$PLAN_JSON" ]]; then
  echo "ERROR: missing branch plan: $PLAN_JSON"
  exit 1
fi

PREPARED="$(PLAN_JSON="$PLAN_JSON" python3 - << 'PY'
import json, os
with open(os.environ['PLAN_JSON'], 'r', encoding='utf-8') as f:
    data = json.load(f)
print('true' if data.get('prepared') else 'false')
PY
)"

if [[ "$PREPARED" != "true" ]]; then
  echo "ERROR: AI task branch plan is blocked"
  cat "$PLAN_JSON"
  exit 1
fi

BASE_BRANCH="$(PLAN_JSON="$PLAN_JSON" python3 - << 'PY'
import json, os
with open(os.environ['PLAN_JSON'], 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('base_branch') or 'main')
PY
)"

BRANCH_NAME="$(PLAN_JSON="$PLAN_JSON" python3 - << 'PY'
import json, os
with open(os.environ['PLAN_JSON'], 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('branch_name') or 'ai-dev/manual-task')
PY
)"

TASK_ID="$(PLAN_JSON="$PLAN_JSON" python3 - << 'PY'
import json, os
with open(os.environ['PLAN_JSON'], 'r', encoding='utf-8') as f:
    data = json.load(f)
print((data.get('task') or {}).get('task_id') or 'unknown')
PY
)"

echo
echo "Task:        $TASK_ID"
echo "Base branch: $BASE_BRANCH"
echo "Task branch: $BRANCH_NAME"
echo "Plan:        $PLAN_JSON"
echo "PR body:     $PR_BODY_MD"
echo

echo "== PR body preview =="
sed -n '1,160p' "$PR_BODY_MD"
echo

echo "== Safety boundaries =="
echo "No direct main changes."
echo "No automatic commit, push, or merge."
echo "No LINE notifications."
echo "No trading or order execution."
echo "No production workflows."
echo "No database or secret file changes."
echo

read -r -p "Type BRANCH to create/switch the AI task branch: " CONFIRM
if [[ "$CONFIRM" != "BRANCH" ]]; then
  echo "Cancelled. No branch changes made."
  exit 0
fi

if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
  git switch "$BRANCH_NAME"
else
  git switch "$BASE_BRANCH"
  git switch -c "$BRANCH_NAME"
fi

echo
echo "AI task branch is ready: $BRANCH_NAME"
echo

echo "Next validation commands after changes:"
echo "python3 scripts/orchestrator/validate_ai_branch.py --base $BASE_BRANCH --head HEAD --pretty"
echo "python3 scripts/orchestrator/check_forbidden_changes.py --base $BASE_BRANCH --head HEAD --pretty"
echo

echo "After validation passes, use normal git review flow:"
echo "git status"
echo "git diff --stat"
echo "git add <changed files>"
echo "git commit -m \"AI dev: $TASK_ID\""
echo "git push -u origin $BRANCH_NAME"
echo

echo "Then open a PR using the generated PR body: $PR_BODY_MD"
