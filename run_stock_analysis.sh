#!/bin/bash
set -euo pipefail

cd /home/kaochuchian/stock-ai

PYTHON_BIN="${PYTHON_BIN:-/home/kaochuchian/stock-ai/venv/bin/python}"
GATE_INPUT="${STOCK_AI_GATE_RUNTIME_INPUT:-templates/production_scheduler_gate_runtime_input.example.json}"
GATE_OUTPUT="${STOCK_AI_GATE_RUNTIME_OUTPUT:-/tmp/production_scheduler_gate_runtime_result.json}"
GATE_SUMMARY_OUTPUT="${STOCK_AI_GATE_RUNTIME_SUMMARY_OUTPUT:-/tmp/production_scheduler_gate_runtime_summary.json}"
LOG_PATH="${STOCK_AI_SCHEDULER_LOG_PATH:-logs/daily.log}"

detect_scheduler_window() {
  if [ -n "${STOCK_AI_SCHEDULER_WINDOW:-}" ]; then
    printf '%s\n' "$STOCK_AI_SCHEDULER_WINDOW"
    return
  fi

  case "$(TZ=Asia/Taipei date +%H%M)" in
    070*) printf '%s\n' "pre_open_0700" ;;
    130*) printf '%s\n' "intraday_1305" ;;
    133*) printf '%s\n' "pre_close_1335" ;;
    *) printf '%s\n' "pre_open_0700" ;;
  esac
}

WINDOW="$(detect_scheduler_window)"

if [ "${STOCK_AI_LEGACY_PRODUCTION_APPROVED:-0}" = "1" ]; then
  "$PYTHON_BIN" scripts/run_pipeline.py pre_open --production-approved >> "$LOG_PATH" 2>&1
  exit $?
fi

"$PYTHON_BIN" scripts/orchestrator/production_scheduler_gate_runtime.py \
  --input "$GATE_INPUT" \
  --output "$GATE_OUTPUT" \
  --summary-output "$GATE_SUMMARY_OUTPUT" \
  --window "$WINDOW" \
  --pretty >> "$LOG_PATH" 2>&1
