#!/usr/bin/env python3
"""Validate TW 15:00 outcome delivery and seven-window no-send payload safety."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.reports.decision_intelligence_v4 import (
    delivery_summary_lines,
    project_decision_intelligence_v4,
    seven_day_review_summary,
)
from app.reports.window_report_contract import all_window_report_contracts
from app.reports.tw_post_close_review import build_structured_review_payload

CANONICAL_URL = (
    "http://35.201.242.167/stock-ai-dashboard/"
    "dashboard/archive/tw/post_close_1500/latest/index.html"
)
LEGACY_UNBUILT_URL = "/dashboard/tw/15-00/latest/index.html"
TW_WINDOWS = ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")
US_WINDOWS = ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630")


def card(stock_id: str, status: str) -> dict[str, Any]:
    review: dict[str, Any] = {"status": status}
    tactical = {"action": "observe", "entry_zone": {"low": 10, "high": 11}, "confidence": 60}
    if status == "no_trade":
        tactical["action"] = "no_trade"
    return {"stock_id": stock_id, "strategies": {"daily_tactical": tactical}, "review_snapshot": review}


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def no_placeholder(text: str, forbidden_lines: set[str]) -> bool:
    lines = {line.strip() for line in text.splitlines() if line.strip()}
    return not re.search(r"(?:：|:)\s*N(?:\b|$)", text) and not (lines & forbidden_lines)


def run_json(command: list[str], output: Path | None = None) -> tuple[int, dict[str, Any], str]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
    if output is not None and output.exists():
        payload = json.loads(output.read_text(encoding="utf-8"))
    else:
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {}
    return completed.returncode, payload, completed.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}

    fixture = {
        "cards": [
            card("HIT", "win"), card("NOT", "not_triggered"), card("FAIL", "loss"),
            card("NONE", "no_trade"), card("WAIT", "breakeven"),
        ]
    }
    projection = project_decision_intelligence_v4("TW", "post_close_1500", fixture)
    review = {"stocks": [{"seven_day_hit_rate": 0.75}, {"seven_day_hit_rate": 0.5}, {"seven_day_hit_rate": None}]}
    lines = delivery_summary_lines(projection, review_payload=review)
    checks["deterministic_five_outcomes"] = lines[0] == "今日結果：命中 1、未觸發 1、失敗 1、無交易 1、待確認 1"
    checks["deterministic_seven_day_metrics"] = lines[1] == "7 日檢討：有效樣本 2，平均命中率 62.5%"
    pending = seven_day_review_summary({"stocks": [{"seven_day_hit_rate": None}]})
    checks["seven_day_pending_not_fabricated"] = pending == {
        "sample_count": 0, "hit_rate": None, "status": "pending_insufficient_sample", "invented_values": False,
    }

    formal_paths = [
        ROOT / "artifacts/runtime/formal_prediction_review_runtime_latest.json",
        ROOT / "artifacts/runtime/us_stock/us_pre_market_2000_latest.json",
        ROOT / "artifacts/runtime/us_stock/us_intraday_2300_latest.json",
        ROOT / "artifacts/runtime/us_stock/us_post_close_review_0630_latest.json",
    ]
    before = {str(path): digest(path) for path in formal_paths}
    contracts = all_window_report_contracts()
    forbidden = {
        item for contract in contracts for item in contract.line_summary_scope[:-1]
    }
    matrix: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="ai-dev-181c-no-send-") as raw:
        temp = Path(raw)
        for window in TW_WINDOWS:
            output = temp / f"tw-{window}.json"
            code, payload, stderr = run_json([
                sys.executable, "scripts/orchestrator/approved_pre_open_delivery.py",
                "--window", window, "--dry-run", "--output", str(output),
            ], output)
            line = str(payload.get("line_payload_preview", ""))
            email = str(payload.get("email_payload_preview", ""))
            key = f"TW:{window}"
            checks[key + ":entrypoint"] = code == 0 and payload.get("mode") == "dry_run_no_delivery"
            checks[key + ":no_send"] = payload.get("line_delivery_status") == "dry_run_not_sent" and payload.get("email_delivery_status") == "dry_run_not_sent"
            checks[key + ":no_placeholder"] = no_placeholder(line, forbidden) and no_placeholder(email, forbidden)
            matrix[key] = {"line": line, "email": email, "stderr": stderr}
        for window in US_WINDOWS:
            output = temp / f"us-{window}.json"
            code, payload, stderr = run_json([
                sys.executable, "scripts/orchestrator/approved_us_stock_delivery.py",
                "--window", window, "--dry-run", "--pretty", "--output", str(output),
            ], output)
            status = payload.get("status", {}) if isinstance(payload.get("status"), dict) else {}
            line = str(payload.get("line_payload_preview") or status.get("line_payload_preview") or "")
            email = str(payload.get("email_payload_preview") or status.get("email_payload_preview") or "")
            key = f"US:{window}"
            checks[key + ":entrypoint"] = code == 0 and status.get("dry_run") is True
            checks[key + ":no_send"] = not payload.get("line", {}).get("attempted") and not payload.get("email", {}).get("attempted")
            checks[key + ":no_placeholder"] = no_placeholder(line, forbidden) and no_placeholder(email, forbidden)
            matrix[key] = {"line": line, "email": email, "stderr": stderr}
    checks["temporary_outputs_removed"] = not Path(raw).exists()
    after = {str(path): digest(path) for path in formal_paths}
    checks["formal_runtime_hash_stable"] = before == after

    tw = matrix.get("TW:post_close_1500", {})
    tw_line, tw_email = tw.get("line", ""), tw.get("email", "")
    current_review = json.loads((ROOT / "artifacts/runtime/formal_prediction_review_runtime_latest.json").read_text(encoding="utf-8"))
    current_window = json.loads((ROOT / "artifacts/runtime/tw_window_decision/post_close_1500_latest.json").read_text(encoding="utf-8"))
    structured = build_structured_review_payload(current_review, current_window)
    counts = structured["outcome_counts"]
    expected_tokens = [f"命中 {counts['hit']}", f"未觸發 {counts['not_triggered']}", f"失敗 {counts['fail']}", f"無交易 {counts['no_trade']}", f"待確認 {counts['pending']}"]
    checks["tw_1500_actual_counts_line_email"] = all(token in tw_line and token in tw_email for token in expected_tokens)
    if structured.get("seven_day_hit_rate") is None:
        expected_review = "7 日檢討：待累積"
    else:
        expected_review = f"7 日檢討：有效樣本 {structured['seven_day_sample_count']}｜平均命中率 {structured['seven_day_hit_rate']:.1%}"
    checks["tw_1500_seven_day_line_email_parity"] = expected_review in tw_line and expected_review in tw_email
    checks["tw_1500_canonical_url"] = CANONICAL_URL in tw_line and CANONICAL_URL in tw_email
    checks["tw_1500_unbuilt_url_absent"] = LEGACY_UNBUILT_URL not in tw_line + tw_email
    evidence = {
        "deterministic_lines": lines,
        "tw_1500_line_payload": tw_line,
        "tw_1500_email_outcome_lines": [line for line in tw_email.splitlines() if "今日結果：" in line or "7 日檢討：" in line],
        "scheduler_equivalent_no_send_windows": sorted(matrix),
        "formal_runtime_hash_before": before,
        "formal_runtime_hash_after": after,
    }
    errors = [name for name, passed in checks.items() if not passed]
    result = {
        "schema_version": "tw_post_close_outcome_delivery_validation_v1",
        "task_id": "AI-DEV-181C", "ok": not errors, "errors": errors,
        "checks": checks, "evidence": evidence,
        "safety": {
            "email_attempted": False, "line_attempted": False, "production_delivery": False,
            "trading": False, "scheduler_changed": False, "python3_main_executed": False,
            "secrets_accessed": False,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
