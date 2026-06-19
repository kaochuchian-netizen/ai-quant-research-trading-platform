#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/stock-ai}"
RUNTIME_DIR="${RUNTIME_DIR:-$HOME/.local/state/stock-ai-orchestrator}"
HANDOFF_MD="$RUNTIME_DIR/current_codex_handoff.md"
HANDOFF_JSON="$RUNTIME_DIR/current_codex_handoff.json"
PREFLIGHT_JSON="$RUNTIME_DIR/codex_manual_launcher_preflight.json"

cd "$REPO_DIR"
mkdir -p "$RUNTIME_DIR"

echo "== Codex manual launcher =="
echo "Repository: $REPO_DIR"
echo "Runtime:    $RUNTIME_DIR"
echo

python3 scripts/orchestrator/codex_autostart_preflight.py \
  --repo-dir "$REPO_DIR" \
  --runtime-dir "$RUNTIME_DIR" \
  --skip-enable-flag-check \
  --skip-tmux-check \
  --pretty > "$PREFLIGHT_JSON"

PREFLIGHT_PASSED="$(PREFLIGHT_JSON="$PREFLIGHT_JSON" python3 - << 'PY'
import json, os
with open(os.environ['PREFLIGHT_JSON'], 'r', encoding='utf-8') as f:
    data = json.load(f)
print('true' if data.get('preflight_passed') else 'false')
PY
)"

if [[ "$PREFLIGHT_PASSED" != "true" ]]; then
  echo "ERROR: preflight blocked manual Codex launcher"
  echo "Preflight result: $PREFLIGHT_JSON"
  cat "$PREFLIGHT_JSON"
  exit 1
fi

BRANCH_NAME="$(PREFLIGHT_JSON="$PREFLIGHT_JSON" python3 - << 'PY'
import json, os
with open(os.environ['PREFLIGHT_JSON'], 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('branch_name') or 'codex/manual-task')
PY
)"

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "Preflight:      passed"
echo "Current branch: $CURRENT_BRANCH"
echo "Task branch:    $BRANCH_NAME"
echo "Preflight log:  $PREFLIGHT_JSON"
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
echo "Only work within handoff allowed_paths."
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
echo "安全邊界：不要發 LINE、不要下單、不要跑 production、不要碰 DB/secrets。"
echo

codex
