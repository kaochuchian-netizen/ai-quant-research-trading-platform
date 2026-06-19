#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/stock-ai}"
RUNTIME_DIR="${RUNTIME_DIR:-$HOME/.local/state/stock-ai-orchestrator}"
PLAN_JSON="$RUNTIME_DIR/ai_task_branch_plan.json"
PR_BODY_MD="$RUNTIME_DIR/ai_task_pr_body.md"
PR_SUMMARY_MD="$RUNTIME_DIR/ai_task_pr_summary.md"
PR_COMMANDS_SH="$RUNTIME_DIR/ai_task_pr_commands.sh"
VALIDATION_JSON="$RUNTIME_DIR/ai_dev_validation_bundle.json"

cd "$REPO_DIR"
mkdir -p "$RUNTIME_DIR"

echo "== AI PR creation wrapper =="
echo "Repository: $REPO_DIR"
echo "Runtime:    $RUNTIME_DIR"
echo

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git command not found"
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: GitHub CLI gh not found"
  echo "Install and authenticate gh before using this wrapper."
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh is not authenticated"
  echo "Run: gh auth login"
  exit 1
fi

if [[ ! -s "$PLAN_JSON" ]]; then
  echo "ERROR: missing branch plan: $PLAN_JSON"
  echo "Run: python3 scripts/orchestrator/prepare_ai_task_branch.py --pretty"
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
print(data.get('branch_name') or '')
PY
)"

PR_TITLE="$(PLAN_JSON="$PLAN_JSON" python3 - << 'PY'
import json, os
with open(os.environ['PLAN_JSON'], 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('pr_title') or 'AI Dev Task')
PY
)"

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ -z "$BRANCH_NAME" ]]; then
  echo "ERROR: branch name missing from plan"
  exit 1
fi

if [[ "$CURRENT_BRANCH" != "$BRANCH_NAME" ]]; then
  echo "ERROR: current branch must be $BRANCH_NAME, got $CURRENT_BRANCH"
  exit 1
fi

if [[ "$CURRENT_BRANCH" == "main" ]]; then
  echo "ERROR: refusing to create PR from main"
  exit 1
fi

echo "Running validation bundle..."
python3 scripts/orchestrator/run_ai_dev_validation_bundle.py \
  --base "$BASE_BRANCH" \
  --head HEAD \
  --runtime-dir "$RUNTIME_DIR" \
  --pretty

VALIDATION_PASSED="$(VALIDATION_JSON="$VALIDATION_JSON" python3 - << 'PY'
import json, os
with open(os.environ['VALIDATION_JSON'], 'r', encoding='utf-8') as f:
    data = json.load(f)
print('true' if data.get('passed') else 'false')
PY
)"

if [[ "$VALIDATION_PASSED" != "true" ]]; then
  echo "ERROR: validation bundle did not pass"
  cat "$VALIDATION_JSON"
  exit 1
fi

python3 scripts/orchestrator/prepare_ai_pr_summary.py \
  --runtime-dir "$RUNTIME_DIR" \
  --pretty

if [[ -n "$(git status --short)" ]]; then
  echo "ERROR: working tree has uncommitted changes. Commit reviewed changes before PR creation."
  git status --short
  exit 1
fi

if [[ ! -s "$PR_BODY_MD" ]]; then
  echo "ERROR: missing PR body: $PR_BODY_MD"
  exit 1
fi

echo
echo "== PR summary =="
sed -n '1,200p' "$PR_SUMMARY_MD" || true
echo

echo "This wrapper will push the current branch and create a PR."
echo "It will not merge, run production, send LINE, or place orders."
echo

read -r -p "Type PR to push branch and create pull request: " CONFIRM
if [[ "$CONFIRM" != "PR" ]]; then
  echo "Cancelled. No push or PR created."
  exit 0
fi

git push -u origin "$BRANCH_NAME"

gh pr create \
  --base "$BASE_BRANCH" \
  --head "$BRANCH_NAME" \
  --title "$PR_TITLE" \
  --body-file "$PR_BODY_MD"

echo
echo "PR created. Wait for GitHub Actions validation before merge."
