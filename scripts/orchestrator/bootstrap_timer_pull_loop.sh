#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.config/systemd/user"
mkdir -p "$HOME/.local/state/stock-ai-orchestrator"

cat > "$HOME/.local/bin/stock-ai-orchestrator-loop.sh" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

cd "$HOME/stock-ai"

echo "$(date -Iseconds) bootstrap_loop start" >> "$HOME/.local/state/stock-ai-orchestrator/loop.log"

git pull --ff-only

"$HOME/stock-ai/venv/bin/python" "$HOME/stock-ai/scripts/orchestrator/run_loop_once.py" --check-remote --pretty

echo "$(date -Iseconds) bootstrap_loop done" >> "$HOME/.local/state/stock-ai-orchestrator/loop.log"
EOF

chmod +x "$HOME/.local/bin/stock-ai-orchestrator-loop.sh"

cat > "$HOME/.config/systemd/user/stock-ai-orchestrator-loop.service" << 'EOF'
[Unit]
Description=Stock AI Orchestrator bootstrap loop iteration

[Service]
Type=oneshot
WorkingDirectory=%h/stock-ai
ExecStart=%h/.local/bin/stock-ai-orchestrator-loop.sh
EOF

systemctl --user daemon-reload
systemctl --user restart stock-ai-orchestrator-loop.timer
systemctl --user start stock-ai-orchestrator-loop.service

systemctl --user status stock-ai-orchestrator-loop.timer --no-pager
systemctl --user status stock-ai-orchestrator-loop.service --no-pager

cat "$HOME/.local/state/stock-ai-orchestrator/loop_status.json"
tail -20 "$HOME/.local/state/stock-ai-orchestrator/loop.log"

git status
