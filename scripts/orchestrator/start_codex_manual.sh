#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/stock-ai}"
RUNTIME_DIR="${RUNTIME_DIR:-$HOME/.local/state/stock-ai-orchestrator}"
HANDOFF_MD="$RUNTIME_DIR/current_codex_handoff.md"
HANDOFF_JSON="$RUNTIME_DIR/current_codex_handoff.json"

cd "$REPO_DIR"

echo "== Codex manual launcher =="
echo "Repository: $REPO_DIR"
echo "Runtime:    $RUNTIME_DIR"
echo

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git command not found"
  exit 1
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "ERROR: codex command not found"
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not inside a Git repository"
  exit 1
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "ERROR: expected to start from branch main, got: $CURRENT_BRANCH"
  exit 1
fi

if [[ -n "$(git status --short)" ]]; then
  echo "ERROR: working tree is not clean"
  git status --short
  exit 1
fi

if [[ ! -s "$HANDOFF_MD" ]]; then
  echo "ERROR: handoff markdown missing or empty: $HANDOFF_MD"
  exit 1
fi

if [[ ! -s "$HANDOFF_JSON" ]]; then
  echo "ERROR: handoff JSON missing or empty: $HANDOFF_JSON"
  exit 1
fi

TASK_ID="$(python3 - << 'PY'
import json, os, re
path = os.environ.get('HANDOFF_JSON')
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)
raw = data.get('task_id') or data.get('handoff_id') or 'manual-task'
safe = re.sub(r'[^A-Za-z0-9._-]+', '-', str(raw)).strip('-').lower()
print(safe or 'manual-task')
PY
)"

BRANCH_NAME="codex/${TASK_ID}"

echo "Current branch: $CURRENT_BRANCH"
echo "Task branch:    $BRANCH_NAME"
echo

echo "== Handoff preview =="
sed -n '1,120p' "$HANDOFF_MD"
echo

echo "== Safety boundaries =="
echo "Do not edit .env or secret files."
echo "Do not edit data/stock_analysis.db."
echo "Do not edit data/backups/."
echo "Do not edit analysis/output/."
echo "Do not change scheduler or timer settings."
echo "Do not run production workflows."
echo "Do not send LINE notifications."
echo "Do not perform trading or order execution."
echo

read -r -p "Type START to create/switch branch and open Codex: " CONFIRM
if [[ "$CONFIRM" != "START" ]]; then
  echo "Cancelled. No changes made."
  exit 0
fi

if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
  git switch "$BRANCH_NAME"
else
  git switch -c "$BRANCH_NAME"
fi

echo
echo "Opening Codex. Paste this instruction first:"
echo
echo "請先不要修改任何檔案。"
echo "請閱讀 $HANDOFF_MD，理解任務範圍、允許路徑、禁止路徑與驗證指令。"
echo "讀完後先回報你的執行計畫，不要先動手。"
echo

codex
